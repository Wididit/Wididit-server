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

from piston.authentication import OAuthAuthentication
from piston.models import Consumer, Token
from piston.utils import rc
from piston.resource import Resource

class CsrfExemptResource(Resource):
    """A Custom Resource that is csrf exempt"""
    def __init__(self, handler, authentication=None):
        super(CsrfExemptResource, self).__init__(handler, authentication)
        self.csrf_exempt = getattr(self.handler, 'csrf_exempt', True)

class StrictOAuthAuthentication(OAuthAuthentication):
    def challenge(self, *args, **kwargs):
        return rc.FORBIDDEN

class ConsumerForm(forms.ModelForm):
    class Meta:
        model = Consumer
        fields = ('name', 'description',)

class TokenForm(forms.ModelForm):
    class Meta:
        model = Token
        fields = ('consumer',)
