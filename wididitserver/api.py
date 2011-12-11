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
from piston.handler import BaseHandler
from piston.resource import Resource
from piston.utils import rc

from wididit import constants

from wididitserver.models import Server, People, Entry, User
from wididitserver.utils import settings


##########################################################################
# Utils

auth = HttpBasicAuthentication(realm='Wididit server')
#auth = OAuthAuthentication(realm='Wididit server')


##########################################################################
# Server

class ServerHandler(BaseHandler):
    allowed_methods = ('GET',)
    model = Server
    fields = ('self', 'hostname',)

    def read(self, request):
        """Returns the list of servers this server is connected to.

        See :ref:`concept-network`.
        """
        return Server.objects.all()

server_handler = Resource(ServerHandler, authentication=auth)


##########################################################################
# People

class PeopleHandler(BaseHandler):
    allowed_methods = ('GET',)
    model = People
    fields = ('username', 'server',)

    def read(self, request, username=None):
        """Returns either a list of all people registered, or the
        user matching the username (wildcard not allowed)."""
        if username is None:
            return People.objects.all()
        else:
            try:
                return People.objects.get(username=username)
            except People.DoesNotExist:
                return rc.NOT_FOUND

people_handler = Resource(PeopleHandler, authentication=auth)


##########################################################################
# Entry

class EntryHandler(BaseHandler):
    allowed_methods = ('GET',)
    model = Entry

    def read(self, request, author=None, id=None):
        """Returns either a list of notices (either from everybody if `author`
        is not given, either from the `author`) or an entry if `author`
        AND `id` are given."""
        if author is not None:
            try:
                author = User.objects.get(username=author)
            except User.DoesNotExist:
                return rc.NOT_FOUND
        if author is None and id is None:
            # FIXME: limit this to a fixed number of results
            return Entry.objects.all()
        elif id is None: # and username is not None
            return Entry.objects.filter(author=author)
        else:
            assert id is not None and author is not None
            try:
                return Entry.objects.get(author=author, id=id)
            except Entry.DoesNotExist:
                return rc.NOT_FOUND

entry_handler = Resource(EntryHandler, authentication=auth)

urlpatterns = patterns('',
    # Piston
    url(r'^oauth/request_token/$',  'piston.authentication.oauth_request_token'),
    url(r'^oauth/authorize/$',      'piston.authentication.oauth_user_auth'),
    url(r'^oauth/access_token/$',   'piston.authentication.oauth_access_token'),

    url(r'^server/$', server_handler, name='wididit:server_list'),
    url(r'^people/$', people_handler, name='wididit:people_list'),
    url(r'^people/(?P<author>%s)/$' % constants.USERNAME_REGEXP, entry_handler, name='wididit:show_people'),
    url(r'^entry/$', entry_handler, name='wididit:entry_list_all'),
    url(r'^entry/(?P<author>%s)/$' % constants.USERNAME_REGEXP, entry_handler, name='wididit:entry_list_author'),
    url(r'^entry/(?P<author>%s)/(?P<id>[0-9]+)/$' % constants.USERNAME_REGEXP, entry_handler, name='wididit:show_entry'),
)

