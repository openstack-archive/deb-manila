# Copyright (c) 2016 Red Hat, Inc.
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

import ddt

from manila.api.openstack import api_version_request as api_version
from manila.api.views import share_accesses
from manila import test
from manila.tests.api import fakes


@ddt.ddt
class ViewBuilderTestCase(test.TestCase):

    def setUp(self):
        super(ViewBuilderTestCase, self).setUp()
        self.builder = share_accesses.ViewBuilder()
        self.fake_access = {
            'id': 'fakeaccessid',
            'share_id': 'fakeshareid',
            'access_level': 'fakeaccesslevel',
            'access_to': 'fakeacccessto',
            'access_type': 'fakeaccesstype',
            'state': 'fakeaccessstate',
            'access_key': 'fakeaccesskey',
        }

    def test_collection_name(self):
        self.assertEqual('share_accesses', self.builder._collection_name)

    @ddt.data("2.20", "2.21")
    def test_view(self, version):
        req = fakes.HTTPRequest.blank('/shares', version=version)

        result = self.builder.view(req, self.fake_access)

        if (api_version.APIVersionRequest(version) <
                api_version.APIVersionRequest("2.21")):
            del self.fake_access['access_key']

        self.assertEqual({'access': self.fake_access}, result)

    @ddt.data("2.20", "2.21")
    def test_summary_view(self, version):
        req = fakes.HTTPRequest.blank('/shares', version=version)

        result = self.builder.summary_view(req, self.fake_access)

        if (api_version.APIVersionRequest(version) <
                api_version.APIVersionRequest("2.21")):
            del self.fake_access['access_key']
        del self.fake_access['share_id']

        self.assertEqual({'access': self.fake_access}, result)

    @ddt.data("2.20", "2.21")
    def test_list_view(self, version):
        req = fakes.HTTPRequest.blank('/shares', version=version)
        accesses = [self.fake_access, ]

        result = self.builder.list_view(req, accesses)

        if (api_version.APIVersionRequest(version) <
                api_version.APIVersionRequest("2.21")):
            del self.fake_access['access_key']
        del self.fake_access['share_id']

        self.assertEqual({'access_list': accesses}, result)
