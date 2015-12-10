# Copyright 2011 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Tests For JsonFilter.
"""

from oslo_context import context
from oslo_serialization import jsonutils

from manila.scheduler.filters import json
from manila import test
from manila.tests.scheduler import fakes


class HostFiltersTestCase(test.TestCase):
    """Test case for JsonFilter."""

    def setUp(self):
        super(HostFiltersTestCase, self).setUp()
        self.context = context.RequestContext('fake', 'fake')
        self.json_query = jsonutils.dumps(
            ['and', ['>=', '$free_ram_mb', 1024],
             ['>=', '$free_disk_mb', 200 * 1024]])
        self.filter = json.JsonFilter()

    def test_json_filter_passes(self):
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': self.json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertTrue(self.filter.host_passes(host, filter_properties))

    def test_json_filter_passes_with_no_query(self):
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 0,
                                    'free_disk_mb': 0,
                                    'capabilities': capabilities})
        self.assertTrue(self.filter.host_passes(host, filter_properties))

    def test_json_filter_fails_on_memory(self):
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': self.json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1023,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

    def test_json_filter_fails_on_disk(self):
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': self.json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': (200 * 1024) - 1,
                                    'capabilities': capabilities})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

    def test_json_filter_fails_on_caps_disabled(self):
        json_query = jsonutils.dumps(
            ['and', ['>=', '$free_ram_mb', 1024],
             ['>=', '$free_disk_mb', 200 * 1024],
             '$capabilities.enabled'])
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'root_gb': 200,
                                               'ephemeral_gb': 0},
                             'scheduler_hints': {'query': json_query}}
        capabilities = {'enabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

    def test_json_filter_fails_on_service_disabled(self):
        json_query = jsonutils.dumps(
            ['and', ['>=', '$free_ram_mb', 1024],
             ['>=', '$free_disk_mb', 200 * 1024],
             ['not', '$service.disabled']])
        filter_properties = {'resource_type': {'memory_mb': 1024,
                                               'local_gb': 200},
                             'scheduler_hints': {'query': json_query}}
        capabilities = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 1024,
                                    'free_disk_mb': 200 * 1024,
                                    'capabilities': capabilities})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

    def test_json_filter_happy_day(self):
        """Test json filter more thoroughly."""
        raw = ['and',
               '$capabilities.enabled',
               ['=', '$capabilities.opt1', 'match'],
               ['or',
                ['and',
                 ['<', '$free_ram_mb', 30],
                 ['<', '$free_disk_mb', 300]],
                ['and',
                 ['>', '$free_ram_mb', 30],
                 ['>', '$free_disk_mb', 300]]]]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }

        # Passes
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 10,
                                    'free_disk_mb': 200,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertTrue(self.filter.host_passes(host, filter_properties))

        # Passes
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 40,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertTrue(self.filter.host_passes(host, filter_properties))

        # Fails due to capabilities being disabled
        capabilities = {'enabled': False, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 40,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

        # Fails due to being exact memory/disk we don't want
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 30,
                                    'free_disk_mb': 300,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

        # Fails due to memory lower but disk higher
        capabilities = {'enabled': True, 'opt1': 'match'}
        service = {'disabled': False}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 20,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

        # Fails due to capabilities 'opt1' not equal
        capabilities = {'enabled': True, 'opt1': 'no-match'}
        service = {'enabled': True}
        host = fakes.FakeHostState('host1',
                                   {'free_ram_mb': 20,
                                    'free_disk_mb': 400,
                                    'capabilities': capabilities,
                                    'service': service})
        self.assertFalse(self.filter.host_passes(host, filter_properties))

    def test_json_filter_basic_operators(self):
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})
        # (operator, arguments, expected_result)
        ops_to_test = [
            ['=', [1, 1], True],
            ['=', [1, 2], False],
            ['<', [1, 2], True],
            ['<', [1, 1], False],
            ['<', [2, 1], False],
            ['>', [2, 1], True],
            ['>', [2, 2], False],
            ['>', [2, 3], False],
            ['<=', [1, 2], True],
            ['<=', [1, 1], True],
            ['<=', [2, 1], False],
            ['>=', [2, 1], True],
            ['>=', [2, 2], True],
            ['>=', [2, 3], False],
            ['in', [1, 1], True],
            ['in', [1, 1, 2, 3], True],
            ['in', [4, 1, 2, 3], False],
            ['not', [True], False],
            ['not', [False], True],
            ['or', [True, False], True],
            ['or', [False, False], False],
            ['and', [True, True], True],
            ['and', [False, False], False],
            ['and', [True, False], False],
            # Nested ((True or False) and (2 > 1)) == Passes
            ['and', [['or', True, False], ['>', 2, 1]], True]]

        for (op, args, expected) in ops_to_test:
            raw = [op] + args
            filter_properties = {
                'scheduler_hints': {
                    'query': jsonutils.dumps(raw),
                },
            }
            self.assertEqual(expected,
                             self.filter.host_passes(host, filter_properties))

        # This results in [False, True, False, True] and if any are True
        # then it passes...
        raw = ['not', True, False, True, False]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(self.filter.host_passes(host, filter_properties))

        # This results in [False, False, False] and if any are True
        # then it passes...which this doesn't
        raw = ['not', True, True, True]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertFalse(self.filter.host_passes(host, filter_properties))

    def test_json_filter_unknown_operator_raises(self):
        raw = ['!=', 1, 2]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})
        self.assertRaises(KeyError,
                          self.filter.host_passes, host, filter_properties)

    def test_json_filter_empty_filters_pass(self):
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})

        raw = []
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(self.filter.host_passes(host, filter_properties))
        raw = {}
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(self.filter.host_passes(host, filter_properties))

    def test_json_filter_invalid_num_arguments_fails(self):
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})

        raw = ['>', ['and', ['or', ['not', ['<', ['>=', ['<=', ['in', ]]]]]]]]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertFalse(self.filter.host_passes(host, filter_properties))

        raw = ['>', 1]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertFalse(self.filter.host_passes(host, filter_properties))

    def test_json_filter_unknown_variable_ignored(self):
        host = fakes.FakeHostState('host1',
                                   {'capabilities': {'enabled': True}})

        raw = ['=', '$........', 1, 1]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(self.filter.host_passes(host, filter_properties))

        raw = ['=', '$foo', 2, 2]
        filter_properties = {
            'scheduler_hints': {
                'query': jsonutils.dumps(raw),
            },
        }
        self.assertTrue(self.filter.host_passes(host, filter_properties))
