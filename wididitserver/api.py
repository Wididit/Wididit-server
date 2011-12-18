# Copyright (C) 2011, Valentin Lorentz
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.conf.urls.defaults import patterns, include, url
from django.core.context_processors import csrf
from django.http import HttpResponse

from piston.authentication import OAuthAuthentication, HttpBasicAuthentication
from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import validate
from piston.utils import rc
from piston.models import Consumer, Token

from haystack.query import SearchQuerySet

from wididit import constants
from wididit import utils

from wididitserver.models import Server, People, Entry, User
from wididitserver.models import ServerForm, PeopleForm, EntryForm
from wididitserver.models import get_server, get_people
from wididitserver.utils import settings
from wididitserver.pistonextras import ConsumerForm, TokenForm
from wididitserver.pistonextras import StrictOAuthAuthentication
from wididitserver.pistonextras import CsrfExemptResource as Resource


##########################################################################
# Utils

http_auth = HttpBasicAuthentication(realm='Wididit server')
oauth_auth = OAuthAuthentication(realm='Wididit server')
auth = http_auth

##########################################################################
# Server

class AnonymousServerHandler(AnonymousBaseHandler):
    allowed_methods = ('GET',)
    model = Server
    fields = ('self', 'hostname',)

    def read(self, request):
        """Returns the list of servers this server is connected to.

        See :ref:`concept-network`.
        """
        return Server.objects.all()

class ServerHandler(BaseHandler):
    anonymous = AnonymousServerHandler
    model = anonymous.model
    fields = anonymous.fields

    def read(self, request):
        return self.anonymous().read(request)

server_handler = Resource(ServerHandler, authentication=auth)


##########################################################################
# People

class AnonymousPeopleHandler(AnonymousBaseHandler):
    allowed_methods = ('GET', 'POST',)
    model = People
    fields = ('username', 'server',)

    def read(self, request, userid=None):
        """Returns either a list of all people registered, or the
        user matching the username (wildcard not allowed)."""
        if userid is None:
            return People.objects.all()
        else:
            try:
                return get_people(userid)
            except People.DoesNotExist:
                return rc.NOT_FOUND
            except Server.DoesNotExist:
                return rc.NOT_FOUND

    @validate(PeopleForm, 'POST')
    def create(self, request):
        request.form.save()
        return rc.CREATED

class PeopleHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT',)
    anonymous = AnonymousPeopleHandler
    model = anonymous.model
    fields = anonymous.fields

    def update(self, request, userid):
        people = get_people(userid)
        if not people.is_local():
            return rc.BAD_REQUEST
        if not people.can_edit(request.user):
            return rc.FORBIDDEN
        form = PeopleForm(request.PUT, instance=people)
        for field in form.fields.values():
            field.required = False
        if not form.is_valid():
            return rc.BAD_REQUEST
        if people.username != form.cleaned_data['username']:
            # We don't allow username changes
            return rc.FORBIDDEN
        form.save()
        return rc.ALL_OK

people_handler = Resource(PeopleHandler, authentication=auth)

##########################################################################
# OAuth

class ConsumerHandler(BaseHandler):
    allowed_methods = ('POST',)
    model = Consumer
    fields = ('status', 'name', 'key', 'description', 'secret',)

    @validate(ConsumerForm, 'POST')
    def create(self, request):
        consumer = request.form.save(commit=False)
        consumer.user = request.user
        consumer.generate_random_codes()
        consumer.save()
        return consumer

consumer_handler = Resource(ConsumerHandler, authentication=http_auth)


##########################################################################
# Entry

class AnonymousEntryHandler(AnonymousBaseHandler):
    allowed_methods = ('GET',)
    model = Entry
    fields = ('id', 'title', 'author', 'contributors',
            'subtitle', 'summary', 'category', 'generator', 'rights', 'source',
            'content',)

    def read(self, request, userid=None, id=None):
        """Returns either a list of notices (either from everybody if
        `userid` is not given, either from the `userid`) or an entry if
        `userid` AND `id` are given."""
        if userid is not None:
            try:
                user = get_people(userid)
            except People.DoesNotExist:
                return rc.NOT_FOUND
            except Server.DoesNotExist:
                return rc.NOT_FOUND

        if userid is None and id is None:
            # FIXME: limit this to a fixed number of results
            return Entry.objects.all()
        elif id is None: # and author is not None
            return Entry.objects.filter(author=user)
        else:
            assert id is not None and author is not None
            try:
                return Entry.objects.get(author=user, id=id)
            except Entry.DoesNotExist:
                return rc.NOT_FOUND

    @classmethod
    def id(cls, entry):
        return entry.id2

class EntryHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    anonymous = AnonymousEntryHandler
    model = anonymous.model
    fields = anonymous.fields

    @validate(EntryForm, 'POST')
    def create(self, request, userid):
        people = get_people(userid)
        if not people.is_local():
            return rc.NOT_IMPLEMENTED
        if not people.can_edit(request.user):
            return rc.FORBIDDEN
        data = request.form.cleaned_data
        entry = request.form.save(commit=False)
        entry.author = people
        entry.save()
        return rc.CREATED

    def update(self, request, userid, id=None):
        if id is None:
            return rc.BAD_REQUEST
        people = get_people(userid)
        if not people.is_local():
            return rc.NOT_IMPLEMENTED
        if not people.can_edit(request.user):
            return rc.FORBIDDEN
        try:
            entry = Entry.objects.get(author=people, id=id)
        except Entry.DoesNotExist:
            return rc.NOT_FOUND
        form = EntryForm(request.PUT, instance=entry)
        for field in form.fields.values():
            field.required = False
        form.save()
        return rc.ALL_OK

    def delete(self, request, userid, id=None):
        if id is None:
            return rc.BAD_REQUEST
        people = get_people(userid)
        if not people.is_local():
            return rc.NOT_IMPLEMENTED
        if not people.can_edit(request.user):
            return rc.FORBIDDEN
        try:
            entry = Entry.objects.get(author=people, id=id)
        except Entry.DoesNotExist:
            return rc.NOT_FOUND
        entry.delete()
        return rc.DELETED


entry_handler = Resource(EntryHandler, authentication=auth)

class AnonymousEntrySearchHandler(AnonymousBaseHandler):
    allowed_methods = ('GET',)
    model = Entry
    fields = AnonymousEntryHandler.fields

    def read(self, request):
        fields = dict(request.GET)
        query = SearchQuerySet().models(Entry)
        if 'tag' in fields:
            for tag in fields['tag'].split():
                tag_obj = Tag.objects.path_get(tag)
                query = query.filter(tags__in=tag_obj)
        if 'content' in fields:
            # Convert `?content=foo%20bar&content=baz` to
            # `"foo bar" "baz"`
            content = ' '.join(['"%s"' % x for x in fields['content']])
            query = query.auto_query(content)
        entries = [x.object for x in query]
        if 'author' in fields:
            authors = [get_people(x) for x in fields['author']]
            entries = [x for x in entries
                    if any([x.author == y for y in authors])]
        return entries

class EntrySearchHandler(BaseHandler):
    anonymous = AnonymousEntrySearchHandler
    model = anonymous.model
    fields = EntryHandler.fields

entry_search_handler = Resource(EntrySearchHandler, authentication=auth)

##########################################################################
# Whoami

class WhoamiHandler(BaseHandler):
    allowed_methods = ('GET',)
    model = People
    fields = PeopleHandler.fields

    def read(self, request):
        return request.user

whoami_handler = Resource(WhoamiHandler, authentication=oauth_auth)

urlpatterns = patterns('',
    url(r'^server/$', server_handler, name='wididit:server_list'),
    url(r'^people/$', people_handler, name='wididit:people_list'),
    url(r'^people/(?P<userid>%s)/$' % constants.USERID_MIX_REGEXP, people_handler, name='wididit:show_people'),
    url(r'^entry/$', entry_handler, name='wididit:entry_list_all'),
    url(r'^entry/(?P<userid>%s)/$' % constants.USERID_MIX_REGEXP, entry_handler, name='wididit:entry_list_author'),
    url(r'^entry/(?P<userid>%s)/(?P<id>[0-9]+)/$' % constants.USERID_MIX_REGEXP, entry_handler, name='wididit:show_entry'),
    url(r'^search/entry/$', entry_search_handler, name='wididit:search_entry'),
    url(r'^oauth/consumer/$', consumer_handler, name='wididit:consumer'),
    url(r'^whoami/$', whoami_handler, name='wididit:whoami'),
)

