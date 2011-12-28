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

import settings

##########################################################################
# Initialize settings
if not hasattr(settings, 'WIDIDIT_HOSTNAME'):
    raise Exception('You must configure WIDIDIT_HOSTNAME in settings.py')

##########################################################################
# Model utils

# This function comes from haystack
def auto_query(query, query_string):
    """
    Performs a best guess constructing the search query.

    This method is somewhat naive but works well enough for the simple,
    common cases.
    """
    clone = query

    # Pull out anything wrapped in quotes and do an exact match on it.
    open_quote_position = None
    non_exact_query = query_string

    for offset, char in enumerate(query_string):
        if char == '"':
            if open_quote_position != None:
                current_match = non_exact_query[open_quote_position + 1:offset]

                if current_match:
                    clone = clone.filter(content__contains=current_match)

                non_exact_query = non_exact_query.replace('"%s"' % current_match, '', 1)
                open_quote_position = None
            else:
                open_quote_position = offset

    # Pseudo-tokenize the rest of the query.
    keywords = non_exact_query.split()

    # Loop through keywords and add filters to the query.
    for keyword in keywords:
        exclude = False

        if keyword.startswith('-') and len(keyword) > 1:
            keyword = keyword[1:]
            exclude = True

        cleaned_keyword = clone.query.clean(keyword)

        if exclude:
            clone = clone.exclude(content=cleaned_keyword)
        else:
            clone = clone.filter(content=cleaned_keyword)

    return clone
