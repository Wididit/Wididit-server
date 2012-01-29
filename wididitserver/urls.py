from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('',
    # Piston
    url(r'^oauth/request_token/$',  'piston.authentication.oauth_request_token'),
    url(r'^oauth/authorize/$',      'piston.authentication.oauth_user_auth', name='oauth_auth'),
    url(r'^oauth/access_token/$',   'piston.authentication.oauth_access_token'),

    # API
    url(r'^api/(?P<emitter_format>[^/]+)/',
        include('wididitserver.api', namespace='api')),
)

