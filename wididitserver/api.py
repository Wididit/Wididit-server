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

import re

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.conf.urls.defaults import patterns, include, url
from django.core.context_processors import csrf
from django.core.urlresolvers import reverse
from django import http as djhttp
from django.db import IntegrityError

from piston.authentication import OAuthAuthentication, HttpBasicAuthentication
from piston.handler import BaseHandler, AnonymousBaseHandler
from piston.utils import validate
from piston.utils import rc
from piston.models import Consumer, Token

from tastypie.api import Api
import tastypie.fields as fields
from tastypie.resources import ModelResource, convert_post_to_put
from tastypie.authentication import BasicAuthentication
from tastypie.validation import Validation, FormValidation
from tastypie.exceptions import BadRequest, ImmediateHttpResponse
from tastypie import http
from tastypie.bundle import Bundle
from tastypie.constants import ALL, ALL_WITH_RELATIONS

from wididit import constants
from wididit import utils

from wididitserver.models import Server, People, Entry, User, Share
from wididitserver.models import PeopleSubscription
from wididitserver.models import ServerForm, PeopleForm, EntryForm
from wididitserver.models import PeopleSubscriptionForm, ShareForm
from wididitserver.models import get_server, get_people, get_entry
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

v1_api = Api(api_name='v1')

class WididitAuthentication(BasicAuthentication):
    """Let unauthenticated users perform GET requests."""
    def is_authenticated(self, request, **kwargs):
        authenticated = super(WididitAuthentication, self).is_authenticated(
                    request, **kwargs)
        if request.method == 'GET':
            return True
        elif isinstance(authenticated, djhttp.HttpResponse):
            return authenticated
        elif authenticated:
            assert not request.user.is_anonymous(), request.user
            try:
                People.objects.get(user=request.user)
                return authenticated
            except ObjectDoesNotExist:
                return False
        else:
            return False

class WididitModelResource(ModelResource):
    def dispatch(self, request_type, request, **kwargs):
        """
        Modified version of ModelResource.dispatch, which passes the object
        to is_authorized
        """
        allowed_methods = getattr(self._meta, "%s_allowed_methods" % request_type, None)
        request_method = self.method_check(request, allowed=allowed_methods)

        method = getattr(self, "%s_%s" % (request_method, request_type), None)

        if method is None:
            raise ImmediateHttpResponse(response=http.HttpNotImplemented())

        try:
            obj = self.cached_obj_get(request=request, **self.remove_api_resource_names(kwargs))
        except (ObjectDoesNotExist, MultipleObjectsReturned) as e:
            obj = None

        self.is_authenticated(request)
        self.is_authorized(request, obj)
        self.throttle_check(request)

        # All clear. Process the request.
        request = convert_post_to_put(request)
        response = method(request, **kwargs)

        # Add the throttled request.
        self.log_throttled_access(request)

        # If what comes back isn't a ``HttpResponse``, assume that the
        # request was accepted and that some action occurred. This also
        # prevents Django from freaking out.
        if not isinstance(response, djhttp.HttpResponse):
            return http.HttpNoContent()

        return response

    def full_dehydrate(self, bundle):
        """
        Modified version of tastypie's full_dehydrate that calls
        field_object.dehydrate only if method is None.
        """
        # Dehydrate each field.
        for field_name, field_object in self.fields.items():
            # A touch leaky but it makes URI resolution work.
            if getattr(field_object, 'dehydrated_type', None) == 'related':
                field_object.api_name = self._meta.api_name
                field_object.resource_name = self._meta.resource_name


            # Check for an optional method to do further dehydration.
            method = getattr(self, "dehydrate_%s" % field_name, None)

            if method:
                bundle.data[field_name] = method(bundle)
            else:
                bundle.data[field_name] = field_object.dehydrate(bundle)

        bundle = self.dehydrate(bundle)
        return bundle

    def _build_people_filter(self, filters, field):
        if field in filters:
            list_ = []
            for item in dict.__getitem__(filters, field):
                try:
                    list_.append(get_people(item).pk)
                except ObjectDoesNotExist:
                    pass
            del filters[field]
        else:
            list_ = None

        return list_

##########################################################################
# Server

class ServerResource(ModelResource):
    class Meta:
        resource_name = 'server'
        queryset = Server.objects.all()
        fields = ('self', 'hostname')
        allowed_methods = ('get',)
        authentication = WididitAuthentication()

    def get_resource_uri(self, bundle):
        return reverse('api_dispatch_detail', kwargs={'resource_name': self._meta.resource_name, 'hostname': bundle.obj.hostname, 'api_name': self._meta.api_name})

    def override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<hostname>[^/]+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
            ]
    prepend_urls = override_urls

v1_api.register(ServerResource())

##########################################################################
# People

class PeopleAuthentication(WididitAuthentication):
    def is_authenticated(self, request, **kwargs):
        # Let tastypie process the request
        authenticated = super(PeopleAuthentication, self) \
                .is_authenticated(request, **kwargs)

        if request.method == 'POST':
            return True # Allow registrations
        else:
            return authenticated

class PeopleAuthorization(object):
    def is_authorized(self, request, obj=None):
        if request.method == 'GET':
            return True
        elif request.method == 'POST':
            # FIXME: Forbid creation of remote accounts
            return request.user.is_anonymous()
        elif request.method == 'PATCH':
            if obj is None:
                return False
            try:
                people = People.objects.get(user=request.user)
            except ObjectDoesNotExist:
                return False
            return obj.can_edit(people)
        else:
            raise AssertionError(request.method)

class PeopleValidation(Validation):
    _username_regexp = re.compile(constants.USERNAME_REGEXP)
    def is_valid(self, bundle, request=None):
        assert request is not None
        errors = {}
        if request.method == 'POST':
            required = ('username', 'password', 'email')
        else:
            required = tuple()
        for field in required:
            if field not in bundle.data:
                errors[field] = ['This field is required']
        if 'username' in bundle.data and \
                not self._username_regexp.match(bundle.data['username']):
            errors['username'] = ['This is not a valid username. Valid '
                    'usernames match \"%s\"' % constants.USERNAME_REGEXP]
        return errors

class PeopleResource(WididitModelResource):
    server = fields.ForeignKey(ServerResource, 'server', readonly=True)
    email = fields.CharField()

    def dehydrate_server(self, bundle):
        return bundle.obj.server.hostname
    def remove_api_resource_names(self, kwargs):
        # split userid field.
        if 'userid' in kwargs:
            assert 'username' not in kwargs
            assert 'server' not in kwargs
            people = get_people(kwargs['userid'])
            kwargs['username'] = people.username
            kwargs['server'] = str(people.server.pk)
            del kwargs['userid']
        return super(PeopleResource, self).remove_api_resource_names(kwargs)

    def obj_create(self, bundle, request=None, **kwargs):
        bundle = super(PeopleResource, self).obj_create(bundle, request, **kwargs)
        assert bundle.obj.is_local()
        user = User.objects.create_user(bundle.data['username'], bundle.data['email'],
                bundle.data['password'])
        user.save()
        bundle.obj.user = user
        bundle.obj.save()
        return bundle

    def obj_update(self, bundle, request=None, **kwargs):
        bundle = super(PeopleResource, self).obj_update(bundle, request, **kwargs)
        user = bundle.obj.user
        if 'password' in bundle.data:
            user.set_password(bundle.data['password'])
            user.save()
        return bundle

    class Meta:
        resource_name = 'people'
        queryset = People.objects.all()
        allowed_methods = ('get', 'post', 'patch')
        fields = ('username', 'server', 'biography')
        authentication = PeopleAuthentication()
        authorization = PeopleAuthorization()
        validation = PeopleValidation()
        # TODO: Add throttling for account creation

    def get_resource_uri(self, bundle):
        return reverse('api_dispatch_detail', kwargs={'resource_name': self._meta.resource_name, 'userid': bundle.obj.userid(), 'api_name': self._meta.api_name})

    def override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<userid>[^/]+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
            ]
    prepend_urls = override_urls

v1_api.register(PeopleResource())

##########################################################################
# Subscription

class SubscriptionAuthorization(object):
    def is_authorized(self, request, obj=None):
        if request.method == 'GET':
            return True
        elif request.method == 'POST':
            return not request.user.is_anonymous()
        elif request.method == 'DELETE':
            return (not request.user.is_anonymous() and
                    obj.subscriber.user == request.user)
        else:
            raise AssertionError(request.method)

class PeopleSubscriptionValidation(Validation):
    _username_regexp = re.compile(constants.USERID_MIX_REGEXP)
    def is_valid(self, bundle, request=None):
        assert request is not None
        assert request.method == 'POST'
        if 'target' not in bundle.data:
            return {'target': ['This field is required']}
        if not self._username_regexp.match(bundle.data['target']):
            return {'target': ['This is not a valid userid. Valid '
                    'userids match \"%s\"' % constants.USERID_MIX_REGEXP]}
        try:
            target = get_people(bundle.data['target'])
        except ObjectDoesNotExist:
            return {'target': ['This userid does not exist.']}
        if PeopleSubscription.objects.filter(
                    subscriber=People.objects.get(user=request.user),
                    target_people=target).exists():
            raise ImmediateHttpResponse(response=http.HttpConflict())
        return []

class PeopleSubscriptionResource(WididitModelResource):
    subscriber = fields.ForeignKey(PeopleResource, 'subscriber')
    target = fields.ForeignKey(PeopleResource, 'target_people')
    class Meta:
        resource_name = 'subscription/people'
        object_class = PeopleSubscription
        queryset = PeopleSubscription.objects.all()
        allowed_methods = ('get', 'post', 'delete')
        fields = ('subscriber', 'target')
        authentication = WididitAuthentication()
        authorization = SubscriptionAuthorization()
        validation = PeopleSubscriptionValidation()
        filtering = {
                'subscriber': ALL,
                'target': ALL,
                }

    def build_filters(self, filters=None):
        if filters is None:
            return {}
        subscribers = self._build_people_filter(filters, 'subscriber')
        targets = self._build_people_filter(filters, 'target')

        orm_filters = super(PeopleSubscriptionResource, self).build_filters(filters)

        if subscribers is not None:
            orm_filters['subscriber__in'] = subscribers
        if targets is not None:
            orm_filters['target__in'] = targets
        return orm_filters

    def hydrate_subscriber(self, bundle):
        bundle.obj.subscriber = get_people(bundle.data['subscriber'])
        del bundle.data['subscriber']
        return bundle
    def hydrate_target(self, bundle):
        bundle.obj.target_people = get_people(bundle.data['target'])
        del bundle.data['target']
        return bundle
    def dehydrate_subscriber(self, bundle):
        return bundle.obj.subscriber.userid()
    def dehydrate_target(self, bundle):
        return bundle.obj.target_people.userid()
    def obj_create(self, bundle, request=None, **kwargs):
        assert request is not None
        assert 'subscriber' not in bundle.data
        bundle.data['subscriber'] = People.objects.get(user=request.user).userid()
        return super(PeopleSubscriptionResource, self).obj_create(bundle, request, **kwargs)

v1_api.register(PeopleSubscriptionResource())

##########################################################################
# Entry

class EntryValidation(Validation):
    def is_valid(self, bundle, request=None):
        assert request is not None
        errors = {}
        if request.method == 'POST':
            # author is not required, as a default is assigned in obj_create
            required = ('title', 'content', 'generator')
        else:
            required = tuple()
        for field in required:
            if field not in bundle.data:
                errors[field] = ['This field is required']
        if 'contributors' in bundle.data and \
                not isinstance(bundle.data['contributors'], list):
            errors['contributors'] = ['This field must be a list of strings.']
        return errors

class EntryAuthorization(object):
    def is_authorized(self, request, obj=None):
        if request.method == 'GET':
            if 'timeline' in request.GET:
                return not request.user.is_anonymous()
            else:
                return True
        elif request.method == 'POST':
            return (not request.user.is_anonymous())
        elif request.method == 'PATCH':
            if obj is None:
                return False
            if request.user.is_anonymous():
                return False
            try:
                people = People.objects.get(user=request.user)
            except ObjectDoesNotExist:
                return False
            return obj.can_edit(people)
        elif request.method == 'DELETE':
            return (not request.user.is_anonymous() and
                    obj.author.user == request.user)
        else:
            raise AssertionError(request.method)

class EntryResource(WididitModelResource):
    author = fields.ForeignKey(PeopleResource, 'author')
    contributors = fields.ToManyField(PeopleResource, 'contributors', blank=True)
    in_reply_to = fields.ForeignKey('self', 'in_reply_to')
    class Meta:
        fields = ('id', 'title', 'author', 'contributors',
                'subtitle', 'summary', 'category', 'generator', 'rights',
                'source', 'content', 'in_reply_to', 'shared_by', 'published',
                'updated')
        allowed_methods = ('get', 'post', 'patch', 'delete')
        object_class = Entry
        authentication = WididitAuthentication()
        authorization = EntryAuthorization()
        validation = EntryValidation()
        filtering = {x:ALL for x in ('title', 'author', 'subtitle', 'summary',
            'source', 'content', 'in_reply_to', 'shared_by', 'published',
            'update', 'contributors')}

    def hydrate_in_reply_to(self, bundle):
        if 'in_reply_to' in bundle.data and \
                bundle.data['in_reply_to'] is not None:
            bundle.obj.in_reply_to = get_entry(bundle.data['in_reply_to'])
            del bundle.data['in_reply_to']
        return bundle
    def hydrate_author(self, bundle):
        bundle.obj.author = get_people(bundle.data['author'])
        del bundle.data['author']
        return bundle
    def hydrate_contributors(self, bundle):
        if 'contributors' in bundle.data:
            contributors = []
            for contributor in bundle.data['contributors']:
                if isinstance(contributor, str):
                    contributors.append(reverse('api_dispatch_detail', kwargs={'resource_name': 'people', 'userid': get_people(contributor).userid(), 'api_name': self._meta.api_name}))
                elif isinstance(contributor, Bundle):
                    # WTF?!?!
                    contributors.append(contributor)
                else:
                    raise AssertionError(repr(contributor))
            bundle.data['contributors'] = contributors
        return bundle
    def dehydrate_author(self, bundle):
        return bundle.obj.author.userid()
    def dehydrate_contributors(self, bundle):
        return [x.userid() for x in bundle.obj.contributors.all()]
    def dehydrate_id(self, bundle):
        return bundle.obj.entryid
    def dehydrate_in_reply_to(self, bundle):
        parent = bundle.obj.in_reply_to
        if parent:
            return '%s/%i' % (parent.author.userid(), parent.entryid)
        else:
            return None

    def build_filters(self, filters=None):
        if filters is None:
            return {}
        authors = self._build_people_filter(filters, 'author')
        orm_filters = super(EntryResource, self).build_filters(filters)
        if authors is not None:
            orm_filters['author__in'] = authors

        if 'in_reply_to' in filters:
            orm_filters['in_reply_to__in'] = [get_entry(x)
                for x in dict.__getitem__(filters, 'in_reply_to')]
            del filters['in_reply_to']
            del orm_filters['in_reply_to__exact']
        return orm_filters

    def get_object_list(self, request=None, **kwargs):
        assert request is not None

        # TODO: Move this code to build_filters

        fields = dict(request.GET)
        enable_shared = False
        if 'shared' in fields:
            enable_shared = True
        enable_native = True
        if 'nonative' in fields:
            enable_native = False
        if (enable_shared, enable_native) == (False, False):
            # Why should we query the database for that?
            return Entry.objects.none()

        if request.user.is_anonymous():
            people = None
        else:
            people = People.objects.get(user=request.user)

        query_native = query_shared = Entry.objects.none()

        if 'timeline' in request.GET:
            authors = PeopleSubscription.objects.filter(subscriber=people)
            authors = [x.target_people for x in authors]


        if enable_native:
            query_native = Entry.objects.all()
            if 'timeline' in request.GET:
                query_native = query_native.filter(author__in=authors)
        if enable_shared:
            shares = Share.objects.all()
            if 'timeline' in request.GET:
                shares = shares.filter(by__in=authors)
            entryids = [x.entry.id for x in shares]
            query_shared = Entry.objects.filter(id__in=entryids)

        query = query_native or query_shared

        return query

    def obj_create(self, bundle, request=None, **kwargs):
        assert request is not None
        assert 'author' not in bundle.data
        bundle.data['author'] = People.objects.get(user=request.user).userid()
        return super(EntryResource, self).obj_create(bundle, request, **kwargs)

    def remove_api_resource_names(self, kwargs):
        if 'userid' in kwargs:
            kwargs['author'] = get_people(kwargs['userid'])
            del kwargs['userid']
        return super(EntryResource, self).remove_api_resource_names(kwargs)

    def get_resource_uri(self, bundle):
        return reverse('api_dispatch_detail', kwargs={'resource_name': self._meta.resource_name, 'userid': bundle.obj.author.userid(), 'entryid': bundle.obj.entryid, 'api_name': self._meta.api_name})

    def override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/$" % self._meta.resource_name, self.wrap_view('dispatch_list'), name="api_dispatch_list"),
            url(r"^(?P<resource_name>%s)/(?P<userid>[^/]+)/(?P<entryid>[0-9]+)/$" % self._meta.resource_name, self.wrap_view('dispatch_detail'), name="api_dispatch_detail"),
            ]
    prepend_urls = override_urls

v1_api.register(EntryResource())


##########################################################################
# Share

class ShareAuthorization(object):
    def is_authorized(self, request, obj=None):
        if request.method == 'GET':
            return True
        elif request.method == 'POST':
            return not request.user.is_anonymous()
        elif request.method == 'DELETE':
            return (not request.user.is_anonymous() and
                    obj.by.user == request.user)
        else:
            raise AssertionError(request.method)

class ShareValidation(Validation):
    _entry_regexp = re.compile('%s/[0-9]+' % constants.USERID_MIX_REGEXP)
    def is_valid(self, bundle, request=None):
        assert request is not None
        assert request.method == 'POST'
        if 'entry' not in bundle.data:
            return {'entry': ['This field is required']}
        if not self._entry_regexp.match(bundle.data['entry']):
            return {'entry': ['This is not a valid entry. Valid '
                    'entries match \"%s/[0-9]+\"' % constants.USERID_MIX_REGEXP]}
        try:
            entry = get_entry(bundle.data['entry'])
        except ObjectDoesNotExist:
            return {'entry': ['This entry does not exist.']}
        if Share.objects.filter(
                    by=People.objects.get(user=request.user),
                    entry=entry).exists():
            raise ImmediateHttpResponse(response=http.HttpConflict())
        return []

class ShareResource(WididitModelResource):
    by = fields.ForeignKey(PeopleResource, 'by')
    entry = fields.ForeignKey(EntryResource, 'entry')
    class Meta:
        resource_name = 'share'
        object_class = Share
        queryset = Share.objects.all()
        allowed_methods = ('get', 'post', 'delete')
        fields = ('entry', 'by')
        authentication = WididitAuthentication()
        authorization = ShareAuthorization()
        validation = ShareValidation()
        filtering = {
                'entry': ALL,
                'by': ALL,
                }

    def hydrate_entry(self, bundle):
        bundle.obj.entry = get_entry(bundle.data['entry'])
        del bundle.data['entry']
        return bundle
    def hydrate_by(self, bundle):
        bundle.obj.by = get_people(bundle.data['by'])
        del bundle.data['by']
        return bundle

    def dehydrate_by(self, bundle):
        return bundle.obj.by.userid()
    def dehydrate_entry(self, bundle):
        return '%s/%i' % (bundle.obj.author.userid(), bundle.obj.entryid)

    def obj_create(self, bundle, request=None, **kwargs):
        assert request is not None
        assert 'by' not in bundle.data
        bundle.data['by'] = People.objects.get(user=request.user).userid()
        return super(ShareResource, self).obj_create(bundle, request, **kwargs)

v1_api.register(ShareResource())

urlpatterns = v1_api.urls
