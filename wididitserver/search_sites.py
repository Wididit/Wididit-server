import haystack
from haystack import site
from haystack import indexes

from wididitserver import models

class EntryIndex(indexes.RealTimeSearchIndex):
    author = indexes.CharField(model_attr='author')
    content = indexes.CharField(document=True, model_attr='content')
    updated = indexes.DateTimeField(model_attr='updated')
    in_reply_to = indexes.CharField(model_attr='in_reply_to', default=None)

site.register(models.Entry, EntryIndex)
