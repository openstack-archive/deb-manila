# Copyright 2013 Mirantis Inc.
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

from oslo_config import cfg
from oslo_serialization import jsonutils
import webob

from manila.common import constants
from manila import context
from manila import db
from manila import exception
from manila.share import api as share_api
from manila import test
from manila.tests.api.contrib import stubs
from manila.tests.api import fakes
from manila.tests import db_utils

CONF = cfg.CONF


def app():
    # no auth, just let environ['manila.context'] pass through
    api = fakes.router.APIRouter()
    mapper = fakes.urlmap.URLMap()
    mapper['/v1'] = api
    return mapper


class AdminActionsTest(test.TestCase):

    def setUp(self):
        super(AdminActionsTest, self).setUp()
        self.flags(rpc_backend='manila.openstack.common.rpc.impl_fake')
        self.share_api = share_api.API()
        self.admin_context = context.RequestContext('admin', 'fake', True)
        self.member_context = context.RequestContext('fake', 'fake')

    def test_reset_status_as_admin(self):
        # current status is available
        share = db_utils.create_share(status=constants.STATUS_AVAILABLE)
        req = webob.Request.blank('/v1/fake/shares/%s/action' % share['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        # request status of 'error'
        req.body = jsonutils.dumps(
            {'os-reset_status': {'status': constants.STATUS_ERROR}})
        # attach admin context to request
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        # request is accepted
        self.assertEqual(resp.status_int, 202)
        share = db.share_get(self.admin_context, share['id'])
        # status changed to 'error'
        self.assertEqual(share['status'], constants.STATUS_ERROR)

    def test_reset_status_as_non_admin(self):
        # current status is 'error'
        share = db_utils.create_share(status=constants.STATUS_ERROR)
        req = webob.Request.blank('/v1/fake/shares/%s/action' % share['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        # request changing status to available
        req.body = jsonutils.dumps(
            {'os-reset_status': {'status': constants.STATUS_AVAILABLE}})
        # non-admin context
        req.environ['manila.context'] = self.member_context
        resp = req.get_response(app())
        # request is not authorized
        self.assertEqual(resp.status_int, 403)
        share = db.share_get(context.get_admin_context(), share['id'])
        # status is still 'error'
        self.assertEqual(share['status'], constants.STATUS_ERROR)

    def test_malformed_reset_status_body(self):
        # current status is available
        share = db_utils.create_share(status=constants.STATUS_AVAILABLE)
        req = webob.Request.blank('/v1/fake/shares/%s/action' % share['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        # malformed request body
        req.body = jsonutils.dumps({'os-reset_status': {'x-status': 'bad'}})
        # attach admin context to request
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        # bad request
        self.assertEqual(resp.status_int, 400)
        share = db.share_get(self.admin_context, share['id'])
        # status is still 'available'
        self.assertEqual(share['status'], constants.STATUS_AVAILABLE)

    def test_invalid_status_for_share(self):
        # current status is available
        share = db_utils.create_share(status=constants.STATUS_AVAILABLE)
        req = webob.Request.blank('/v1/fake/shares/%s/action' % share['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        # 'invalid' is not a valid status
        req.body = jsonutils.dumps({'os-reset_status': {'status': 'invalid'}})
        # attach admin context to request
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        # bad request
        self.assertEqual(resp.status_int, 400)
        share = db.share_get(self.admin_context, share['id'])
        # status is still 'available'
        self.assertEqual(share['status'], constants.STATUS_AVAILABLE)

    def test_reset_status_for_missing_share(self):
        # missing-share-id
        req = webob.Request.blank('/v1/fake/shares/%s/action' %
                                  'missing-share-id')
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        # malformed request body
        req.body = jsonutils.dumps(
            {'os-reset_status': {'status': constants.STATUS_AVAILABLE}})
        # attach admin context to request
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        # not found
        self.assertEqual(resp.status_int, 404)
        self.assertRaises(exception.NotFound,
                          db.share_get,
                          self.admin_context,
                          'missing-share-id')

    def test_snapshot_reset_status(self):
        # snapshot in 'error_deleting'
        share = db_utils.create_share()
        snapshot = db_utils.create_snapshot(
            status=constants.STATUS_ERROR_DELETING,
            share_id=share['id']
        )
        req = webob.Request.blank('/v1/fake/snapshots/%s/action' %
                                  snapshot['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        # request status of 'error'
        req.body = jsonutils.dumps(
            {'os-reset_status': {'status': constants.STATUS_ERROR}})
        # attach admin context to request
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        # request is accepted
        self.assertEqual(resp.status_int, 202)
        snapshot = db.share_snapshot_get(self.admin_context, snapshot['id'])
        # status changed to 'error'
        self.assertEqual(snapshot['status'], constants.STATUS_ERROR)

    def test_invalid_status_for_snapshot(self):
        # snapshot in 'available'
        share = db_utils.create_share()
        snapshot = db_utils.create_snapshot(
            status=constants.STATUS_AVAILABLE,
            share_id=share['id']
        )
        req = webob.Request.blank('/v1/fake/snapshots/%s/action' %
                                  snapshot['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        # 'attaching' is not a valid status for snapshots
        req.body = jsonutils.dumps({'os-reset_status': {'status':
                                                        'attaching'}})
        # attach admin context to request
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        # request is accepted
        self.assertEqual(resp.status_int, 400)
        snapshot = db.share_snapshot_get(self.admin_context, snapshot['id'])
        # status is still 'available'
        self.assertEqual(snapshot['status'], constants.STATUS_AVAILABLE)

    def test_admin_force_delete_share(self):
        share = db_utils.create_share(size=1, override_defaults=True)
        req = webob.Request.blank('/v1/fake/shares/%s/action' % share['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        req.body = jsonutils.dumps({'os-force_delete': {}})
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        self.assertEqual(resp.status_int, 202)
        self.assertRaises(exception.NotFound,
                          db.share_get,
                          self.admin_context,
                          share['id'])

    def test_member_force_delete_share(self):
        share = db_utils.create_share(size=1)
        req = webob.Request.blank('/v1/fake/shares/%s/action' % share['id'])
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        req.body = jsonutils.dumps({'os-force_delete': {}})
        req.environ['manila.context'] = self.member_context
        resp = req.get_response(app())
        self.assertEqual(resp.status_int, 403)

    def test_admin_force_delete_snapshot(self):
        snapshot = stubs.stub_snapshot(1, host='foo')
        self.mock_object(db, 'share_get', lambda x, y: snapshot)
        self.mock_object(db, 'share_snapshot_get', lambda x, y: snapshot)
        self.mock_object(share_api.API, 'delete_snapshot',
                         lambda *x, **y: True)
        path = '/v1/fake/snapshots/%s/action' % snapshot['id']
        req = webob.Request.blank(path)
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        req.body = jsonutils.dumps({'os-force_delete': {}})
        req.environ['manila.context'] = self.admin_context
        resp = req.get_response(app())
        self.assertEqual(resp.status_int, 202)

    def test_member_force_delete_snapshot(self):
        snapshot = stubs.stub_snapshot(1, host='foo')
        self.mock_object(db, 'share_get', lambda x, y: snapshot)
        self.mock_object(db, 'share_snapshot_get', lambda x, y: snapshot)
        self.mock_object(share_api.API, 'delete_snapshot',
                         lambda *x, **y: True)
        path = '/v1/fake/snapshots/%s/action' % snapshot['id']
        req = webob.Request.blank(path)
        req.method = 'POST'
        req.headers['content-type'] = 'application/json'
        req.body = jsonutils.dumps({'os-force_delete': {}})
        req.environ['manila.context'] = self.member_context
        resp = req.get_response(app())
        self.assertEqual(resp.status_int, 403)
