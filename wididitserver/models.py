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

from django.db import models
from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User, AnonymousUser
from django.dispatch import Signal
from django.core.signals import request_finished
from django.dispatch import receiver
from django.db.models.signals import post_save

from wididit import constants

from wididitserver import utils


##########################################################################
# Utils

class Atomizable:
    """Parent class for all models compatible with the Atom protocol."""
    pass

_username_regexp = re.compile(constants.USERNAME_REGEXP)
def validate_username(value):
    if not _username_regexp.match(value):
        raise ValidationError(u'%s is not a valid username.' % value)


##########################################################################
# Server

class Server(models.Model):
    hostname = models.CharField(max_length=constants.MAX_HOSTNAME_LENGTH,
            default=utils.settings.WIDIDIT_HOSTNAME)
    key = models.TextField(null=True) # Not used for the moment.

    def self(self):
        return self.hostname == utils.settings.WIDIDIT_HOSTNAME

    def __unicode__(self):
        return self.hostname

class ServerAdmin(admin.ModelAdmin):
    pass
admin.site.register(Server, ServerAdmin)

class ServerForm(forms.ModelForm):
    class Meta:
        model = Server
        exclude = ('key',)


##########################################################################
# People

class People(models.Model):
    server = models.ForeignKey(Server,
            help_text='The server to where this people is register.',
            null=True, blank=True)
    username = models.CharField(max_length=constants.MAX_USERNAME_LENGTH,
            validators=[validate_username])
    user = models.OneToOneField(User,
            help_text='If this people is registered on this server, '
            'this is the associated User instance of this people.',
            blank=True, null=True)

    def __unicode__(self):
        return '%s@%s' % (self.username, self.server)

    class Meta:
        unique_together = ('server', 'username',)

class PeopleAdmin(admin.ModelAdmin):
    pass
admin.site.register(People, PeopleAdmin)

class PeopleForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    email = forms.EmailField()
    class Meta:
        model = People
        exclude = ('user',)


##########################################################################
# Tag

class Tag(models.Model):
    name = models.CharField(max_length=constants.MAX_TAG_LENGTH)

class TagAdmin(admin.ModelAdmin):
    pass
admin.site.register(Tag, TagAdmin)


##########################################################################
# Entry

class Entry(models.Model, Atomizable):
    # Fields specified in RFC 4287 (Atom Syndication Format)
    id2 = models.IntegerField(null=True, blank=True)
    content = models.TextField()
    author = models.ForeignKey(People, related_name='author')
    category = models.ForeignKey(Tag, blank=True, null=True)
    contributors = models.ManyToManyField(People, related_name='contributors',
            null=True, blank=True)
    generator = models.CharField(max_length=constants.MAX_GENERATOR_LENGTH,
            help_text='Client used to post this entry.', blank=True)
    published = models.TimeField(auto_now_add=True)
    rights = models.TextField(blank=True)
    source = models.ForeignKey('self', null=True, blank=True)
    subtitle = models.CharField(max_length=constants.MAX_SUBTITLE_LENGTH,
            null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    title = models.CharField(max_length=constants.MAX_TITLE_LENGTH)
    updated = models.TimeField(auto_now=True)

    def __unicode__(self):
        return self.title

    class Meta:
        verbose_name_plural = 'Entries'
        unique_together = ('id2', 'author',)

@receiver(post_save)
def set_entry_id(sender, **kwargs):
    entry = kwargs['instance']
    if not isinstance(entry, Entry) or not kwargs['created']:
        return

    if entry.id2 is not None:
        return
    max_id = Entry.objects\
            .filter(author=entry.author) \
            .order_by('-id2')[0].id2 or 0
    entry.id2 = max_id + 1
    entry.save()

Signal().connect(set_entry_id, Entry)

class EntryAdmin(admin.ModelAdmin):
    fieldsets = (
            ('Head', {
                'fields': ('title', 'author', 'contributors')
            }),
            ('Subtitle & summary', {
                'classes': ('collapse',),
                'fields': ('subtitle', 'summary')
            }),
            ('Metadata', {
                'classes': ('collapse',),
                'fields': ('category', 'generator',
                    'rights', 'source')
            }),
            (None, {
                'fields': ('content',)
            }),
        )
    list_display = ('title', 'author')
admin.site.register(Entry, EntryAdmin)

class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        exclude = ('author', 'contributors', 'published', 'updated')
