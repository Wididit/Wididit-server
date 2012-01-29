from django.conf.urls.defaults import patterns, include, url
from django.shortcuts import render_to_response
from django.template import RequestContext

import settings
from wididit import constants

def context_processor(request):
    return {
            'SERVER_HOSTNAME': settings.WIDIDIT_HOSTNAME,
            'SERVER_NAME': settings.WIDIDIT_SERVERNAME,
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
        })
    return render_to_response('wididitserver/index.html', c)

def show_people(request, userid):
    c = RequestContext(request, {
            'people': api_request(request, 'People', userid=userid),
            'entries': api_request(request, 'Entry', userid=userid),
        })
    return render_to_response('wididitserver/people.html', c)

urlpatterns = patterns('',
        url(r'^$', index, name='index'),
        url(r'^people/(?P<userid>%s)/$' % constants.USERID_MIX_REGEXP, show_people, name='people'),
)
