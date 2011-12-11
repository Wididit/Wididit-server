from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('',
    url(r'^api/(?P<emitter_format>[^/]+)/', include('wididitserver.api')),
)

