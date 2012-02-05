from django.conf.urls.defaults import patterns, include, url
from django.contrib.auth import authenticate, login, logout
from django.utils.translation import ugettext as _
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.db import IntegrityError
from django import forms

import settings
from wididit import constants
from wididitserver.models import validate_username, models
from wididitserver.models import PeopleForm, EntryForm
from wididitserver.models import People

def error(request, title, message):
    c = RequestContext(request, {
            'title': title,
            'message': message,
        })
    return render_to_response('wididitserver/error.html', c)

def success(request, title, message):
    c = RequestContext(request, {
            'title': title,
            'message': message,
        })
    return render_to_response('wididitserver/success.html', c)

def context_processor(request):
    try:
        people = People.objects.get(user=request.user.pk)
    except:
        people = None
    return {
            'PEOPLE': people,
            'SERVER_HOSTNAME': settings.WIDIDIT_HOSTNAME,
            'SERVER_NAME': settings.WIDIDIT_SERVERNAME,
            'request': request,
        }

def api_handler(request, handler, mode=None):
    """Returns the handler from the API."""
    from wididitserver import api
    handler = getattr(api, handler + 'Handler')
    if not request.user.is_authenticated():
        handler = handler.anonymous
    handler = handler()
    if mode:
        handler = getattr(handler, mode)
    return handler
def api_request(request, handler, mode='read', **kwargs):
    handler = api_handler(request, handler, mode)
    return handler(request, **kwargs)

def index(request):
    c = RequestContext(request, {
            'entries': api_request(request, 'Entry'),
            'post_form' : EntryForm(),
        })
    return render_to_response('wididitserver/index.html', c)

def show_people(request, userid):
    c = RequestContext(request, {
            'people': api_request(request, 'People', userid=userid),
            'entries': api_request(request, 'Entry', userid=userid),
        })
    return render_to_response('wididitserver/people.html', c)

class ConnectionForm(PeopleForm):
    email = None
    biography = None
    password2 = None

def connect(request):
    if request.user.is_authenticated():
        logout(request)
    if request.method == 'POST':
        form = ConnectionForm(request.POST)
        if form.is_valid() and 'username' in form.cleaned_data and \
                'password' in form.cleaned_data:
            user = authenticate(username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'])
            if user is not None:
                if user.is_active:
                    login(request, user)
                    return success(request, _('Logged in'),
                        _('You have been successfully logged in.'))
                else:
                    return error(request, _('Disabled account'),
                        _('Your account has been disabled. Contact an '
                            'administrator for more information.'))
            else:
                return error(request, _('Invalid username/password'),
                    _('The username and/or the password you gave is '
                        'invalid. Try again.'))
        else:
            return error(request, _('Invalid form'),
                    _('You submitted an invalid form. Please try again.'))
    else:
        c = RequestContext(request, {
            })
        return render_to_response('wididitserver/connection_form.html', c)

def disconnect(request):
    logout(request)
    return success(request, _('Logged out'),
        _('You have been successfully logged out.'))

def register(request):
    if request.user.is_authenticated():
        logout(request)
    if request.method == 'POST':
        form = PeopleForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['password']!=form.cleaned_data['password2']:
                form.errors.update({'password2':
                    _('You did not give the same password.')})
            else:
                try:
                    people = form.save()
                    user = authenticate(username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])
                    login(request, user)
                    return success(request, _('Registration'),
                        _('You have successfully registered and you have been '
                            'logged in.'))
                except IntegrityError:
                    form.errors.update({'username':
                        _('This username already exists. Please pick another.'
                            )})
    else:
        form = PeopleForm()
    c = RequestContext(request, {
        'form': form,
        })
    return render_to_response('wididitserver/registration_form.html', c)


def post(request):
    # TODO: implement this
    pass

urlpatterns = patterns('',
        url(r'^$', index, name='index'),
        url(r'^people/(?P<userid>%s)/$' % constants.USERID_MIX_REGEXP, show_people, name='people'),
        url(r'^connect/$', connect, name='connect'),
        url(r'^disconnect/$', disconnect, name='disconnect'),
        url(r'^register/$', register, name='register'),

        url(r'^post/$', post, name='post'),
)
