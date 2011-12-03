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

from django.db import models
from django.contrib.auth.models import User

from wididit import constants

class Atomizable:
    """Parent class for all models compatible with the Atom protocol."""
    pass

class Server(models.Model):
    hostname = models.CharField(max_length=constants.MAX_HOSTNAME_LENGTH)

    def __unicode__(self):
        return self.hostname

class People(models.Model):
    server = models.ForeignKey(Server,
            help='The server to where this people is register.')
    username = models.CharField(max_length=constants.MAX_USERNAME_LENGTH)
    user = models.OneToOneField(User,
            help='If this people is registered on this server, '
            'this is the associated User instance of this people.')

class Tag(models.Model):
    name = models.CharField(contents.MAX_TAG_LENGTH)

class Entry(models.Model, Atomizable):
    # Fields specified in RFC 4287 (Atom Syndication Format)
    content = models.TextField()
    author = models.ForeignKey(People)
    category = models.ForeignKey(Tag)
    contributors = models.ManyToManyFields(People)
    generator = models.CharField(max_length=constants.MAX_GENERATOR_LENGTH,
            help='Client used to post this entry.')
    published = models.TimeField()
    rights = models.CharField()
    source = models.ForeignKey(Entry)
    subtitle = models.TextField()
    summary = models.TextField()
    title = models.TextField()
    updated = models.TimeField()
