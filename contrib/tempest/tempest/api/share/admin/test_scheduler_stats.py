# Copyright (c) 2015 Clinton Knight.  All rights reserved.
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

from tempest_lib import exceptions as lib_exc  # noqa

from tempest.api.share import base
from tempest import config_share as config
from tempest import test

CONF = config.CONF


class SchedulerStatsAdminTest(base.BaseSharesAdminTest):

    @test.attr(type=["gate", "smoke", ])
    def test_pool_list(self):

        # List pools
        pool_response = self.shares_client.list_pools()
        pool_list = pool_response.get('pools')
        self.assertIsNotNone(pool_list, 'No pools returned from pools API')
        self.assertNotEmpty(pool_list)
        pool = pool_list[0]
        required_keys = {'name', 'host', 'backend', 'pool'}
        actual_keys = set(pool.keys())
        self.assertTrue(actual_keys.issuperset(required_keys))

    @test.attr(type=["gate", "smoke", ])
    def test_pool_list_with_filters(self):

        # List pools
        pool_response = self.shares_client.list_pools()
        pool_list = pool_response.get('pools')

        # Ensure we got at least one pool
        self.assertIsNotNone(pool_list, 'No pools returned from pools API')
        self.assertNotEmpty(pool_list)
        pool = pool_list[0]

        # Build search opts from data and get pools again with filter
        search_opts = {
            'host': pool.get('host'),
            'backend': pool.get('backend'),
            'pool': pool.get('pool'),
        }
        pool_response = self.shares_client.list_pools(
            search_opts=search_opts)
        filtered_pool_list = pool_response.get('pools')

        # Ensure we got exactly one pool matching the first one from above
        self.assertEqual(1, len(filtered_pool_list))

        # Match the key values, not the timestamp.
        for k, v in search_opts.items():
            self.assertEqual(v, filtered_pool_list[0][k])

    @test.attr(type=["gate", "smoke", ])
    def test_pool_list_with_filters_negative(self):

        # Build search opts for a non-existent pool
        search_opts = {
            'host': 'foo',
            'backend': 'bar',
            'pool': 'shark',
        }
        pool_response = self.shares_client.list_pools(
            search_opts=search_opts)
        pool_list = pool_response.get('pools')

        # Ensure we got no pools
        self.assertEmpty(pool_list)

    @test.attr(type=["gate", "smoke", ])
    def test_pool_list_detail(self):

        # List pools
        pool_response = self.shares_client.list_pools(detail=True)
        pool_list = pool_response.get('pools')
        self.assertIsNotNone(pool_list, 'No pools returned from pools API')
        self.assertNotEmpty(pool_list)
        pool = pool_list[0]
        required_keys = {'name', 'host', 'backend', 'pool', 'capabilities'}
        actual_keys = set(pool.keys())
        self.assertTrue(actual_keys.issuperset(required_keys))

    @test.attr(type=["gate", "smoke", ])
    def test_pool_list_detail_with_filters(self):

        # List pools
        pool_response = self.shares_client.list_pools(detail=True)
        pool_list = pool_response.get('pools')

        # Ensure we got at least one pool
        self.assertIsNotNone(pool_list, 'No pools returned from pools API')
        self.assertNotEmpty(pool_list)
        pool = pool_list[0]

        # Build search opts from data and get pools again with filter
        search_opts = {
            'host': pool.get('host'),
            'backend': pool.get('backend'),
            'pool': pool.get('pool'),
        }
        pool_response = self.shares_client.list_pools(
            detail=True, search_opts=search_opts)
        filtered_pool_list = pool_response.get('pools')

        # Ensure we got exactly one pool matching the first one from above
        self.assertEqual(1, len(filtered_pool_list))

        # Match the key values, not the timestamp.
        for k, v in search_opts.items():
            self.assertEqual(v, filtered_pool_list[0][k])

    @test.attr(type=["gate", "smoke", ])
    def test_pool_list_detail_with_filters_negative(self):

        # Build search opts for a non-existent pool
        search_opts = {
            'host': 'foo',
            'backend': 'bar',
            'pool': 'shark',
        }
        pool_response = self.shares_client.list_pools(
            detail=True, search_opts=search_opts)
        pool_list = pool_response.get('pools')

        # Ensure we got no pools
        self.assertEmpty(pool_list)
