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

class TestEntry(TestCase):
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

    def testPost(self):
        c = Client()

        response = c.post('/api/json/entry/tester/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            })
        self.assertEqual(response.status_code, 401, response.content)
        response = c.post('/api/json/entry/tester/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras('tester2'))
        self.assertEqual(response.status_code, 401, response.content)

        response = c.post('/api/json/entry/tester/', {
            'content': 'This is a test',
            'generator': 'API tests',
            'title': 'test',
            }, **self.getExtras())
        self.assertEqual(response.status_code, 201, response.content)

        response = c.get('/api/json/entry/tester/')
        self.assertEqual(response.status_code, 200, response.content)
        reply = json.loads(response.content)
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply[0]['content'], 'This is a test')
        self.assertEqual(reply[0]['generator'], 'API tests')
        self.assertEqual(reply[0]['title'], 'test')


