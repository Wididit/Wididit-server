"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

import json
import base64

from django.test import TestCase
from django.test.client import Client

def get_token(login, password):
    return 'Basic ' + base64.b64encode(':'.join([login, password]))

class WididitTestCase(TestCase):
    def getExtras(self, user='tester'):
        return {'HTTP_AUTHORIZATION': get_token(user, 'foo')}

    def setUp(self):
        c = Client()

        response = c.post('/api/json/people/', {
            'username': 'tester',
            'email': 'tester@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/json/people/', {
            'username': 'tester2',
            'email': 'tester2@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/json/people/', {
            'username': 'tester3',
            'email': 'tester2@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)



class TestPeople(TestCase):
    def test_creation(self):
        c = Client()

        response = c.get('/api/json/people/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 0)

        response = c.post('/api/json/people/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/people/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['username'], 'tester')

    def test_update(self):
        c = Client()

        response = c.post('/api/json/people/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/json/people/', {
            'username': 'tester2',
            'email': 'foo@wididit.net',
            'password': 'foo2'})
        self.assertEqual(response.status_code, 201, response.content)

        response = c.put('/api/json/people/tester/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 401, response.content)
        response = c.put('/api/json/people/tester2/', {
            'username': 'tester2',
            'email': 'foo@wididit.net',
            'password': 'foo2'})
        self.assertEqual(response.status_code, 401, response.content)

        c.login(login='tester', password='foo')
        response = c.put('/api/json/people/tester/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo2'},
            HTTP_AUTHORIZATION=get_token('tester', 'pgojgoergpoer'))
        self.assertEqual(response.status_code, 401, response.content)
        response = c.put('/api/json/people/tester/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo2'},
            HTTP_AUTHORIZATION=get_token('tester', 'foo'))
        self.assertEqual(response.status_code, 200, response.content)
        response = c.put('/api/json/people/tester/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'},
            HTTP_AUTHORIZATION=get_token('tester', 'foo'))
        self.assertEqual(response.status_code, 401, response.content)
        response = c.put('/api/json/people/tester/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'},
            HTTP_AUTHORIZATION=get_token('tester', 'foo2'))
        self.assertEqual(response.status_code, 200, response.content)

        response = c.put('/api/json/people/tester2/', {
            'username': 'tester2',
            'email': 'foo@wididit.net',
            'password': 'foo2'})
        self.assertEqual(response.status_code, 401, response.content)

    def test_privacy(self):
        c = Client()

        response = c.post('/api/json/people/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.get('/api/json/people/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertNotIn('password', reply[0])
        self.assertNotIn('email', reply[0])
        self.assertNotIn('user', reply[0])

class TestEntry(WididitTestCase):
    def testPost(self):
        c = Client()

        response = c.post('/api/json/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            })
        self.assertEqual(response.status_code, 401, response.content)

        response = c.post('/api/json/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['content'], 'This is a test')
        self.assertEqual(reply[0]['generator'], 'API tests')
        self.assertEqual(reply[0]['title'], 'test')

        response = c.post('/api/json/entry/?author=tester', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test2',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 2)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['content'], 'This is a test')
        self.assertEqual(reply[1]['id'], 2)
        self.assertEqual(reply[1]['content'], 'This is a second test')

    def testEdit(self):
        c = Client()

        response = c.post('/api/json/entry/?author=tester', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.put('/api/json/entry/tester/1/', {
            'content': 'This is an editted test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)

        response = c.get('/api/json/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['content'], 'This is an editted test')

    def testDelete(self):
        c = Client()

        response = c.post('/api/json/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.delete('/api/json/entry/tester/1/', **self.getExtras())
        self.assertEqual(response.status_code, 204, response.content)
        response = c.get('/api/json/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 0)

    def testSearch(self):
        c = Client()

        response = c.post('/api/json/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/json/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/?content=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 0)

        response = c.get('/api/json/entry/?content=second')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['author']['username'], 'tester2')

        response = c.get('/api/json/entry/?content=second&author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 0)

    def testPermissions(self):
        c = Client()

        response = c.post('/api/json/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'contributors': 'tester2',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/tester/1/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply['contributors']), 1)
        self.assertEqual(reply['contributors'][0]['username'], 'tester2')

        response = c.put('/api/json/entry/tester/1/', {
            'content': 'This is an editted test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 200, response.content)

        response = c.put('/api/json/entry/tester/1/', {
            'contributors': []
            }, **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)

        response = c.get('/api/json/entry/tester/1/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply['contributors']), 0)

    def testThreads(self):
        c = Client()

        response = c.post('/api/json/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)

        response = c.post('/api/json/entry/tester/1/', {
            'content': 'another test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 2)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['in_reply_to'], None)
        self.assertEqual(reply[1]['id'], 2)
        self.assertEqual(reply[1]['in_reply_to']['id'], 1)

        response = c.get('/api/json/entry/?in_reply_to=tester/1')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['id'], 2)
        self.assertEqual(reply[0]['in_reply_to']['id'], 1)

        response = c.post('/api/json/entry/tester/1/', {
            'content': 'another test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/?in_reply_to=tester/1')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 2)

        response = c.post('/api/json/entry/tester/2/', {
            'content': 'another test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/?in_reply_to=tester/1')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 2)


class TestSubscription(WididitTestCase):
    def testPeople(self):
        c = Client()

        response = c.get('/api/json/entry/timeline/')
        self.assertEqual(response.status_code, 401, response.content)

        response = c.get('/api/json/subscription/tester/people/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 0)

        response = c.get('/api/json/entry/timeline/', **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 0)

        response = c.post('/api/json/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/json/subscription/tester/people/', {
            'target_people': 'tester2'}, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/subscription/tester/people/',
                **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['target_people']['username'], 'tester2')

        response = c.get('/api/json/entry/timeline/', **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)

        response = c.post('/api/json/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester3'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/timeline/', **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)

