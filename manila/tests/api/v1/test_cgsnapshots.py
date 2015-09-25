# Copyright 2015 Alex Meade
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

import copy
import datetime
import uuid

import mock
from oslo_config import cfg
import six
import webob

import manila.api.v1.cgsnapshots as cgs
from manila.common import constants
from manila import exception
from manila import test
from manila.tests.api import fakes


CONF = cfg.CONF


class CGSnapshotApiTest(test.TestCase):
    def setUp(self):
        super(CGSnapshotApiTest, self).setUp()
        self.controller = cgs.CGSnapshotController()
        self.api_version = '2.4'
        self.request = fakes.HTTPRequest.blank('/consistency-groups',
                                               version=self.api_version,
                                               experimental=True)

    def _get_fake_cgsnapshot(self, **values):
        snap = {
            'id': 'fake_id',
            'user_id': 'fakeuser',
            'project_id': 'fakeproject',
            'status': constants.STATUS_CREATING,
            'name': None,
            'description': None,
            'consistency_group_id': None,
            'created_at': datetime.datetime(1, 1, 1, 1, 1, 1),
        }

        snap.update(**values)

        expected_snap = copy.deepcopy(snap)
        del expected_snap['user_id']
        expected_snap['links'] = mock.ANY
        return snap, expected_snap

    def _get_fake_simple_cgsnapshot(self, **values):
        snap = {
            'id': 'fake_id',
            'name': None,
        }

        snap.update(**values)
        expected_snap = copy.deepcopy(snap)
        expected_snap['links'] = mock.ANY
        return snap, expected_snap

    def _get_fake_cgsnapshot_member(self, **values):
        member = {
            'id': 'fake_id',
            'user_id': 'fakeuser',
            'project_id': 'fakeproject',
            'status': constants.STATUS_CREATING,
            'cgsnapshot_id': None,
            'share_proto': None,
            'share_type_id': None,
            'share_id': None,
            'size': None,
            'created_at': datetime.datetime(1, 1, 1, 1, 1, 1),
        }

        member.update(**values)

        expected_member = copy.deepcopy(member)
        del expected_member['user_id']
        del expected_member['status']
        expected_member['share_protocol'] = member['share_proto']
        del expected_member['share_proto']
        return member, expected_member

    def test_create_invalid_body(self):
        body = {"not_cg_snapshot": {}}
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          self.request, body)

    def test_create_no_consistency_group_id(self):
        body = {"cgnapshot": {}}
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          self.request, body)

    def test_create(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        fake_id = six.text_type(uuid.uuid4())
        self.mock_object(self.controller.cg_api, 'create_cgsnapshot',
                         mock.Mock(return_value=fake_snap))

        body = {"cgsnapshot": {"consistency_group_id": fake_id}}
        context = self.request.environ['manila.context']
        res_dict = self.controller.create(self.request, body)

        self.controller.cg_api.create_cgsnapshot.assert_called_once_with(
            context, consistency_group_id=fake_id)
        self.assertEqual(expected_snap, res_dict['cgsnapshot'])

    def test_create_cg_does_not_exist(self):
        fake_id = six.text_type(uuid.uuid4())
        self.mock_object(self.controller.cg_api, 'create_cgsnapshot',
                         mock.Mock(
                             side_effect=exception.ConsistencyGroupNotFound(
                                 consistency_group_id=six.text_type(
                                     uuid.uuid4())
                             )))

        body = {"cgsnapshot": {"consistency_group_id": fake_id}}
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          self.request, body)

    def test_create_cg_does_not_a_uuid(self):
        self.mock_object(self.controller.cg_api, 'create_cgsnapshot',
                         mock.Mock(
                             side_effect=exception.ConsistencyGroupNotFound(
                                 consistency_group_id='not_a_uuid'
                             )))

        body = {"cgsnapshot": {"consistency_group_id": "not_a_uuid"}}
        self.assertRaises(webob.exc.HTTPBadRequest, self.controller.create,
                          self.request, body)

    def test_create_invalid_cg(self):
        fake_id = six.text_type(uuid.uuid4())
        self.mock_object(self.controller.cg_api, 'create_cgsnapshot',
                         mock.Mock(
                             side_effect=exception.InvalidConsistencyGroup(
                                 reason='bad_status'
                             )))

        body = {"cgsnapshot": {"consistency_group_id": fake_id}}
        self.assertRaises(webob.exc.HTTPConflict, self.controller.create,
                          self.request, body)

    def test_create_with_name(self):
        fake_name = 'fake_name'
        fake_snap, expected_snap = self._get_fake_cgsnapshot(name=fake_name)
        fake_id = six.text_type(uuid.uuid4())
        self.mock_object(self.controller.cg_api, 'create_cgsnapshot',
                         mock.Mock(return_value=fake_snap))

        body = {"cgsnapshot": {"consistency_group_id": fake_id,
                               "name": fake_name}}
        context = self.request.environ['manila.context']
        res_dict = self.controller.create(self.request, body)

        self.controller.cg_api.create_cgsnapshot.assert_called_once_with(
            context, consistency_group_id=fake_id, name=fake_name)
        self.assertEqual(expected_snap, res_dict['cgsnapshot'])

    def test_create_with_description(self):
        fake_description = 'fake_description'
        fake_snap, expected_snap = self._get_fake_cgsnapshot(
            description=fake_description)
        fake_id = six.text_type(uuid.uuid4())
        self.mock_object(self.controller.cg_api, 'create_cgsnapshot',
                         mock.Mock(return_value=fake_snap))

        body = {"cgsnapshot": {"consistency_group_id": fake_id,
                               "description": fake_description}}
        context = self.request.environ['manila.context']
        res_dict = self.controller.create(self.request, body)

        self.controller.cg_api.create_cgsnapshot.assert_called_once_with(
            context, consistency_group_id=fake_id,
            description=fake_description)
        self.assertEqual(expected_snap, res_dict['cgsnapshot'])

    def test_create_with_name_and_description(self):
        fake_name = 'fake_name'
        fake_description = 'fake_description'
        fake_id = six.text_type(uuid.uuid4())
        fake_snap, expected_snap = self._get_fake_cgsnapshot(
            description=fake_description, name=fake_name)
        self.mock_object(self.controller.cg_api, 'create_cgsnapshot',
                         mock.Mock(return_value=fake_snap))

        body = {"cgsnapshot": {"consistency_group_id": fake_id,
                               "description": fake_description,
                               "name": fake_name}}
        context = self.request.environ['manila.context']
        res_dict = self.controller.create(self.request, body)

        self.controller.cg_api.create_cgsnapshot.assert_called_once_with(
            context, consistency_group_id=fake_id, name=fake_name,
            description=fake_description)
        self.assertEqual(expected_snap, res_dict['cgsnapshot'])

    def test_update_with_name_and_description(self):
        fake_name = 'fake_name'
        fake_description = 'fake_description'
        fake_id = six.text_type(uuid.uuid4())
        fake_snap, expected_snap = self._get_fake_cgsnapshot(
            description=fake_description, name=fake_name)
        self.mock_object(self.controller.cg_api, 'get_cgsnapshot',
                         mock.Mock(return_value=fake_snap))
        self.mock_object(self.controller.cg_api, 'update_cgsnapshot',
                         mock.Mock(return_value=fake_snap))

        body = {"cgsnapshot": {"description": fake_description,
                               "name": fake_name}}
        context = self.request.environ['manila.context']
        res_dict = self.controller.update(self.request, fake_id, body)

        self.controller.cg_api.update_cgsnapshot.assert_called_once_with(
            context, fake_snap,
            dict(name=fake_name, description=fake_description))
        self.assertEqual(expected_snap, res_dict['cgsnapshot'])

    def test_update_snapshot_not_found(self):
        body = {"cgsnapshot": {}}
        self.mock_object(self.controller.cg_api, 'get_cgsnapshot',
                         mock.Mock(side_effect=exception.NotFound))
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.update,
                          self.request, 'fake_id', body)

    def test_update_invalid_body(self):
        body = {"not_cgsnapshot": {}}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update,
                          self.request, 'fake_id', body)

    def test_update_invalid_body_invalid_field(self):
        body = {"cgsnapshot": {"unknown_field": ""}}
        exc = self.assertRaises(webob.exc.HTTPBadRequest,
                                self.controller.update,
                                self.request, 'fake_id', body)
        self.assertTrue('unknown_field' in six.text_type(exc))

    def test_update_invalid_body_readonly_field(self):
        body = {"cgsnapshot": {"created_at": []}}
        exc = self.assertRaises(webob.exc.HTTPBadRequest,
                                self.controller.update,
                                self.request, 'fake_id', body)
        self.assertTrue('created_at' in six.text_type(exc))

    def test_list_index(self):
        fake_snap, expected_snap = self._get_fake_simple_cgsnapshot()
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[fake_snap]))
        res_dict = self.controller.index(self.request)
        self.assertEqual([expected_snap], res_dict['cgsnapshots'])

    def test_list_index_no_cgs(self):
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[]))
        res_dict = self.controller.index(self.request)
        self.assertEqual([], res_dict['cgsnapshots'])

    def test_list_index_with_limit(self):
        fake_snap, expected_snap = self._get_fake_simple_cgsnapshot()
        fake_snap2, expected_snap2 = self._get_fake_simple_cgsnapshot(
            id="fake_id2")
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[fake_snap, fake_snap2]))
        req = fakes.HTTPRequest.blank('/cgsnapshots?limit=1',
                                      version=self.api_version,
                                      experimental=True)
        res_dict = self.controller.index(req)
        self.assertEqual(1, len(res_dict['cgsnapshots']))
        self.assertEqual([expected_snap], res_dict['cgsnapshots'])

    def test_list_index_with_limit_and_offset(self):
        fake_snap, expected_snap = self._get_fake_simple_cgsnapshot()
        fake_snap2, expected_snap2 = self._get_fake_simple_cgsnapshot(
            id="fake_id2")
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[fake_snap, fake_snap2]))
        req = fakes.HTTPRequest.blank('/cgsnapshots?limit=1&offset=1',
                                      version=self.api_version,
                                      experimental=True)

        res_dict = self.controller.index(req)

        self.assertEqual(1, len(res_dict['cgsnapshots']))
        self.assertEqual([expected_snap2], res_dict['cgsnapshots'])

    def test_list_detail(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[fake_snap]))
        res_dict = self.controller.detail(self.request)
        self.assertEqual([expected_snap], res_dict['cgsnapshots'])

    def test_list_detail_no_cgs(self):
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[]))
        res_dict = self.controller.detail(self.request)
        self.assertEqual([], res_dict['cgsnapshots'])

    def test_list_detail_with_limit(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        fake_snap2, expected_snap2 = self._get_fake_cgsnapshot(
            id="fake_id2")
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[fake_snap, fake_snap2]))
        req = fakes.HTTPRequest.blank('/cgsnapshots?limit=1',
                                      version=self.api_version,
                                      experimental=True)
        res_dict = self.controller.detail(req)
        self.assertEqual(1, len(res_dict['cgsnapshots']))
        self.assertEqual([expected_snap], res_dict['cgsnapshots'])

    def test_list_detail_with_limit_and_offset(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        fake_snap2, expected_snap2 = self._get_fake_cgsnapshot(
            id="fake_id2")
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshots',
                         mock.Mock(return_value=[fake_snap, fake_snap2]))
        req = fakes.HTTPRequest.blank('/cgsnapshots?limit=1&offset=1',
                                      version=self.api_version,
                                      experimental=True)

        res_dict = self.controller.detail(req)

        self.assertEqual(1, len(res_dict['cgsnapshots']))
        self.assertEqual([expected_snap2], res_dict['cgsnapshots'])

    def test_delete(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        self.mock_object(self.controller.cg_api, 'get_cgsnapshot',
                         mock.Mock(return_value=fake_snap))
        self.mock_object(self.controller.cg_api, 'delete_cgsnapshot')

        res = self.controller.delete(self.request, fake_snap['id'])

        self.assertEqual(202, res.status_code)

    def test_delete_not_found(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        self.mock_object(self.controller.cg_api, 'get_cgsnapshot',
                         mock.Mock(side_effect=exception.NotFound))

        self.assertRaises(webob.exc.HTTPNotFound, self.controller.delete,
                          self.request, fake_snap['id'])

    def test_delete_in_conflicting_status(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        self.mock_object(self.controller.cg_api, 'get_cgsnapshot',
                         mock.Mock(return_value=fake_snap))
        self.mock_object(self.controller.cg_api, 'delete_cgsnapshot',
                         mock.Mock(
                             side_effect=exception.InvalidCGSnapshot(
                                 reason='blah')))

        self.assertRaises(webob.exc.HTTPConflict, self.controller.delete,
                          self.request, fake_snap['id'])

    def test_show(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        self.mock_object(self.controller.cg_api, 'get_cgsnapshot',
                         mock.Mock(return_value=fake_snap))

        res_dict = self.controller.show(self.request, fake_snap['id'])

        self.assertEqual(expected_snap, res_dict['cgsnapshot'])

    def test_show_cg_not_found(self):
        fake_snap, expected_snap = self._get_fake_cgsnapshot()
        self.mock_object(self.controller.cg_api, 'get_cgsnapshot',
                         mock.Mock(side_effect=exception.NotFound))

        self.assertRaises(webob.exc.HTTPNotFound, self.controller.show,
                          self.request, fake_snap['id'])

    def test_members_empty(self):
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshot_members',
                         mock.Mock(return_value=[]))
        res_dict = self.controller.members(self.request, 'fake_cg_id')
        self.assertEqual([], res_dict['cgsnapshot_members'])

    def test_members(self):
        fake_member, expected_member = self._get_fake_cgsnapshot_member()
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshot_members',
                         mock.Mock(return_value=[fake_member]))
        res_dict = self.controller.members(self.request, 'fake_cg_id')
        self.assertEqual([expected_member], res_dict['cgsnapshot_members'])

    def test_members_with_limit(self):
        fake_member, expected_member = self._get_fake_cgsnapshot_member()
        fake_member2, expected_member2 = self._get_fake_cgsnapshot_member(
            id="fake_id2")
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshot_members',
                         mock.Mock(return_value=[fake_member, fake_member2]))
        req = fakes.HTTPRequest.blank('/members?limit=1',
                                      version=self.api_version,
                                      experimental=True)
        res_dict = self.controller.members(req, 'fake_cg_id')
        self.assertEqual(1, len(res_dict['cgsnapshot_members']))

    def test_members_with_limit_and_offset(self):
        fake_member, expected_member = self._get_fake_cgsnapshot_member()
        fake_member2, expected_member2 = self._get_fake_cgsnapshot_member(
            id="fake_id2")
        self.mock_object(self.controller.cg_api, 'get_all_cgsnapshot_members',
                         mock.Mock(return_value=[fake_member, fake_member2]))
        req = fakes.HTTPRequest.blank('/members?limit=1&offset=1',
                                      version=self.api_version,
                                      experimental=True)

        res_dict = self.controller.members(req, 'fake_cg_id')

        self.assertEqual(1, len(res_dict['cgsnapshot_members']))
        self.assertEqual([expected_member2], res_dict['cgsnapshot_members'])
