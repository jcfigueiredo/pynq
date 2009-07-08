#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Licensed under the Open Software License ("OSL") v. 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.opensource.org/licenses/osl-3.0.php

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import sys
import re
from os.path import dirname, abspath, join
root_path = abspath(join(dirname(__file__), "../../"))
sys.path.insert(0, root_path)

from pynq.providers import DictionaryProvider
from pynq.enums import Actions
from pynq import From
from base import BaseUnitTest

class TestDictionaryProvider(BaseUnitTest):

    def test_querying_with_invalid_action_raises(self):
        error = "Invalid action exception. invalid_action is unknown."
        q = From({'one':'one','two':'two','three':'three'})
        provider = q.provider
        self.assertRaisesEx(ValueError, provider.parse, q, "invalid_action", exc_pattern=re.compile(error))

    def test_dictionary_provider_parses_query_and_returns_dict(self):
        dct = {'one':'one','two':'two'}
        query = From(dct).where("item.value == 'two'")
        provider = query.provider
        assert isinstance(provider.parse(query, Actions.SelectMany), dict)
        
    def test_dictionary_provider_filters_using_binary_expression(self):
        dct = {'one':'one','two':'two'}
        query = From(dct).where("item.value == 'two'")
        provider = query.provider
        result = provider.parse(query, Actions.SelectMany)
        assert result == {'two':'two'}, "The dictionary was not filtered properly and now is: %s" % result

    def test_dictionary_provider_filters_using_binary_expression_for_numbers(self):
        dct = {'one':1,'two':2,'eleven':11,'twelve':12}
        query = From(dct).where("item.value > 10")
        provider = query.provider
        result = provider.parse(query, Actions.SelectMany)
        assert result == {'eleven':11,'twelve':12}, "The dictionary was not filtered properly and now is: %s" % result

    def test_dictionary_provider_parses_query_using_lesser_than(self):
        dct = {'one':1,'two':2,'eleven':11,'twelve':12}
        query = From(dct).where("item.value <= 3")
        provider = query.provider
        result = provider.parse(query, Actions.SelectMany)
        assert result == {'one':1,'two':2}, "The dictionary was not filtered properly and now is: %s" % result

if __name__ == '__main__':
    unittest.main()
