import haystack
from haystack import site

from wididitserver import models


haystack.autodiscover()

site.register(models.Entry)
