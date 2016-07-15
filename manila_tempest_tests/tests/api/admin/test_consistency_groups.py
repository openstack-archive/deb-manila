# Copyright 2015 Andrew Kerr
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

from tempest import config
from tempest.lib.common.utils import data_utils
from tempest import test
import testtools

from manila_tempest_tests.tests.api import base

CONF = config.CONF
CG_REQUIRED_ELEMENTS = {"id", "name", "description", "created_at", "status",
                        "share_types", "project_id", "host", "links"}


@testtools.skipUnless(CONF.share.run_consistency_group_tests,
                      'Consistency Group tests disabled.')
class ConsistencyGroupsTest(base.BaseSharesAdminTest):

    @classmethod
    def resource_setup(cls):
        super(ConsistencyGroupsTest, cls).resource_setup()
        # Create 2 share_types
        name = data_utils.rand_name("tempest-manila")
        extra_specs = cls.add_required_extra_specs_to_dict()
        share_type = cls.create_share_type(name, extra_specs=extra_specs)
        cls.share_type = share_type['share_type']

        name = data_utils.rand_name("tempest-manila")
        share_type = cls.create_share_type(name, extra_specs=extra_specs)
        cls.share_type2 = share_type['share_type']

    @test.attr(type=[base.TAG_POSITIVE, base.TAG_API_WITH_BACKEND])
    def test_create_cg_with_multiple_share_types_v2_4(self):
        # Create a consistency group
        consistency_group = self.create_consistency_group(
            cleanup_in_class=False,
            share_type_ids=[self.share_type['id'], self.share_type2['id']],
            version='2.4',
        )

        self.assertTrue(CG_REQUIRED_ELEMENTS.issubset(
            consistency_group.keys()),
            'At least one expected element missing from consistency group '
            'response. Expected %(expected)s, got %(actual)s.' % {
                "expected": CG_REQUIRED_ELEMENTS,
                "actual": consistency_group.keys()})

        actual_share_types = consistency_group['share_types']
        expected_share_types = [self.share_type['id'], self.share_type2['id']]
        self.assertEqual(sorted(expected_share_types),
                         sorted(actual_share_types),
                         'Incorrect share types applied to consistency group '
                         '%s. Expected %s, got %s' % (consistency_group['id'],
                                                      expected_share_types,
                                                      actual_share_types))

    @test.attr(type=[base.TAG_POSITIVE, base.TAG_API_WITH_BACKEND])
    @testtools.skipIf(
        not CONF.share.multitenancy_enabled, "Only for multitenancy.")
    def test_create_cg_from_cgsnapshot_verify_share_server_information(self):
        # Create a consistency group
        orig_consistency_group = self.create_consistency_group(
            cleanup_in_class=False,
            share_type_ids=[self.share_type['id']],
            version='2.4')

        # Get latest CG information
        orig_consistency_group = self.shares_v2_client.get_consistency_group(
            orig_consistency_group['id'], version='2.4')

        # Assert share server information
        self.assertIsNotNone(orig_consistency_group['share_network_id'])
        self.assertIsNotNone(orig_consistency_group['share_server_id'])

        cg_snapshot = self.create_cgsnapshot_wait_for_active(
            orig_consistency_group['id'], cleanup_in_class=False,
            version='2.4')
        new_consistency_group = self.create_consistency_group(
            cleanup_in_class=False, version='2.4',
            source_cgsnapshot_id=cg_snapshot['id'])

        # Assert share server information
        self.assertEqual(orig_consistency_group['share_network_id'],
                         new_consistency_group['share_network_id'])
        self.assertEqual(orig_consistency_group['share_server_id'],
                         new_consistency_group['share_server_id'])
