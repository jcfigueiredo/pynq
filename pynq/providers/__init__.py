#!/usr/bin/env python
# -*- coding:utf-8 -*-

# Licensed under the Open Software License ("OSL") v. 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.opensource.org/licenses/osl-3.0.php

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import operator
import sys
from os.path import dirname, abspath, join
root_path = abspath(join(dirname(__file__), "../../"))
sys.path.insert(0, root_path)

from pynq.enums import Actions
from pynq.guard import Guard
from pynq.expressions import NameExpression, UnaryExpression
from pynq.providers.partition_algorithm import EquivalenceClassSetPartition

class IPynqProvider(object):
    def parse(self, query):
        pass

class CollectionProvider(IPynqProvider):
    def __init__(self, collection):
        self.collection = collection

    def compare_items(self, a, b):
        expression = None
        for order_expression in self.order_expressions:
            is_negate_expression = isinstance(order_expression, UnaryExpression) and \
                                   order_expression.node_type == UnaryExpression.Negate

            modifier = 1
            curr_expr = order_expression
            if is_negate_expression:
                modifier = -1
                curr_expr = order_expression.rhs

            if isinstance(curr_expr, NameExpression):
                field_name = curr_expr.name
                result = cmp(modifier * getattr(a, field_name), modifier * getattr(b, field_name))
            else:
                item = a
                val1 = eval(str(curr_expr))
                item = b
                val2 = eval(str(curr_expr))
                result = cmp(modifier * val1, modifier * val2)

            expression = expression is None and result or (expression or result)

        return expression

    def parse(self, query, action, **kwargs):
        if action == Actions.SelectMany:
            return self.parse_select_many(query)
        elif action == Actions.Select:
            return self.parse_select(query, kwargs["cols"])
        elif action == Actions.Count:
            return self.parse_count(query)
        elif action == Actions.Max:
            return self.parse_max(query, kwargs["column"])
        elif action == Actions.Min:
            return self.parse_min(query, kwargs["column"])
        elif action == Actions.Sum:
            return self.parse_sum(query, kwargs["column"])
        elif action == Actions.Avg:
            return self.parse_avg(query, kwargs["column"])
        else:
            raise ValueError("Invalid action exception. %s is unknown." % action)

    def __group_collection(self, collection, group_expression):
        if isinstance(group_expression, NameExpression):
            expr_name = group_expression.name
            if "." in expr_name:
                rel = lambda item: reduce(getattr, expr_name, item)
            else:
                rel = lambda item: getattr(item, expr_name)
        else:
            rel = lambda item: eval(str(query.group_expression))

        return EquivalenceClassSetPartition.partition(collection, rel)

    def __select_items_for(self, query):
        processed_collection = list(self.collection)
        for expression in query.expressions:
            klass = BinaryExpressionProcessor()
            processed_collection = klass.process(processed_collection, expression)

        if query.order_expressions:
            self.order_expressions = query.order_expressions
            processed_collection.sort(self.compare_items)
        return processed_collection

    def parse_select_many(self, query):
        col = self.__select_items_for(query)

        group_expression = query.group_expression
        if group_expression:
            col = self.__group_collection(col, group_expression)

        return col

    def parse_select(self, query, cols):
        columns = [query.parser.parse(col) for col in cols]
        col = self.transform_collection(self.__select_items_for(query), columns)

        group_expression = query.group_expression
        if group_expression:
            col = self.__group_collection(col, group_expression)

        return col

    def parse_count(self, query):
        return len(self.parse_select_many(query))

    def parse_max(self, query, column):
        return self.__perform_operation_on_all(query, column, lambda items: max(items), "max")

    def parse_min(self, query, column):
        return self.__perform_operation_on_all(query, column, lambda items: min(items), "min")

    def parse_sum(self, query, column):
        return self.__perform_operation_on_all(query, column, lambda items: sum(items), "sum")

    def __perform_operation_on_all(self, query, column, operation, command_name):
        seq = self.parse_select_many(query)

        if len(seq) == 0:
            return 0

        error_message = "The attribute '%s' was not found in the specified collection's items. If you meant to use the raw value of each item in the collection just use the word 'item' as a parameter to .%s or use .%s()" % (column, command_name, command_name)

        Guard.against_empty(column, error_message)

        attribute = column.replace("item.","")
        if "item." in column:
            try:
                seq = [self.rec_getattr(item, attribute) for item in seq]
            except AttributeError:
                raise ValueError(error_message)
        else:
            if attribute.lower() != "item":
                raise ValueError(error_message)

        return operation(seq)

    def parse_avg(self, query, column):
        seq = self.parse_select_many(query)

        if len(seq) == 0:
            return 0

        error_message = "The attribute '%s' was not found in the specified collection's items. If you meant to use the raw value of each item in the collection just use the word 'item' as a parameter to .avg or use .avg()" % column

        Guard.against_empty(column, error_message)

        attribute = column.replace("item.","")

        if "item." in column:
            try:
                seq = [self.rec_getattr(item, attribute) for item in seq]
            except AttributeError:
                raise ValueError(error_message)
        else:
            if attribute.lower() != "item":
                raise ValueError(error_message)
            
        return reduce(operator.add,seq)/len(seq)
       
    def rec_getattr(self, obj, attr):
        return reduce(getattr, attr.split('.'), obj)

    def transform_collection(self, col, cols):
        dynamic_item = type('DynamicItem', (object,), {})

        items = []
        app = items.append
        for item in col:
            field_count = 0
            new_item = dynamic_item()
            for field in cols:
                if isinstance(field, NameExpression):
                    field_name = field.name
                    setattr(new_item, field_name, getattr(item, field_name))
                else:
                    setattr(new_item, "dynamic_%d" % field_count, eval(str(field)))
                field_count += 1
            app(new_item)

        return items
#######################################################
class DictionaryProvider(IPynqProvider):
    def __init__(self, dic):
        self.dic = dic
        self.col = self.__convert_dict(dic)

    def __convert_dict(self, dic):
        items = []
        for key, value in dic.iteritems():
            kvp = KeyValuePair(key, value)
            items.append(kvp)
        return items

    def parse(self, query, action, **kwargs):
        collection_provider = CollectionProvider(self.col)
        result = collection_provider.parse(query, action, **kwargs)
        return dict([(item.key, item.value) for item in result])

class KeyValuePair (object):

    def __init__(self, key, value):
        self.key = key
        self.value = value


class BinaryExpressionProcessor(object):
    @classmethod
    def process(cls, iterator, expression):
        filters = str(expression)
        return [item for item in iterator if eval(filters)]
