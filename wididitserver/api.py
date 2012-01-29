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

from wididit import constants
from wididit import utils

from wididitserver.models import Server, People, Entry, User, Share
from wididitserver.models import PeopleSubscription
from wididitserver.models import ServerForm, PeopleForm, EntryForm
from wididitserver.models import PeopleSubscriptionForm, ShareForm
from wididitserver.models import get_server, get_people
from wididitserver.utils import settings
import wididitserver.utils as serverutils
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
    fields = ('username', 'server', 'biography')

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
        people = request.form.save(commit=False)
        # FIXME: if creating a remote user, make sure he exists.
        people.save()

        response = rc.CREATED
        response.content = str(people.userid())
        return response

class PeopleHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT',)
    anonymous = AnonymousPeopleHandler
    model = anonymous.model
    fields = anonymous.fields

    def read(self, request, **kwargs):
        return self.anonymous().read(request, **kwargs)
    def create(self, request, **kwargs):
        return self.anonymous().read(request, **kwargs)

    def update(self, request, userid):
        people = get_people(userid)
        userid = people.userid()
        if not people.is_local():
            return rc.BAD_REQUEST
        if not people.can_edit(request.user):
            return rc.FORBIDDEN
        form = PeopleForm(request.PUT, instance=people)
        if not form.is_valid():
            return rc.BAD_REQUEST
        if userid != people.userid():
            # people.userid() got a new value because of PeopleForm(instance=).
            # We shouldn't allow that!
            return rc.FORBIDDEN
        people = form.save()
        people.save()
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
# Subscription

class AnonymousPeopleSubscriptionHandler(AnonymousBaseHandler):
    allowed_methods = ('GET',)
    model = PeopleSubscription

    def read(self, request, userid, targetid=None):
        subscriber = get_people(userid)
        if targetid is None:
            return PeopleSubscription.objects.filter(subscriber=subscriber)
        else:
            target = get_people(targetid)
            try:
                return PeopleSubscription.objects.get(
                        subscriber=subscriber,
                        target_people=target)
            except PeopleSubscription.DoesNotExist:
                return rc.NOT_FOUND
            except People.DoesNotExist:
                return rc.NOT_FOUND

class PeopleSubscriptionHandler(BaseHandler):
    allowed_methods = ('GET', 'POST',)
    anonymous = AnonymousPeopleSubscriptionHandler
    model = anonymous.model
    fields = anonymous.fields

    def read(self, request, *args, **kwargs):
        return self.anonymous().read(request, *args, **kwargs)

    @validate(PeopleSubscriptionForm, 'POST')
    def create(self, request, userid):
        subscriber = get_people(userid)
        if subscriber.user != request.user:
            return rc.FORBIDDEN
        subs = request.form.save(commit=False)
        subs.subscriber = subscriber
        subs.save()
        return rc.CREATED

people_subscription_handler = Resource(PeopleSubscriptionHandler,
        authentication=auth)


##########################################################################
# Entry

class AnonymousEntryHandler(AnonymousBaseHandler):
    allowed_methods = ('GET',)
    model = Entry
    fields = ('id', 'title', 'author', 'contributors',
            'subtitle', 'summary', 'category', 'generator', 'rights', 'source',
            'content', 'in_reply_to', 'shared_by', 'published', 'updated')

    def read(self, request, mode=None, userid=None, entryid=None):
        """Returns either a list of notices (either from everybody if
        `userid` is not given, either from the `userid`) or an entry if
        `userid` AND `id` are given."""

        # Display a single entry
        if entryid is not None:
            assert userid is not None
            assert mode is None
            if userid is not None:
                try:
                    user = get_people(userid)
                except People.DoesNotExist:
                    return rc.NOT_FOUND
            try:
                return Entry.objects.get(author=user, id2=entryid)
            except Entry.DoesNotExist:
                return rc.NOT_FOUND

        # Display multiple entries
        fields = dict(request.GET)

        enable_shared = False
        if 'shared' in fields:
            enable_shared = True
        enable_native = True
        if 'nonative' in fields:
            enable_native = False
        if (enable_shared, enable_native) == (False, False):
            # Why should we query the database for that?
            return []

        if mode == 'timeline':
            # Display (shared?) entries from people the user subscribed to.

            if request.user is None or request.user.id is None:
                # We need to know who you are.
                return rc.FORBIDDEN
            try:
                people = People.objects.get(user=request.user.id)
            except People.DoesNotExist:
                # Authenticated, but not a people.
                return rc.FORBIDDEN

            query_native = query_shared = Entry.objects.none()

            # The list of people we subscribed to.
            authors = PeopleSubscription.objects.filter(subscriber=people)
            authors = [x.target_people for x in authors]

            if enable_native:
                query_native = Entry.objects.filter(author__in=authors)

            if enable_shared:
                shares = Share.objects.filter(people__in=authors)
                entryids = [x.entry.id for x in shares]
                query_shared = Entry.objects.filter(id__in=entryids)

            # Merge results.
            query = query_native or query_shared
        else:
            if enable_native:
                # Obviously, all shared entries also exist as native
                query = Entry.objects.all()
            else:
                assert enable_shared, 'Run memcheck! enable_native and ' +\
                        'enable_shared weren\'t both False before.'
                entryids = [x.entry.id for x in Share.objects.all()]
                query = Entry.objects.filter(id__in=entryids)

        if 'author' in fields:
            query_native = query_shared = Entry.objects.none()

            authors = []
            for author in fields['author']:
                try:
                    authors.append(get_people(author))
                except People.DoesNotExist:
                    continue
            if enable_native:
                query_native = query.filter(author__in=authors)

            if enable_shared:
                shares = Share.objects.filter(people__in=authors)
                entryids = [x.entry.id for x in shares]
                query_shared = Entry.objects.filter(id__in=entryids)

            query = query_native or query_shared

        if 'tag' in fields:
            for tag in fields['tag'].split():
                tag_obj = Tag.objects.path_get(tag)
                query = query.filter(tags__in=tag_obj)

        if 'content' in fields:
            # Convert `?content=foo%20bar&content=baz` to
            # `"foo bar" "baz"`
            content = ' '.join(['"%s"' % x for x in fields['content']])
            query = serverutils.auto_query(query, content)

        if 'in_reply_to' in fields:
            if len(fields['in_reply_to']) != 1:
                return rc.BAD_REQUEST
            try:
                userid, entryid = fields['in_reply_to'][0].split('/')
                people = get_people(userid)
                entry = Entry.objects.get(author=people, id2=entryid)
            except Entry.DoesNotExist:
                return rc.NOT_FOUND
            except People.DoesNotExist:
                return rc.NOT_FOUND
            query = query.filter(in_reply_to__exact=entry)
            query = query.exclude(in_reply_to=None)

        query = query.order_by('updated')

        return query


    @classmethod
    def id(cls, entry):
        return entry.id2

    @classmethod
    def shared_by(cls, entry):
        return [x.people for x in Share.objects.filter(entry=entry)]

class EntryHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'PUT', 'DELETE')
    anonymous = AnonymousEntryHandler
    model = anonymous.model
    fields = anonymous.fields

    def read(self, request, *args, **kwargs):
        return self.anonymous().read(request, *args, **kwargs)

    @validate(EntryForm, 'POST')
    def create(self, request, userid=None, entryid=None):
        if (userid is None and entryid is not None) or \
                (userid is not None and entryid is None):
            return rc.BAD_REQUEST
        people = People.objects.get(user=request.user)
        if not people.is_local():
            return rc.NOT_IMPLEMENTED
        if not people.can_edit(request.user):
            return rc.FORBIDDEN
        data = request.form.cleaned_data
        entry = request.form.save(commit=False)
        entry.author = people
        if userid is not None:
            assert entryid is not None
            try:
                entry.in_reply_to = Entry.objects.get(author=get_people(userid),
                        id2=entryid)
            except Entry.DoesNotExist:
                return rc.NOT_FOUND
        entry.save()

        response = rc.CREATED
        response.content = str(entry.id)
        return response

    def update(self, request, userid, entryid=None):
        if id is None:
            return rc.BAD_REQUEST
        people = get_people(userid)
        if not people.is_local():
            return rc.NOT_IMPLEMENTED
        try:
            entry = Entry.objects.get(author=people, id2=entryid)
        except Entry.DoesNotExist:
            return rc.NOT_FOUND
        if not entry.can_edit(people):
            return rc.FORBIDDEN
        form = EntryForm(request.PUT, instance=entry)
        form.save()
        return rc.ALL_OK

    def delete(self, request, userid, entryid=None):
        if id is None:
            return rc.BAD_REQUEST
        people = get_people(userid)
        if not people.is_local():
            return rc.NOT_IMPLEMENTED
        if not people.can_edit(request.user):
            return rc.FORBIDDEN
        try:
            entry = Entry.objects.get(author=people, id2=entryid)
        except Entry.DoesNotExist:
            return rc.NOT_FOUND
        entry.delete()
        return rc.DELETED

    id = anonymous.id
    shared_by = anonymous.shared_by

entry_handler = Resource(EntryHandler, authentication=auth)

##########################################################################
# Share

class ShareHandler(BaseHandler):
    allowed_methods = ('POST',)
    model = Share

    @validate(ShareForm, 'POST')
    def create(self, request):
        share = request.form.save(commit=False)
        try:
            share.people = People.objects.get(user=request.user)
        except People.DoesNotExist:
            return rc.FORBIDDEN
        share.save()
        return rc.CREATED

share_handler = Resource(ShareHandler, authentication=auth)

##########################################################################
# Whoami

class WhoamiHandler(BaseHandler):
    allowed_methods = ('GET',)
    model = People
    fields = PeopleHandler.fields

    def read(self, request):
        return People.objects.get(user=request.user)

whoami_handler = Resource(WhoamiHandler, authentication=auth)

urlpatterns = patterns('',
    # Server
    url(r'^server/$', server_handler, name='server_list'),

    # People
    url(r'^people/$', people_handler, name='people_list'),
    url(r'^people/(?P<userid>%s)/$' % constants.USERID_MIX_REGEXP, people_handler, name='people'),

    # Subscription
    url(r'^subscription/(?P<userid>%s)/people/$' % constants.USERID_MIX_REGEXP, people_subscription_handler, name='people_subscriptions_list'),
    url(r'^subscription/(?P<userid>%s)/people/(?P<targetid>%s)/$' % (constants.USERID_MIX_REGEXP, constants.USERID_MIX_REGEXP), people_subscription_handler, name='people_subscription'),

    # Entries
    url(r'^entry/$', entry_handler, name='entry_list_all'),
    url(r'^entry/(?P<mode>timeline)/$', entry_handler, name='entry_timeline'),
    url(r'^entry/(?P<userid>%s)/(?P<entryid>[0-9]+)/$' % constants.USERID_MIX_REGEXP, entry_handler, name='show_entry'),

    # Shares
    url(r'^share/$', share_handler, name='share_index'),

    # Utils
    url(r'^oauth/consumer/$', consumer_handler, name='consumer'),
    url(r'^whoami/$', whoami_handler, name='whoami'),
)

