from django.conf.urls.defaults import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'wididit_server.views.home', name='home'),
    # url(r'^wididit_server/', include('wididit_server.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    url(r'', include('wididitserver.urls')),
    (r'^static/admin/(?P<path>.*)$', 'django.views.static.serve',
                {'document_root': '/usr/lib/python2.7/dist-packages/django/contrib/admin/media/',
                    'show_indexes': True}),
)
