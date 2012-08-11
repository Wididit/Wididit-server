from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns('',
    # API
    url(r'^api/',
        include('wididitserver.api')),

    # Web interface
    url(r'^web/', include('wididitserver.views', namespace='web')),
)

