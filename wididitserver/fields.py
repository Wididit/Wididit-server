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

from django import forms
from django.db import models

class PeopleField(forms.ModelChoiceField):
    def to_python(self, value):
        from wididitserver.models import get_people
        return get_people(value)

class TagField(forms.ModelChoiceField):
    def to_python(self, value):
        from wididitserver.models import Tag
        return Tag.objects.get_or_create_from_path(value)

class EntryField(forms.ModelChoiceField):
    def validate(self, value):
        from wididitserver.models import Entry
        if isinstance(value, Entry):
            return
        if not isinstance(value, unicode):
            raise forms.ValidationError(value.__class__)
        splitted = value.split('/')
        if len(splitted) != 2:
            raise forms.ValidationError('An entry field must be in the '
                    'format <userid>/<entryid>')
    def to_python(self, value):
        from wididitserver.models import Entry, get_people
        if isinstance(value, Entry):
            return value
        splitted = value.split('/')
        userid, entryid = splitted
        try:
            return Entry.objects.get(author=get_people(userid), id2=entryid)
        except Entry.DoesNotExist:
            raise forms.ValidationError('This entry does not exist.')
