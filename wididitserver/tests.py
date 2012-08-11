"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

import json
import base64

from urlparse import urlparse
from django.test import TestCase
from django.test.client import Client as DjangoClient
from django.test.client import FakePayload

class Client(DjangoClient):
    def post(self, path, data, *args, **kwargs):
        if 'content_type' not in kwargs:
            kwargs['content_type'] = 'application/json'
        kwargs['data'] = json.dumps(data)
        return super(Client, self).post(path, *args, **kwargs)
    def patch(self, path, data={}, content_type='application/json',
              **extra):
        "Construct a PATCH request."

        if content_type == 'application/json':
            post_data = json.dumps(data)
        else:
            post_data = self._encode_data(data, content_type)

        parsed = urlparse(path)
        r = {
            'CONTENT_LENGTH': len(post_data),
            'CONTENT_TYPE':   content_type,
            'PATH_INFO':      self._get_path(parsed),
            'QUERY_STRING':   parsed[4],
            'REQUEST_METHOD': 'PATCH',
            'wsgi.input':     FakePayload(post_data),
        }
        r.update(extra)
        return self.request(**r)

def get_token(login, password):
    return 'Basic ' + base64.b64encode(':'.join([login, password]))

class WididitTestCase(TestCase):
    def getExtras(self, user='tester'):
        return {'HTTP_AUTHORIZATION': get_token(user, 'foo')}

    def setUp(self):
        c = Client()

        response = c.post('/api/v1/people/', {
            'username': 'tester',
            'email': 'tester@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/v1/people/', {
            'username': 'tester2',
            'email': 'tester2@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/v1/people/', {
            'username': 'tester3',
            'email': 'tester2@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)



class TestPeople(TestCase):
    def test_creation(self):
        c = Client()

        response = c.get('/api/v1/people/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

        response = c.post('/api/v1/people/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/people/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['username'], 'tester')

    def test_update(self):
        c = Client()

        response = c.post('/api/v1/people/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/v1/people/', {
            'username': 'tester2',
            'email': 'foo@wididit.net',
            'password': 'foo2'})
        self.assertEqual(response.status_code, 201, response.content)

        response = c.patch('/api/v1/people/tester/', {
            'email': 'foo@wididit.net'})
        self.assertEqual(response.status_code, 401, response.content)
        response = c.patch('/api/v1/people/tester2/', {
            'email': 'foo@wididit.net'})
        self.assertEqual(response.status_code, 401, response.content)

        response = c.get('/api/v1/people/tester/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(reply['username'], 'tester')

        response = c.patch('/api/v1/people/tester/', {
            'password': 'foo2'},
            HTTP_AUTHORIZATION=get_token('tester', 'pgojgoergpoer'))
        self.assertEqual(response.status_code, 401, response.content)
        response = c.patch('/api/v1/people/tester/', {
            'password': 'foo2'},
            HTTP_AUTHORIZATION=get_token('tester', 'foo'))
        self.assertEqual(response.status_code, 202, response.content)
        response = c.patch('/api/v1/people/tester/', {
            'email': 'foo@wididit.net'},
            HTTP_AUTHORIZATION=get_token('tester', 'foo'))
        self.assertEqual(response.status_code, 401, response.content)
        response = c.patch('/api/v1/people/tester/', {
            'email': 'foo@wididit.net'},
            HTTP_AUTHORIZATION=get_token('tester', 'foo2'))
        self.assertEqual(response.status_code, 202, response.content)

        response = c.patch('/api/v1/people/tester/', {
            'email': 'foo@wididit.net'},
            HTTP_AUTHORIZATION=get_token('tester', 'foo'))
        self.assertEqual(response.status_code, 401, response.content)

        response = c.patch('/api/v1/people/tester2/', {
            'email': 'foo@wididit.net'})
        self.assertEqual(response.status_code, 401, response.content)

    def test_privacy(self):
        c = Client()

        response = c.post('/api/v1/people/', {
            'username': 'tester',
            'email': 'foo@wididit.net',
            'password': 'foo'})
        self.assertEqual(response.status_code, 201, response.content)
        response = c.get('/api/v1/people/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertNotIn('password', reply[0])
        self.assertIs(reply[0]['email'], None)
        self.assertNotIn('user', reply[0])

class TestEntry(WididitTestCase):
    def testPost(self):
        c = Client()

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            })
        self.assertEqual(response.status_code, 401, response.content)

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['content'], 'This is a test')
        self.assertEqual(reply[0]['generator'], 'API tests')
        self.assertEqual(reply[0]['title'], 'test')

        response = c.post('/api/v1/entry/?author=tester', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test2',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 2)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['content'], 'This is a test')
        self.assertEqual(reply[1]['id'], 2)
        self.assertEqual(reply[1]['content'], 'This is a second test')

    def testEdit(self):
        c = Client()

        response = c.post('/api/v1/entry/?author=tester', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.patch('/api/v1/entry/tester/1/', {
            'content': 'This is an editted test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 202, response.content)

        response = c.get('/api/v1/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['title'], 'test')
        self.assertEqual(reply[0]['content'], 'This is an editted test')

    def testDelete(self):
        c = Client()

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.delete('/api/v1/entry/tester/1/', **self.getExtras())
        self.assertEqual(response.status_code, 204, response.content)
        response = c.get('/api/v1/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

    def testSearch(self):
        c = Client()

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)
        response = c.post('/api/v1/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?content__contains=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

        response = c.get('/api/v1/entry/?content__contains=second')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['author'].split('@')[0], 'tester2')

        response = c.get('/api/v1/entry/?content=second&author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

    def testPermissions(self):
        c = Client()

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'contributors': ['tester2'],
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/tester/1/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply['contributors']), 1)
        self.assertEqual(reply['contributors'][0].split('@')[0], 'tester2')

        response = c.patch('/api/v1/entry/tester/1/', {
            'content': 'This is an editted test',
            'generator': 'API tests',
            'contributors': ['tester2'],
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 202, response.content)

        response = c.patch('/api/v1/entry/tester/1/', {
            'content': 'This is an editted test',
            'generator': 'API tests',
            'contributors': [],
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 202, response.content)

        response = c.get('/api/v1/entry/tester/1/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply['contributors']), 0)

    def testThreads(self):
        c = Client()

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)

        response = c.post('/api/v1/entry/', {
            'in_reply_to': 'tester/1',
            'content': 'another test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?author=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 2)
        self.assertEqual(reply[0]['id'], 1)
        self.assertEqual(reply[0]['in_reply_to'], None)
        self.assertEqual(reply[1]['id'], 2)
        self.assertEqual(reply[1]['in_reply_to'].split('/')[1], '1')

        response = c.get('/api/v1/entry/?in_reply_to=tester/1')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['id'], 2)
        self.assertEqual(reply[0]['in_reply_to'].split('/')[1], '1')

        response = c.post('/api/v1/entry/', {
            'in_reply_to': 'tester/1',
            'content': 'another test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?in_reply_to=tester/1')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 2)

        response = c.post('/api/v1/entry/', {
            'in_reply_to': 'tester/2',
            'content': 'another test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?in_reply_to=tester/1')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 2)

    def testShare(self):
        c = Client()

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/v1/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/v1/entry/', {
            'content': 'This is a third test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/v1/share/', {
            'entry': 'tester/2',
            }, **self.getExtras('tester3'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?nonative&shared')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['content'], 'This is a second test')

        response = c.get('/api/v1/entry/?nonative')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

        response = c.get('/api/v1/entry/?shared')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 3)


class TestSubscription(WididitTestCase):
    def testPeople(self):
        c = Client()

        response = c.get('/api/v1/entry/?timeline')
        self.assertEqual(response.status_code, 401, response.content)

        response = c.get('/api/v1/subscription/people/?subscriber=tester')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

        response = c.get('/api/v1/entry/?timeline', **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

        response = c.post('/api/v1/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/v1/subscription/people/', {
            'target': 'tester2'}, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/subscription/people/?subscriber=tester',
                **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['target'].split('@')[0], 'tester2')

        response = c.get('/api/v1/entry/?timeline', **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)

        response = c.post('/api/v1/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester3'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?timeline', **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)

    def testShare(self):
        c = Client()

        response = c.post('/api/v1/entry/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/v1/entry/', {
            'content': 'This is a second test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/v1/entry/', {
            'content': 'This is a third test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.post('/api/v1/share/', {
            'entry': 'tester/2',
            }, **self.getExtras('tester3'))
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?timeline&nonative&shared',
                **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)

        response = c.post('/api/v1/subscription/people/?subscriber=tester', {
            'target': 'tester3'}, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/v1/entry/?timeline&nonative&shared',
                **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 1)

        response = c.get('/api/v1/entry/?timeline&shared&author=tester2',
                **self.getExtras())
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)['objects']
        self.assertEqual(len(reply), 0)
