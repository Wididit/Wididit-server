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
import textwrap

from django.db import models
from django.contrib import admin
from django import forms
from django.forms.forms import BoundField
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User, AnonymousUser
from django.dispatch import Signal
from django.core.signals import request_finished
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils.html import conditional_escape
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe

from wididit import constants, utils

from wididitserver.utils import settings
from wididitserver.fields import EntryField, PeopleField, TagField


##########################################################################
# Utils

class Atomizable:
    """Parent class for all models compatible with the Atom protocol."""
    pass

_username_regexp = re.compile(constants.USERNAME_REGEXP)
def validate_username(value):
    if not _username_regexp.match(value):
        raise ValidationError(u'%s is not a valid username.' % value)

def get_server(hostname=None):
    if hostname is None:
        hostname = settings.WIDIDIT_HOSTNAME
    return Server.objects.get(hostname=hostname)

def get_people(userid):
    username, servername = utils.userid2tuple(userid,
            settings.WIDIDIT_HOSTNAME)
    server = get_server(servername)
    return People.objects.get(username=username, server=server)

class WididitModelForm(forms.ModelForm):
    """A ModelForm which complies with Wididit web interface."""
    def _html_output(self, normal_row, error_row, row_ender, help_text_html, errors_on_separate_row, errored_field_end=''):
        """Django's original method + errored_field_end attribute."""
        top_errors = self.non_field_errors() # Errors that should be displayed above all fields.
        output, hidden_fields = [], []

        for name, field in self.fields.items():
            html_class_attr = ''
            bf = BoundField(self, field, name)
            bf_errors = self.error_class([conditional_escape(error) for error in bf.errors]) # Escape and cache in local variable.
            if bf.is_hidden:
                if bf_errors:
                    top_errors.extend([u'(Hidden field %s) %s' % (name, force_unicode(e)) for e in bf_errors])
                hidden_fields.append(unicode(bf))
            else:
                css_classes = bf.css_classes()
                if errors_on_separate_row and bf_errors:
                    output.append(error_row % force_unicode(bf_errors))
                    #css_classes += ' notice error'

                # Create a 'class="..."' atribute if the row should have any
                # CSS classes applied.
                if css_classes:
                    html_class_attr = ' class="%s"' % css_classes


                if bf.label:
                    label = conditional_escape(force_unicode(bf.label))
                    # Only add the suffix if the label does not end in
                    # punctuation.
                    if self.label_suffix:
                        if label[-1] not in ':?.!':
                            label += self.label_suffix
                    label = bf.label_tag(label) or ''
                else:
                    label = ''

                if field.help_text:
                    help_text = help_text_html % force_unicode(field.help_text)
                else:
                    help_text = u''

                output.append(normal_row % {
                    'errors': force_unicode(bf_errors),
                    'label': force_unicode(label),
                    'field': unicode(bf),
                    'help_text': help_text,
                    'html_class_attr': html_class_attr
                })
                if errors_on_separate_row and bf_errors:
                    output.append(errored_field_end)

        if top_errors:
            output.insert(0, error_row % force_unicode(top_errors))

        if hidden_fields: # Insert any hidden fields in the last row.
            str_hidden = u''.join(hidden_fields)
            if output:
                last_row = output[-1]
                # Chop off the trailing row_ender (e.g. '</td></tr>') and
                # insert the hidden fields.
                if not last_row.endswith(row_ender):
                    # This can happen in the as_p() case (and possibly others
                    # that users write): if there are only top errors, we may
                    # not be able to conscript the last row for our purposes,
                    # so insert a new, empty row.
                    last_row = (normal_row % {'errors': '', 'label': '',
                                              'field': '', 'help_text':'',
                                              'html_class_attr': html_class_attr})
                    output.append(last_row)
                output[-1] = last_row[:-len(row_ender)] + str_hidden + row_ender
            else:
                # If there aren't any rows in the output, just append the
                # hidden fields.
                output.append(str_hidden)
        return mark_safe(u'\n'.join(output))

    def as_p(self):
        "Returns this form rendered as HTML <p>s."
        return self._html_output(
            normal_row = u'<p%(html_class_attr)s>%(label)s %(field)s%(help_text)s</p>',
            error_row = u'<div class="notice error">%s',
            row_ender = '</div></p>',
            help_text_html = u' <span class="helptext">%s</span>',
            errors_on_separate_row = True,
            errored_field_end='</div>')


##########################################################################
# Server

class Server(models.Model):
    hostname = models.CharField(max_length=constants.MAX_HOSTNAME_LENGTH,
            default=settings.WIDIDIT_HOSTNAME)
    key = models.TextField(null=True) # Not used for the moment.

    def is_self(self):
        """Returns whether this is this server."""
        return self.hostname == settings.WIDIDIT_HOSTNAME

    def __unicode__(self):
        return self.hostname

class ServerAdmin(admin.ModelAdmin):
    pass
admin.site.register(Server, ServerAdmin)

class ServerForm(WididitModelForm):
    class Meta:
        model = Server
        exclude = ('key',)


##########################################################################
# People

class People(models.Model):
    server = models.ForeignKey(Server,
            help_text='The server to where this people is register.',
            default=get_server)
    username = models.CharField(max_length=constants.MAX_USERNAME_LENGTH,
            validators=[validate_username])
    user = models.OneToOneField(User,
            help_text='If this people is registered on this server, '
            'this is the associated User instance of this people.',
            blank=True, null=True)
    biography = models.TextField(default='', blank=True)

    def is_local(self):
        """Returns whether the people is registered on this server."""
        return self.server.is_self()

    def can_edit(self, user):
        return user.is_staff or user == self.user

    def __unicode__(self):
        return self.userid()

    def userid(self):
        return '%s@%s' % (self.username, self.server)

    class Meta:
        unique_together = ('server', 'username',)

class PeopleAdmin(admin.ModelAdmin):
    pass
admin.site.register(People, PeopleAdmin)

class PeopleForm(WididitModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    email = forms.EmailField(required=False)

    def save(self, commit=True, *args, **kwargs):
        data = self.cleaned_data
        if self.instance is None:
            people = super(PeopleForm, self).save(commit=commit, *args, **kwargs)
        else:
            people = self.instance
        if people.is_local():
            if people.user is None:
                user = User.objects.create_user(data['username'], data['email'],
                        data['password'])
                user.save()
                people.user = user
            else:
                if data['password'] != '':
                    people.user.set_password(data['password'])
                if data['email'] != '':
                    people.user.email = data['email']
                people.user.save()
        if commit:
            people.save()
        return people

    class Meta:
        model = People
        exclude = ('user', 'server',)

PeopleForm.base_fields.keyOrder = ['username', 'password', 'email', 'biography']


##########################################################################
# Tag

class TagManager(models.Manager):
    def get_or_create_from_path(self, path):
        """Get a Tag from its path."""
        current_tag = None
        for tag_name in path.split('#'):
            if tag_name == '':
                continue
            try:
                current_tag = self.get(name=tag_name, parent=current_tag)
            except Tag.DoesNotExist:
                current_tag = Tag(name=tag_name, parent=current_tag)
                current_tag.save()
        return current_tag

class Tag(models.Model):
    name = models.CharField(max_length=constants.MAX_TAG_LENGTH)
    parent = models.ForeignKey('self', null=True, blank=True)

    objects = TagManager()

    def belongs_to(self, other):
        if self is other:
            return True
        elif self.parent is None:
            return False
        else:
            return self.parent.belongs_to(other)

    def __unicode__(self):
        if self.parent is None:
            return '#' + self.name
        else:
            return u''.join(self.parent, self.name)

    class Meta:
        unique_together = ('name', 'parent',)

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
    #category = models.ForeignKey(Category, blank=True, null=True)
    category = models.TextField(default='', blank=True)
    contributors = models.ManyToManyField(People, related_name='contributors',
            null=True, blank=True)
    generator = models.CharField(max_length=constants.MAX_GENERATOR_LENGTH,
            help_text='Client used to post this entry.', blank=True)
    published = models.DateTimeField(auto_now_add=True)
    rights = models.TextField(blank=True)
    #source = models.ForeignKey('self', null=True, blank=True,
    #        related_name='entry_source')
    source = models.TextField(default='', blank=True)
    subtitle = models.CharField(max_length=constants.MAX_SUBTITLE_LENGTH,
            null=True, blank=True)
    title = models.CharField(max_length=constants.MAX_TITLE_LENGTH)
    updated = models.DateTimeField(auto_now=True)

    def summary(self):
        if len(self.content) <= 500:
            return self.content
        else:
            return textwrap.wrap(self.content, 1000, replace_whitespace=False)[0] + '...'

    # Fields specified in RFC 4685 (Atom Threading Extensions)
    in_reply_to = models.ForeignKey('self', null=True, blank=True,
            related_name='entry_in-reply-to')

    # Extra fields:
    tags = models.ManyToManyField(Tag, related_name='tags',
            null=True, blank=True)

    def save(self, *args, **kwargs):
        # Prevent ValueError: 'Entry' instance needs to have a primary key
        # value before a many-to-many relationship can be used.
        super(Entry, self).save(*args, **kwargs)

        self.contributors = []
        if hasattr(self, '_contributors'):
            for people in self._contributors:
                self.contributors.add(people)

        tags = utils.get_tags(self.content)
        self.tags = [Tag.objects.get_or_create_from_path(x) for x in tags]
        super(Entry, self).save(*args, **kwargs)

    def can_edit(self, people):
        if people == self.author:
            return True
        else:
            return people in self.contributors.all()

    def add_contributor(self, people):
        try:
            self.contributors.add(people)
        except ValueError:
            # ValueError: 'Entry' instance needs to have a primary key
            # value before a many-to-many relationship can be used.
            if not hasattr(self, '_contributors'):
                self._contributors = []
            self._contributors.append(people)

    def can_delete(self, people):
        return people == self.author

    def __unicode__(self):
        return '%s/%s' % (self.author, self.id2)

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
                'fields': ('title', 'subtitle', 'author', 'contributors')
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

class EntryForm(WididitModelForm):
    def __init__(self, data, *args, **kwargs):
        if 'contributors' in data:
            self._contributors = data['contributors'].split()
            del data['contributors']
        super(EntryForm, self).__init__(data, *args, **kwargs)

    def save(self, commit=True, *args, **kwargs):
        self.fields['contributors'].required = False
        entry = super(EntryForm, self).save(commit=False, *args, **kwargs)
        self.fields['contributors'].required = True
        if hasattr(self, '_contributors'):
            for userid in self._contributors:
                entry.add_contributor(get_people(userid))
        if commit:
            entry.save()
        return entry

    class Meta:
        model = Entry
        exclude = ('id2', 'author', 'published', 'updated')



##########################################################################
# Subscription

class Subscription(models.Model):
    subscriber = models.ForeignKey(People, related_name='%(class)s_subscriber')

    tag_blacklist = models.TextField(default='', blank=True)

    class Meta:
        abstract = True

class SubscriptionForm(WididitModelForm):
    pass

class PeopleSubscription(Subscription):
    target_people = models.ForeignKey(People, related_name='target_people')

    tag_whitelist = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('subscriber', 'target_people')

class PeopleSubscriptionForm(SubscriptionForm):
    target_people = PeopleField(People)

    class Meta:
        model = PeopleSubscription
        exclude = ('subscriber',)


##########################################################################
# Share

class Share(models.Model):
    entry = models.ForeignKey(Entry)
    people = models.ForeignKey(People)
    timestamp = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s by %s' % (self.entry, self.people)

    class Meta:
        unique_together = ('entry', 'people',)

class ShareForm(WididitModelForm):
    entry = EntryField(Entry)

    class Meta:
        model = Share
        exclude = ('people', 'timestamp',)
