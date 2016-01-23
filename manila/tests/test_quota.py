# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

import datetime

import mock
from oslo_config import cfg
from oslo_utils import timeutils
import testtools

from manila.common import constants
from manila import context
from manila import db
from manila.db.sqlalchemy import api as sqa_api
from manila.db.sqlalchemy import models as sqa_models
from manila import exception
from manila import quota
from manila import share
from manila import test
from manila.tests import db_utils

CONF = cfg.CONF


class QuotaIntegrationTestCase(test.TestCase):
    def setUp(self):
        super(QuotaIntegrationTestCase, self).setUp()
        self.flags(quota_shares=2,
                   quota_gigabytes=20)

        self.user_id = 'admin'
        self.project_id = 'admin'
        self.create_share = lambda size=10: (
            db_utils.create_share(user_id=self.user_id,
                                  project_id=self.project_id,
                                  size=size,
                                  status=constants.STATUS_AVAILABLE)
        )
        self.context = context.RequestContext(self.user_id,
                                              self.project_id,
                                              is_admin=True)

    @testtools.skip("SQLAlchemy sqlite insert bug")
    def test_too_many_shares(self):
        share_ids = []
        for i in range(CONF.quota_shares):
            share_ref = self.create_share()
            share_ids.append(share_ref['id'])
        self.assertRaises(exception.QuotaError,
                          share.API().create,
                          self.context, 'nfs', 10, '', '', None)
        for share_id in share_ids:
            db.share_delete(self.context, share_id)

    @testtools.skip("SQLAlchemy sqlite insert bug")
    def test_too_many_gigabytes(self):
        share_ids = []
        share_ref = self.create_share(size=20)
        share_ids.append(share_ref['id'])
        self.assertRaises(exception.QuotaError,
                          share.API().create,
                          self.context, 'cifs', 10, '', '', None)
        for share_id in share_ids:
            db.share_delete(self.context, share_id)


class FakeContext(object):
    def __init__(self, project_id, quota_class):
        self.is_admin = False
        self.user_id = 'fake_user'
        self.project_id = project_id
        self.quota_class = quota_class
        self.read_deleted = 'no'

    def elevated(self):
        elevated = self.__class__(self.project_id, self.quota_class)
        elevated.is_admin = True
        return elevated


class FakeDriver(object):
    def __init__(self, by_project=None, by_class=None, reservations=None):
        self.called = []
        self.by_project = by_project or {}
        self.by_class = by_class or {}
        self.reservations = reservations or []

    def get_by_project(self, context, project_id, resource):
        self.called.append(('get_by_project', context, project_id, resource))
        try:
            return self.by_project[project_id][resource]
        except KeyError:
            raise exception.ProjectQuotaNotFound(project_id=project_id)

    def get_by_class(self, context, quota_class, resource):
        self.called.append(('get_by_class', context, quota_class, resource))
        try:
            return self.by_class[quota_class][resource]
        except KeyError:
            raise exception.QuotaClassNotFound(class_name=quota_class)

    def get_defaults(self, context, resources):
        self.called.append(('get_defaults', context, resources))
        return resources

    def get_class_quotas(self, context, resources, quota_class,
                         defaults=True):
        self.called.append(('get_class_quotas', context, resources,
                            quota_class, defaults))
        return resources

    def get_project_quotas(self, context, resources, project_id,
                           quota_class=None, defaults=True, usages=True,
                           remains=False):
        self.called.append(('get_project_quotas', context, resources,
                            project_id, quota_class, defaults, usages,
                            remains))
        return resources

    def limit_check(self, context, resources, values, project_id=None,
                    user_id=None):
        self.called.append(('limit_check', context, resources,
                            values, project_id, user_id))

    def reserve(self, context, resources, deltas, expire=None,
                project_id=None, user_id=None):
        self.called.append(('reserve', context, resources, deltas,
                            expire, project_id, user_id))
        return self.reservations

    def commit(self, context, reservations, project_id=None, user_id=None):
        self.called.append(('commit', context, reservations, project_id,
                            user_id))

    def rollback(self, context, reservations, project_id=None, user_id=None):
        self.called.append(('rollback', context, reservations, project_id,
                            user_id))

    def destroy_all_by_project_and_user(self, context, project_id, user_id):
        self.called.append(('destroy_all_by_project_and_user', context,
                            project_id, user_id))

    def destroy_all_by_project(self, context, project_id):
        self.called.append(('destroy_all_by_project', context, project_id))

    def expire(self, context):
        self.called.append(('expire', context))


class BaseResourceTestCase(test.TestCase):
    def test_no_flag(self):
        resource = quota.BaseResource('test_resource')

        self.assertEqual('test_resource', resource.name)
        self.assertIsNone(resource.flag)
        self.assertEqual(-1, resource.default)

    def test_with_flag(self):
        # We know this flag exists, so use it...
        self.flags(quota_shares=10)
        resource = quota.BaseResource('test_resource', 'quota_shares')

        self.assertEqual('test_resource', resource.name)
        self.assertEqual('quota_shares', resource.flag)
        self.assertEqual(10, resource.default)

    def test_with_flag_no_quota(self):
        self.flags(quota_shares=-1)
        resource = quota.BaseResource('test_resource', 'quota_shares')

        self.assertEqual('test_resource', resource.name)
        self.assertEqual('quota_shares', resource.flag)
        self.assertEqual(-1, resource.default)

    def test_quota_no_project_no_class(self):
        self.flags(quota_shares=10)
        resource = quota.BaseResource('test_resource', 'quota_shares')
        driver = FakeDriver()
        context = FakeContext(None, None)
        quota_value = resource.quota(driver, context)

        self.assertEqual(10, quota_value)

    def test_quota_with_project_no_class(self):
        self.flags(quota_shares=10)
        resource = quota.BaseResource('test_resource', 'quota_shares')
        driver = FakeDriver(
            by_project=dict(
                test_project=dict(test_resource=15), ))
        context = FakeContext('test_project', None)
        quota_value = resource.quota(driver, context)

        self.assertEqual(15, quota_value)

    def test_quota_no_project_with_class(self):
        self.flags(quota_shares=10)
        resource = quota.BaseResource('test_resource', 'quota_shares')
        driver = FakeDriver(
            by_class=dict(
                test_class=dict(test_resource=20), ))
        context = FakeContext(None, 'test_class')
        quota_value = resource.quota(driver, context)

        self.assertEqual(20, quota_value)

    def test_quota_with_project_with_class(self):
        self.flags(quota_shares=10)
        resource = quota.BaseResource('test_resource', 'quota_shares')
        driver = FakeDriver(by_project=dict(
            test_project=dict(test_resource=15), ),
            by_class=dict(test_class=dict(test_resource=20), ))
        context = FakeContext('test_project', 'test_class')
        quota_value = resource.quota(driver, context)

        self.assertEqual(15, quota_value)

    def test_quota_override_project_with_class(self):
        self.flags(quota_shares=10)
        resource = quota.BaseResource('test_resource', 'quota_shares')
        driver = FakeDriver(by_project=dict(
            test_project=dict(test_resource=15),
            override_project=dict(test_resource=20), ))
        context = FakeContext('test_project', 'test_class')
        quota_value = resource.quota(driver, context,
                                     project_id='override_project')

        self.assertEqual(20, quota_value)

    def test_quota_with_project_override_class(self):
        self.flags(quota_shares=10)
        resource = quota.BaseResource('test_resource', 'quota_shares')
        driver = FakeDriver(by_class=dict(
            test_class=dict(test_resource=15),
            override_class=dict(test_resource=20), ))
        context = FakeContext('test_project', 'test_class')
        quota_value = resource.quota(driver, context,
                                     quota_class='override_class')

        self.assertEqual(20, quota_value)


class QuotaEngineTestCase(test.TestCase):
    def test_init(self):
        quota_obj = quota.QuotaEngine()

        self.assertEqual({}, quota_obj._resources)
        self.assertIsInstance(quota_obj._driver, quota.DbQuotaDriver)

    def test_init_override_string(self):
        quota_obj = quota.QuotaEngine(
            quota_driver_class='manila.tests.test_quota.FakeDriver')

        self.assertEqual({}, quota_obj._resources)
        self.assertIsInstance(quota_obj._driver, FakeDriver)

    def test_init_override_obj(self):
        quota_obj = quota.QuotaEngine(quota_driver_class=FakeDriver)

        self.assertEqual({}, quota_obj._resources)
        self.assertEqual(FakeDriver, quota_obj._driver)

    def test_register_resource(self):
        quota_obj = quota.QuotaEngine()
        resource = quota.AbsoluteResource('test_resource')
        quota_obj.register_resource(resource)

        self.assertEqual(dict(test_resource=resource), quota_obj._resources)

    def test_register_resources(self):
        quota_obj = quota.QuotaEngine()
        resources = [
            quota.AbsoluteResource('test_resource1'),
            quota.AbsoluteResource('test_resource2'),
            quota.AbsoluteResource('test_resource3'), ]
        quota_obj.register_resources(resources)

        self.assertEqual(dict(test_resource1=resources[0],
                              test_resource2=resources[1],
                              test_resource3=resources[2], ),
                         quota_obj._resources)

    def test_sync_predeclared(self):
        quota_obj = quota.QuotaEngine()

        def spam(*args, **kwargs):
            pass

        resource = quota.ReservableResource('test_resource', spam)
        quota_obj.register_resource(resource)

        self.assertEqual(spam, resource.sync)

    def test_sync_multi(self):
        quota_obj = quota.QuotaEngine()

        def spam(*args, **kwargs):
            pass

        resources = [
            quota.ReservableResource('test_resource1', spam),
            quota.ReservableResource('test_resource2', spam),
            quota.ReservableResource('test_resource3', spam),
            quota.ReservableResource('test_resource4', spam), ]
        quota_obj.register_resources(resources[:2])

        self.assertEqual(spam, resources[0].sync)
        self.assertEqual(spam, resources[1].sync)
        self.assertEqual(spam, resources[2].sync)
        self.assertEqual(spam, resources[3].sync)

    def test_get_by_project(self):
        context = FakeContext('test_project', 'test_class')
        driver = FakeDriver(
            by_project=dict(
                test_project=dict(test_resource=42)))
        quota_obj = quota.QuotaEngine(quota_driver_class=driver)
        result = quota_obj.get_by_project(context, 'test_project',
                                          'test_resource')

        self.assertEqual([('get_by_project',
                           context,
                           'test_project',
                           'test_resource'), ], driver.called)
        self.assertEqual(42, result)

    def test_get_by_class(self):
        context = FakeContext('test_project', 'test_class')
        driver = FakeDriver(
            by_class=dict(
                test_class=dict(test_resource=42)))
        quota_obj = quota.QuotaEngine(quota_driver_class=driver)
        result = quota_obj.get_by_class(context, 'test_class', 'test_resource')

        self.assertEqual([('get_by_class',
                           context,
                           'test_class',
                           'test_resource'), ], driver.called)
        self.assertEqual(42, result)

    def _make_quota_obj(self, driver):
        quota_obj = quota.QuotaEngine(quota_driver_class=driver)
        resources = [
            quota.AbsoluteResource('test_resource4'),
            quota.AbsoluteResource('test_resource3'),
            quota.AbsoluteResource('test_resource2'),
            quota.AbsoluteResource('test_resource1'), ]
        quota_obj.register_resources(resources)

        return quota_obj

    def test_get_defaults(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        result = quota_obj.get_defaults(context)

        self.assertEqual([('get_defaults',
                           context,
                           quota_obj._resources), ],
                         driver.called)
        self.assertEqual(quota_obj._resources, result)

    def test_get_class_quotas(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        result1 = quota_obj.get_class_quotas(context, 'test_class')
        result2 = quota_obj.get_class_quotas(context, 'test_class', False)

        self.assertEqual([
            ('get_class_quotas',
             context,
             quota_obj._resources,
             'test_class', True),
            ('get_class_quotas',
             context, quota_obj._resources,
             'test_class', False), ], driver.called)
        self.assertEqual(quota_obj._resources, result1)
        self.assertEqual(quota_obj._resources, result2)

    def test_get_project_quotas(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        result1 = quota_obj.get_project_quotas(context, 'test_project')
        result2 = quota_obj.get_project_quotas(context, 'test_project',
                                               quota_class='test_class',
                                               defaults=False,
                                               usages=False)

        self.assertEqual([
            ('get_project_quotas',
             context,
             quota_obj._resources,
             'test_project',
             None,
             True,
             True,
             False),
            ('get_project_quotas',
             context,
             quota_obj._resources,
             'test_project',
             'test_class',
             False,
             False,
             False), ],
            driver.called)
        self.assertEqual(quota_obj._resources, result1)
        self.assertEqual(quota_obj._resources, result2)

    def test_count_no_resource(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        self.assertRaises(exception.QuotaResourceUnknown,
                          quota_obj.count, context, 'test_resource5',
                          True, foo='bar')

    def test_count_wrong_resource(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        self.assertRaises(exception.QuotaResourceUnknown,
                          quota_obj.count, context, 'test_resource1',
                          True, foo='bar')

    def test_count(self):
        def fake_count(context, *args, **kwargs):
            self.assertEqual((True,), args)
            self.assertEqual(dict(foo='bar'), kwargs)
            return 5

        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        quota_obj.register_resource(quota.CountableResource('test_resource5',
                                                            fake_count))
        result = quota_obj.count(context, 'test_resource5', True, foo='bar')

        self.assertEqual(5, result)

    def test_limit_check(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        quota_obj.limit_check(context, test_resource1=4, test_resource2=3,
                              test_resource3=2, test_resource4=1)

        self.assertEqual([
            ('limit_check',
             context,
             quota_obj._resources,
             dict(
                 test_resource1=4,
                 test_resource2=3,
                 test_resource3=2,
                 test_resource4=1,),
             None, None), ],
            driver.called)

    def test_reserve(self):
        context = FakeContext(None, None)
        driver = FakeDriver(reservations=['resv-01',
                                          'resv-02',
                                          'resv-03',
                                          'resv-04', ])
        quota_obj = self._make_quota_obj(driver)
        result1 = quota_obj.reserve(context, test_resource1=4,
                                    test_resource2=3, test_resource3=2,
                                    test_resource4=1)
        result2 = quota_obj.reserve(context, expire=3600,
                                    test_resource1=1, test_resource2=2,
                                    test_resource3=3, test_resource4=4)
        result3 = quota_obj.reserve(context, project_id='fake_project',
                                    test_resource1=1, test_resource2=2,
                                    test_resource3=3, test_resource4=4)

        self.assertEqual([
            ('reserve',
             context,
             quota_obj._resources,
             dict(
                 test_resource1=4,
                 test_resource2=3,
                 test_resource3=2,
                 test_resource4=1, ),
             None,
             None,
             None),
            ('reserve',
             context,
             quota_obj._resources,
             dict(
                 test_resource1=1,
                 test_resource2=2,
                 test_resource3=3,
                 test_resource4=4, ),
             3600,
             None,
             None),
            ('reserve',
             context,
             quota_obj._resources,
             dict(
                 test_resource1=1,
                 test_resource2=2,
                 test_resource3=3,
                 test_resource4=4, ),
             None,
             'fake_project', None), ],
            driver.called)
        self.assertEqual(['resv-01',
                          'resv-02',
                          'resv-03',
                          'resv-04', ], result1)
        self.assertEqual(['resv-01',
                          'resv-02',
                          'resv-03',
                          'resv-04', ], result2)
        self.assertEqual(['resv-01',
                          'resv-02',
                          'resv-03',
                          'resv-04', ], result3)

    def test_commit(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        quota_obj.commit(context, ['resv-01', 'resv-02', 'resv-03'])

        self.assertEqual([('commit',
                           context,
                           ['resv-01',
                            'resv-02',
                            'resv-03'],
                           None, None), ], driver.called)

    def test_rollback(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        quota_obj.rollback(context, ['resv-01', 'resv-02', 'resv-03'])

        self.assertEqual([('rollback',
                           context,
                           ['resv-01',
                            'resv-02',
                            'resv-03'],
                           None, None), ], driver.called)

    def test_destroy_all_by_project_and_user(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        quota_obj.destroy_all_by_project_and_user(context,
                                                  'test_project', 'fake_user')

        self.assertEqual([
            ('destroy_all_by_project_and_user', context, 'test_project',
             'fake_user'), ], driver.called)

    def test_destroy_all_by_project(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        quota_obj.destroy_all_by_project(context, 'test_project')

        self.assertEqual([('destroy_all_by_project',
                           context,
                           'test_project'), ], driver.called)

    def test_expire(self):
        context = FakeContext(None, None)
        driver = FakeDriver()
        quota_obj = self._make_quota_obj(driver)
        quota_obj.expire(context)

        self.assertEqual([('expire', context), ], driver.called)

    def test_resources(self):
        quota_obj = self._make_quota_obj(None)

        self.assertEqual(['test_resource1', 'test_resource2',
                          'test_resource3', 'test_resource4'],
                         quota_obj.resources)


class DbQuotaDriverTestCase(test.TestCase):
    expected_all_context = {
        "shares": {"limit": 10, "in_use": 2, "reserved": 0, },
        "gigabytes": {"limit": 50, "in_use": 10, "reserved": 0, },
        "snapshot_gigabytes": {"limit": 50, "in_use": 20, "reserved": 0, },
        "snapshots": {"limit": 10, "in_use": 4, "reserved": 0, },
        "share_networks": {"limit": 10, "in_use": 0, "reserved": 0, },
    }

    def setUp(self):
        super(DbQuotaDriverTestCase, self).setUp()
        self.flags(
            quota_shares=10, quota_snapshots=10, quota_gigabytes=1000,
            quota_snapshot_gigabytes=1000, reservation_expire=86400,
            until_refresh=0, max_age=0)

        self.driver = quota.DbQuotaDriver()

        self.calls = []

        self.patcher = mock.patch.object(timeutils, 'utcnow')
        self.mock_utcnow = self.patcher.start()
        self.mock_utcnow.return_value = datetime.datetime.utcnow()

    def tearDown(self):
        self.patcher.stop()
        super(DbQuotaDriverTestCase, self).tearDown()

    def test_get_defaults(self):
        # Use our pre-defined resources
        result = self.driver.get_defaults(None, quota.QUOTAS._resources)
        expected = {
            "shares": 10,
            "gigabytes": 1000,
            "snapshot_gigabytes": 1000,
            "snapshots": 10,
            "share_networks": 10,
        }
        self.assertEqual(expected, result)

    def _stub_quota_class_get_all_by_name(self):
        # Stub out quota_class_get_all_by_name
        def fake_qcgabn(context, quota_class):
            self.calls.append('quota_class_get_all_by_name')
            self.assertEqual('test_class', quota_class)
            return dict(gigabytes=500, shares=10, snapshot_gigabytes=50)
        self.mock_object(db, 'quota_class_get_all_by_name', fake_qcgabn)

    def test_get_class_quotas(self):
        self._stub_quota_class_get_all_by_name()
        result = self.driver.get_class_quotas(None, quota.QUOTAS._resources,
                                              'test_class')

        self.assertEqual(['quota_class_get_all_by_name'], self.calls)
        expected = {
            "shares": 10,
            "gigabytes": 500,
            "snapshot_gigabytes": 50,
            "snapshots": 10,
            "share_networks": 10,
        }
        self.assertEqual(expected, result)

    def test_get_class_quotas_no_defaults(self):
        self._stub_quota_class_get_all_by_name()
        result = self.driver.get_class_quotas(None, quota.QUOTAS._resources,
                                              'test_class', False)

        self.assertEqual(['quota_class_get_all_by_name'], self.calls)
        self.assertEqual(
            dict(shares=10, gigabytes=500, snapshot_gigabytes=50), result)

    def _stub_get_by_project_and_user(self):
        def fake_qgabpu(context, project_id, user_id):
            self.calls.append('quota_get_all_by_project_and_user')
            self.assertEqual('test_project', project_id)
            self.assertEqual('fake_user', user_id)
            return dict(
                shares=10, gigabytes=50, snapshots=10, snapshot_gigabytes=50,
                reserved=0)

        def fake_qgabp(context, project_id):
            self.calls.append('quota_get_all_by_project')
            self.assertEqual('test_project', project_id)
            return dict(
                shares=10, gigabytes=50, snapshots=10, snapshot_gigabytes=50,
                reserved=0)

        def fake_qugabpu(context, project_id, user_id):
            self.calls.append('quota_usage_get_all_by_project_and_user')
            self.assertEqual('test_project', project_id)
            self.assertEqual('fake_user', user_id)
            return dict(
                shares=dict(in_use=2, reserved=0),
                gigabytes=dict(in_use=10, reserved=0),
                snapshots=dict(in_use=4, reserved=0),
                snapshot_gigabytes=dict(in_use=20, reserved=0),
            )

        self.mock_object(db, 'quota_get_all_by_project_and_user', fake_qgabpu)
        self.mock_object(db, 'quota_get_all_by_project', fake_qgabp)
        self.mock_object(db, 'quota_usage_get_all_by_project_and_user',
                         fake_qugabpu)

        self._stub_quota_class_get_all_by_name()

    def test_get_user_quotas(self):
        self._stub_get_by_project_and_user()
        result = self.driver.get_user_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project', 'fake_user')

        self.assertEqual([
            'quota_get_all_by_project_and_user',
            'quota_get_all_by_project',
            'quota_usage_get_all_by_project_and_user',
            'quota_class_get_all_by_name', ], self.calls)
        self.assertEqual(self.expected_all_context, result)

    def _stub_get_by_project(self):
        def fake_qgabp(context, project_id):
            self.calls.append('quota_get_all_by_project')
            self.assertEqual('test_project', project_id)
            return dict(
                shares=10, gigabytes=50, snapshot_gigabytes=50, reserved=0)

        def fake_qugabp(context, project_id):
            self.calls.append('quota_usage_get_all_by_project')
            self.assertEqual('test_project', project_id)
            return dict(
                shares=dict(in_use=2, reserved=0),
                snapshots=dict(in_use=4, reserved=0),
                snapshot_gigabytes=dict(in_use=20, reserved=0),
                gigabytes=dict(in_use=10, reserved=0))

        self.mock_object(db, 'quota_get_all_by_project', fake_qgabp)
        self.mock_object(db, 'quota_usage_get_all_by_project', fake_qugabp)

        self._stub_quota_class_get_all_by_name()

    def test_get_project_quotas(self):
        self._stub_get_by_project()
        result = self.driver.get_project_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project')

        self.assertEqual(['quota_get_all_by_project',
                          'quota_usage_get_all_by_project',
                          'quota_class_get_all_by_name', ], self.calls)
        self.assertEqual(self.expected_all_context, result)

    def test_get_project_quotas_with_remains(self):
        self._stub_get_by_project()
        result = self.driver.get_project_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project', remains=True)
        for result_key in result:
            self.assertIn("remains", result[result_key])

    def test_get_user_quotas_alt_context_no_class(self):
        self._stub_get_by_project_and_user()
        result = self.driver.get_user_quotas(
            FakeContext('other_project', None),
            quota.QUOTAS._resources, 'test_project', 'fake_user')

        self.assertEqual([
            'quota_get_all_by_project_and_user',
            'quota_get_all_by_project',
            'quota_usage_get_all_by_project_and_user', ], self.calls)
        self.assertEqual(self.expected_all_context, result)

    def test_get_project_quotas_alt_context_no_class(self):
        self._stub_get_by_project()
        result = self.driver.get_project_quotas(
            FakeContext('other_project', None),
            quota.QUOTAS._resources, 'test_project')

        self.assertEqual(['quota_get_all_by_project',
                          'quota_usage_get_all_by_project', ], self.calls)
        self.assertEqual(self.expected_all_context, result)

    def test_get_user_quotas_alt_context_with_class(self):
        self._stub_get_by_project_and_user()
        result = self.driver.get_user_quotas(
            FakeContext('other_project', 'other_class'),
            quota.QUOTAS._resources, 'test_project', 'fake_user',
            quota_class='test_class')

        self.assertEqual([
            'quota_get_all_by_project_and_user',
            'quota_get_all_by_project',
            'quota_usage_get_all_by_project_and_user',
            'quota_class_get_all_by_name', ], self.calls)
        self.assertEqual(self.expected_all_context, result)

    def test_get_project_quotas_alt_context_with_class(self):
        self._stub_get_by_project()
        result = self.driver.get_project_quotas(
            FakeContext('other_project', 'other_class'),
            quota.QUOTAS._resources, 'test_project', quota_class='test_class')

        self.assertEqual(['quota_get_all_by_project',
                          'quota_usage_get_all_by_project',
                          'quota_class_get_all_by_name', ], self.calls)
        self.assertEqual(self.expected_all_context, result)

    def test_get_user_quotas_no_defaults(self):
        self._stub_get_by_project_and_user()
        result = self.driver.get_user_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project', 'fake_user',
            defaults=False)

        self.assertEqual([
            'quota_get_all_by_project_and_user',
            'quota_get_all_by_project',
            'quota_usage_get_all_by_project_and_user',
            'quota_class_get_all_by_name', ], self.calls)
        expected = {
            "shares": {"limit": 10, "in_use": 2, "reserved": 0, },
            "gigabytes": {"limit": 50, "in_use": 10, "reserved": 0, },
            "snapshot_gigabytes": {"limit": 50, "in_use": 20, "reserved": 0, },
            "snapshots": {"limit": 10, "in_use": 4, "reserved": 0, },
        }
        self.assertEqual(expected, result)

    def test_get_project_quotas_no_defaults(self):
        self._stub_get_by_project()
        result = self.driver.get_project_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project', defaults=False)

        self.assertEqual(['quota_get_all_by_project',
                          'quota_usage_get_all_by_project',
                          'quota_class_get_all_by_name', ], self.calls)
        expected = {
            "shares": {"limit": 10, "in_use": 2, "reserved": 0, },
            "gigabytes": {"limit": 50, "in_use": 10, "reserved": 0, },
            "snapshot_gigabytes": {"limit": 50, "in_use": 20, "reserved": 0, },
        }
        self.assertEqual(expected, result)

    def test_get_user_quotas_no_usages(self):
        self._stub_get_by_project_and_user()
        result = self.driver.get_user_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project', 'fake_user', usages=False)

        self.assertEqual([
            'quota_get_all_by_project_and_user',
            'quota_get_all_by_project',
            'quota_class_get_all_by_name', ], self.calls)
        expected = {
            "shares": {"limit": 10, },
            "gigabytes": {"limit": 50, },
            "snapshot_gigabytes": {"limit": 50, },
            "snapshots": {"limit": 10, },
            "share_networks": {"limit": 10, },
        }
        self.assertEqual(expected, result, result)

    def test_get_project_quotas_no_usages(self):
        self._stub_get_by_project()
        result = self.driver.get_project_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project', usages=False)

        self.assertEqual(['quota_get_all_by_project',
                          'quota_class_get_all_by_name', ], self.calls)
        expected = {
            "shares": {"limit": 10, },
            "gigabytes": {"limit": 50, },
            "snapshot_gigabytes": {"limit": 50, },
            "snapshots": {"limit": 10, },
            "share_networks": {"limit": 10, },
        }
        self.assertEqual(expected, result)

    def _stub_get_settable_quotas(self):
        def fake_get_project_quotas(context, resources, project_id,
                                    quota_class=None, defaults=True,
                                    usages=True, remains=False):
            self.calls.append('get_project_quotas')
            result = {}
            for k, v in resources.items():
                remains = v.default
                in_use = 0
                result[k] = {'limit': v.default, 'in_use': in_use,
                             'reserved': 0, 'remains': remains}
            return result

        def fake_get_user_quotas(context, resources, project_id, user_id,
                                 quota_class=None, defaults=True,
                                 usages=True):
            self.calls.append('get_user_quotas')
            result = {}
            for k, v in resources.items():
                in_use = 0
                result[k] = {'limit': v.default,
                             'in_use': in_use, 'reserved': 0}
            return result

        def fake_qgabpau(context, project_id, user_id):
            self.calls.append('quota_get_all_by_project_and_user')
            return {'shares': 2}

        self.mock_object(self.driver, 'get_project_quotas',
                         fake_get_project_quotas)
        self.mock_object(self.driver, 'get_user_quotas',
                         fake_get_user_quotas)
        self.mock_object(db, 'quota_get_all_by_project_and_user',
                         fake_qgabpau)

    def test_get_settable_quotas_with_user(self):
        self._stub_get_settable_quotas()
        result = self.driver.get_settable_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project', user_id='test_user')

        self.assertEqual([
            'get_project_quotas',
            'get_user_quotas',
            'quota_get_all_by_project_and_user', ], self.calls)
        expected = {
            "shares": {"minimum": 0, "maximum": 12, },
            "gigabytes": {"minimum": 0, "maximum": 1000, },
            "snapshot_gigabytes": {"minimum": 0, "maximum": 1000, },
            "snapshots": {"minimum": 0, "maximum": 10, },
            "share_networks": {"minimum": 0, "maximum": 10, },
        }
        self.assertEqual(expected, result)

    def test_get_settable_quotas_without_user(self):
        self._stub_get_settable_quotas()
        result = self.driver.get_settable_quotas(
            FakeContext('test_project', 'test_class'),
            quota.QUOTAS._resources, 'test_project')

        self.assertEqual(['get_project_quotas', ], self.calls)
        expected = {
            "shares": {"minimum": 0, "maximum": -1, },
            "gigabytes": {"minimum": 0, "maximum": -1, },
            "snapshot_gigabytes": {"minimum": 0, "maximum": -1, },
            "snapshots": {"minimum": 0, "maximum": -1, },
            "share_networks": {"minimum": 0, "maximum": -1, },
        }
        self.assertEqual(expected, result)

    def _stub_get_project_quotas(self):
        def fake_get_project_quotas(context, resources, project_id,
                                    quota_class=None, defaults=True,
                                    usages=True):
            self.calls.append('get_project_quotas')
            return {k: dict(limit=v.default)
                    for k, v in resources.items()}

        self.mock_object(self.driver, 'get_project_quotas',
                         fake_get_project_quotas)

    def test_get_quotas_has_sync_unknown(self):
        self._stub_get_project_quotas()
        self.assertRaises(exception.QuotaResourceUnknown,
                          self.driver._get_quotas,
                          None, quota.QUOTAS._resources,
                          ['unknown'], True)
        self.assertEqual([], self.calls)

    def test_get_quotas_no_sync_unknown(self):
        self._stub_get_project_quotas()
        self.assertRaises(exception.QuotaResourceUnknown,
                          self.driver._get_quotas,
                          None, quota.QUOTAS._resources,
                          ['unknown'], False)
        self.assertEqual([], self.calls)

    def test_get_quotas_has_sync_no_sync_resource(self):
        self._stub_get_project_quotas()
        self.assertRaises(exception.QuotaResourceUnknown,
                          self.driver._get_quotas,
                          None, quota.QUOTAS._resources,
                          ['metadata_items'], True)
        self.assertEqual([], self.calls)

    def test_get_quotas_no_sync_has_sync_resource(self):
        self._stub_get_project_quotas()
        self.assertRaises(exception.QuotaResourceUnknown,
                          self.driver._get_quotas,
                          None, quota.QUOTAS._resources,
                          ['shares'], False)
        self.assertEqual([], self.calls)

    def test_get_quotas_has_sync(self):
        self._stub_get_project_quotas()
        result = self.driver._get_quotas(FakeContext('test_project',
                                                     'test_class'),
                                         quota.QUOTAS._resources,
                                         ['shares', 'gigabytes'],
                                         True)

        self.assertEqual(['get_project_quotas'], self.calls)
        self.assertEqual(dict(shares=10, gigabytes=1000, ), result)

    def _stub_quota_reserve(self):
        def fake_quota_reserve(context, resources, quotas, user_quotas,
                               deltas, expire, until_refresh, max_age,
                               project_id=None, user_id=None):
            self.calls.append(('quota_reserve', expire, until_refresh,
                               max_age))
            return ['resv-1', 'resv-2', 'resv-3']
        self.mock_object(db, 'quota_reserve', fake_quota_reserve)

    def test_reserve_bad_expire(self):
        self._stub_get_project_quotas()
        self._stub_quota_reserve()
        self.assertRaises(exception.InvalidReservationExpiration,
                          self.driver.reserve,
                          FakeContext('test_project', 'test_class'),
                          quota.QUOTAS._resources,
                          dict(shares=2), expire='invalid')
        self.assertEqual([], self.calls)

    def test_reserve_default_expire(self):
        self._stub_get_project_quotas()
        self._stub_quota_reserve()
        result = self.driver.reserve(FakeContext('test_project', 'test_class'),
                                     quota.QUOTAS._resources,
                                     dict(shares=2))

        expire = timeutils.utcnow() + datetime.timedelta(seconds=86400)
        self.assertEqual(['get_project_quotas',
                          ('quota_reserve', expire, 0, 0), ], self.calls)
        self.assertEqual(['resv-1', 'resv-2', 'resv-3'], result)

    def test_reserve_int_expire(self):
        self._stub_get_project_quotas()
        self._stub_quota_reserve()
        result = self.driver.reserve(FakeContext('test_project', 'test_class'),
                                     quota.QUOTAS._resources,
                                     dict(shares=2), expire=3600)

        expire = timeutils.utcnow() + datetime.timedelta(seconds=3600)
        self.assertEqual(['get_project_quotas',
                          ('quota_reserve', expire, 0, 0), ], self.calls)
        self.assertEqual(['resv-1', 'resv-2', 'resv-3'], result)

    def test_reserve_timedelta_expire(self):
        self._stub_get_project_quotas()
        self._stub_quota_reserve()
        expire_delta = datetime.timedelta(seconds=60)
        result = self.driver.reserve(FakeContext('test_project', 'test_class'),
                                     quota.QUOTAS._resources,
                                     dict(shares=2), expire=expire_delta)

        expire = timeutils.utcnow() + expire_delta
        self.assertEqual(['get_project_quotas',
                          ('quota_reserve', expire, 0, 0), ], self.calls)
        self.assertEqual(['resv-1', 'resv-2', 'resv-3'], result)

    def test_reserve_datetime_expire(self):
        self._stub_get_project_quotas()
        self._stub_quota_reserve()
        expire = timeutils.utcnow() + datetime.timedelta(seconds=120)
        result = self.driver.reserve(FakeContext('test_project', 'test_class'),
                                     quota.QUOTAS._resources,
                                     dict(shares=2), expire=expire)

        self.assertEqual(['get_project_quotas',
                          ('quota_reserve', expire, 0, 0), ], self.calls)
        self.assertEqual(['resv-1', 'resv-2', 'resv-3'], result)

    def test_reserve_until_refresh(self):
        self._stub_get_project_quotas()
        self._stub_quota_reserve()
        self.flags(until_refresh=500)
        expire = timeutils.utcnow() + datetime.timedelta(seconds=120)
        result = self.driver.reserve(FakeContext('test_project', 'test_class'),
                                     quota.QUOTAS._resources,
                                     dict(shares=2), expire=expire)

        self.assertEqual(['get_project_quotas',
                          ('quota_reserve', expire, 500, 0), ], self.calls)
        self.assertEqual(['resv-1', 'resv-2', 'resv-3'], result)

    def test_reserve_max_age(self):
        self._stub_get_project_quotas()
        self._stub_quota_reserve()
        self.flags(max_age=86400)
        expire = timeutils.utcnow() + datetime.timedelta(seconds=120)
        result = self.driver.reserve(FakeContext('test_project', 'test_class'),
                                     quota.QUOTAS._resources,
                                     dict(shares=2), expire=expire)

        self.assertEqual(['get_project_quotas',
                          ('quota_reserve', expire, 0, 86400), ], self.calls)
        self.assertEqual(['resv-1', 'resv-2', 'resv-3'], result)

    def _stub_quota_delete_all_by_project(self):
        def fake_quota_delete_all_by_project(context, project_id):
            self.calls.append(('quota_destroy_all_by_project', project_id))
            return None
        self.mock_object(sqa_api, 'quota_destroy_all_by_project',
                         fake_quota_delete_all_by_project)

    def test_delete_by_project(self):
        self._stub_quota_delete_all_by_project()
        self.driver.destroy_all_by_project(FakeContext('test_project',
                                                       'test_class'),
                                           'test_project')
        self.assertEqual([('quota_destroy_all_by_project',
                           ('test_project')), ], self.calls)


class FakeSession(object):
    def begin(self):
        return self

    def add(self, instance):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        return False


class FakeUsage(sqa_models.QuotaUsage):
    def save(self, *args, **kwargs):
        pass


class QuotaReserveSqlAlchemyTestCase(test.TestCase):
    # manila.db.sqlalchemy.api.quota_reserve is so complex it needs its
    # own test case, and since it's a quota manipulator, this is the
    # best place to put it...

    def setUp(self):
        super(QuotaReserveSqlAlchemyTestCase, self).setUp()

        self.sync_called = set()

        def make_sync(res_name):
            def sync(context, project_id, user_id, session):
                self.sync_called.add(res_name)
                if res_name in self.usages:
                    if self.usages[res_name].in_use < 0:
                        return {res_name: 2}
                    else:
                        return {res_name: self.usages[res_name].in_use - 1}
                return {res_name: 0}
            return sync

        self.resources = {}
        for res_name in ('shares', 'gigabytes'):
            method_name = '_sync_%s' % res_name
            sqa_api.QUOTA_SYNC_FUNCTIONS[method_name] = make_sync(res_name)
            res = quota.ReservableResource(res_name, '_sync_%s' % res_name)
            self.resources[res_name] = res

        self.expire = timeutils.utcnow() + datetime.timedelta(seconds=3600)

        self.usages = {}
        self.usages_created = {}
        self.reservations_created = {}

        def fake_get_session():
            return FakeSession()

        def fake_get_project_quota_usages(context, session, project_id):
            return self.usages.copy()

        def fake_get_user_quota_usages(context, session, project_id, user_id):
            return self.usages.copy()

        def fake_quota_usage_create(context, project_id, user_id, resource,
                                    in_use, reserved, until_refresh,
                                    session=None, save=True):
            quota_usage_ref = self._make_quota_usage(
                project_id, user_id, resource, in_use, reserved, until_refresh,
                timeutils.utcnow(), timeutils.utcnow())

            self.usages_created[resource] = quota_usage_ref

            return quota_usage_ref

        def fake_reservation_create(context, uuid, usage_id, project_id,
                                    user_id, resource, delta, expire,
                                    session=None):
            reservation_ref = self._make_reservation(
                uuid, usage_id, project_id, user_id, resource, delta, expire,
                timeutils.utcnow(), timeutils.utcnow())

            self.reservations_created[resource] = reservation_ref

            return reservation_ref

        self.mock_object(sqa_api, 'get_session', fake_get_session)
        self.mock_object(sqa_api, '_get_project_quota_usages',
                         fake_get_project_quota_usages)
        self.mock_object(sqa_api, '_get_user_quota_usages',
                         fake_get_user_quota_usages)
        self.mock_object(sqa_api, '_quota_usage_create',
                         fake_quota_usage_create)
        self.mock_object(sqa_api, '_reservation_create',
                         fake_reservation_create)

        self.patcher = mock.patch.object(timeutils, 'utcnow')
        self.mock_utcnow = self.patcher.start()
        self.mock_utcnow.return_value = datetime.datetime.utcnow()

    def tearDown(self):
        self.patcher.stop()
        super(QuotaReserveSqlAlchemyTestCase, self).tearDown()

    def _make_quota_usage(self, project_id, user_id, resource, in_use,
                          reserved, until_refresh, created_at, updated_at):
        quota_usage_ref = FakeUsage()
        quota_usage_ref.id = len(self.usages) + len(self.usages_created)
        quota_usage_ref.project_id = project_id
        quota_usage_ref.resource = resource
        quota_usage_ref.in_use = in_use
        quota_usage_ref.reserved = reserved
        quota_usage_ref.until_refresh = until_refresh
        quota_usage_ref.created_at = created_at
        quota_usage_ref.updated_at = updated_at
        quota_usage_ref.deleted_at = None
        quota_usage_ref.deleted = False

        return quota_usage_ref

    def init_usage(self, project_id, user_id, resource, in_use, reserved,
                   until_refresh=None, created_at=None, updated_at=None):
        if created_at is None:
            created_at = timeutils.utcnow()
        if updated_at is None:
            updated_at = timeutils.utcnow()

        quota_usage_ref = self._make_quota_usage(project_id, user_id,
                                                 resource, in_use,
                                                 reserved, until_refresh,
                                                 created_at, updated_at)

        self.usages[resource] = quota_usage_ref

    def compare_usage(self, usage_dict, expected):
        for usage in expected:
            resource = usage['resource']
            for key, value in usage.items():
                actual = getattr(usage_dict[resource], key)
                self.assertEqual(value, actual,
                                 "%s != %s on usage for resource %s" %
                                 (value, actual, resource))

    def _make_reservation(self, uuid, usage_id, project_id, user_id, resource,
                          delta, expire, created_at, updated_at):
        reservation_ref = sqa_models.Reservation()
        reservation_ref.id = len(self.reservations_created)
        reservation_ref.uuid = uuid
        reservation_ref.usage_id = usage_id
        reservation_ref.project_id = project_id
        reservation_ref.resource = resource
        reservation_ref.delta = delta
        reservation_ref.expire = expire
        reservation_ref.created_at = created_at
        reservation_ref.updated_at = updated_at
        reservation_ref.deleted_at = None
        reservation_ref.deleted = False

        return reservation_ref

    def compare_reservation(self, reservations, expected):
        reservations = set(reservations)
        for resv in expected:
            resource = resv['resource']
            resv_obj = self.reservations_created[resource]

            self.assertIn(resv_obj.uuid, reservations)
            reservations.discard(resv_obj.uuid)

            for key, value in resv.items():
                actual = getattr(resv_obj, key)
                self.assertEqual(value, actual,
                                 "%s != %s on reservation for resource %s" %
                                 (value, actual, resource))

        self.assertEqual(0, len(reservations))

    def test_quota_reserve_create_usages(self):
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5,
                      gigabytes=10 * 1024, )
        deltas = dict(shares=2,
                      gigabytes=2 * 1024, )
        result = sqa_api.quota_reserve(context, self.resources, quotas,
                                       quotas, deltas, self.expire, 0, 0)

        self.assertEqual(set(['shares', 'gigabytes']), self.sync_called)
        self.compare_usage(self.usages_created,
                           [dict(resource='shares',
                                 project_id='test_project',
                                 in_use=0,
                                 reserved=2,
                                 until_refresh=None),
                            dict(resource='gigabytes',
                                 project_id='test_project',
                                 in_use=0,
                                 reserved=2 * 1024,
                                 until_refresh=None), ])
        self.compare_reservation(
            result,
            [dict(resource='shares',
                  usage_id=self.usages_created['shares'],
                  project_id='test_project',
                  delta=2),
             dict(resource='gigabytes',
                  usage_id=self.usages_created['gigabytes'],
                  delta=2 * 1024), ])

    def test_quota_reserve_negative_in_use(self):
        self.init_usage('test_project', 'test_user', 'shares', -1, 0,
                        until_refresh=1)
        self.init_usage('test_project', 'test_user', 'gigabytes', -1, 0,
                        until_refresh=1)
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5,
                      gigabytes=10 * 1024, )
        deltas = dict(shares=2,
                      gigabytes=2 * 1024, )
        result = sqa_api.quota_reserve(context, self.resources, quotas,
                                       quotas, deltas, self.expire, 5, 0)

        self.assertEqual(set(['shares', 'gigabytes']), self.sync_called)
        self.compare_usage(self.usages, [dict(resource='shares',
                                              project_id='test_project',
                                              in_use=2,
                                              reserved=2,
                                              until_refresh=5),
                                         dict(resource='gigabytes',
                                              project_id='test_project',
                                              in_use=2,
                                              reserved=2 * 1024,
                                              until_refresh=5), ])
        self.assertEqual({}, self.usages_created)
        self.compare_reservation(result,
                                 [dict(resource='shares',
                                       usage_id=self.usages['shares'],
                                       project_id='test_project',
                                       delta=2),
                                  dict(resource='gigabytes',
                                       usage_id=self.usages['gigabytes'],
                                       delta=2 * 1024), ])

    def test_quota_reserve_until_refresh(self):
        self.init_usage('test_project', 'test_user', 'shares', 3, 0,
                        until_refresh=1)
        self.init_usage('test_project', 'test_user', 'gigabytes', 3, 0,
                        until_refresh=1)
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5, gigabytes=10 * 1024, )
        deltas = dict(shares=2, gigabytes=2 * 1024, )
        result = sqa_api.quota_reserve(context, self.resources, quotas,
                                       quotas, deltas, self.expire, 5, 0)

        self.assertEqual(set(['shares', 'gigabytes']), self.sync_called)
        self.compare_usage(self.usages, [dict(resource='shares',
                                              project_id='test_project',
                                              in_use=2,
                                              reserved=2,
                                              until_refresh=5),
                                         dict(resource='gigabytes',
                                              project_id='test_project',
                                              in_use=2,
                                              reserved=2 * 1024,
                                              until_refresh=5), ])
        self.assertEqual({}, self.usages_created)
        self.compare_reservation(result,
                                 [dict(resource='shares',
                                       usage_id=self.usages['shares'],
                                       project_id='test_project',
                                       delta=2),
                                  dict(resource='gigabytes',
                                       usage_id=self.usages['gigabytes'],
                                       delta=2 * 1024), ])

    def test_quota_reserve_max_age(self):
        max_age = 3600
        record_created = (timeutils.utcnow() -
                          datetime.timedelta(seconds=max_age))
        self.init_usage('test_project', 'test_user', 'shares', 3, 0,
                        created_at=record_created, updated_at=record_created)
        self.init_usage('test_project', 'test_user', 'gigabytes', 3, 0,
                        created_at=record_created, updated_at=record_created)
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5, gigabytes=10 * 1024, )
        deltas = dict(shares=2, gigabytes=2 * 1024, )
        result = sqa_api.quota_reserve(context, self.resources, quotas,
                                       quotas, deltas, self.expire, 0,
                                       max_age)

        self.assertEqual(set(['shares', 'gigabytes']), self.sync_called)
        self.compare_usage(self.usages, [dict(resource='shares',
                                              project_id='test_project',
                                              in_use=2,
                                              reserved=2,
                                              until_refresh=None),
                                         dict(resource='gigabytes',
                                              project_id='test_project',
                                              in_use=2,
                                              reserved=2 * 1024,
                                              until_refresh=None), ])
        self.assertEqual({}, self.usages_created)
        self.compare_reservation(result,
                                 [dict(resource='shares',
                                       usage_id=self.usages['shares'],
                                       project_id='test_project',
                                       delta=2),
                                  dict(resource='gigabytes',
                                       usage_id=self.usages['gigabytes'],
                                       delta=2 * 1024), ])

    def test_quota_reserve_no_refresh(self):
        self.init_usage('test_project', 'test_user', 'shares', 3, 0)
        self.init_usage('test_project', 'test_user', 'gigabytes', 3, 0)
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5, gigabytes=10 * 1024, )
        deltas = dict(shares=2, gigabytes=2 * 1024, )
        result = sqa_api.quota_reserve(context, self.resources, quotas,
                                       quotas, deltas, self.expire, 0, 0)

        self.assertEqual(set([]), self.sync_called)
        self.compare_usage(self.usages, [dict(resource='shares',
                                              project_id='test_project',
                                              in_use=3,
                                              reserved=2,
                                              until_refresh=None),
                                         dict(resource='gigabytes',
                                              project_id='test_project',
                                              in_use=3,
                                              reserved=2 * 1024,
                                              until_refresh=None), ])
        self.assertEqual({}, self.usages_created)
        self.compare_reservation(result,
                                 [dict(resource='shares',
                                       usage_id=self.usages['shares'],
                                       project_id='test_project',
                                       delta=2),
                                  dict(resource='gigabytes',
                                       usage_id=self.usages['gigabytes'],
                                       delta=2 * 1024), ])

    def test_quota_reserve_unders(self):
        self.init_usage('test_project', 'test_user', 'shares', 1, 0)
        self.init_usage('test_project', 'test_user', 'gigabytes', 1 * 1024, 0)
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5, gigabytes=10 * 1024, )
        deltas = dict(shares=-2, gigabytes=-2 * 1024, )
        result = sqa_api.quota_reserve(context, self.resources, quotas,
                                       quotas, deltas, self.expire, 0, 0)

        self.assertEqual(set([]), self.sync_called)
        self.compare_usage(self.usages, [dict(resource='shares',
                                              project_id='test_project',
                                              in_use=1,
                                              reserved=0,
                                              until_refresh=None),
                                         dict(resource='gigabytes',
                                              project_id='test_project',
                                              in_use=1 * 1024,
                                              reserved=0,
                                              until_refresh=None), ])
        self.assertEqual({}, self.usages_created)
        self.compare_reservation(result,
                                 [dict(resource='shares',
                                       usage_id=self.usages['shares'],
                                       project_id='test_project',
                                       delta=-2),
                                  dict(resource='gigabytes',
                                       usage_id=self.usages['gigabytes'],
                                       delta=-2 * 1024), ])

    def test_quota_reserve_overs(self):
        self.init_usage('test_project', 'test_user', 'shares', 4, 0)
        self.init_usage('test_project', 'test_user', 'gigabytes', 10 * 1024,
                        0)
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5, gigabytes=10 * 1024, )
        deltas = dict(shares=2, gigabytes=2 * 1024, )
        self.assertRaises(exception.OverQuota,
                          sqa_api.quota_reserve,
                          context, self.resources, quotas, quotas,
                          deltas, self.expire, 0, 0)

        self.assertEqual(set([]), self.sync_called)
        self.compare_usage(self.usages, [dict(resource='shares',
                                              project_id='test_project',
                                              in_use=4,
                                              reserved=0,
                                              until_refresh=None),
                                         dict(resource='gigabytes',
                                              project_id='test_project',
                                              in_use=10 * 1024,
                                              reserved=0,
                                              until_refresh=None), ])
        self.assertEqual({}, self.usages_created)
        self.assertEqual({}, self.reservations_created)

    def test_quota_reserve_reduction(self):
        self.init_usage('test_project', 'test_user', 'shares', 10, 0)
        self.init_usage('test_project', 'test_user', 'gigabytes', 20 * 1024,
                        0)
        context = FakeContext('test_project', 'test_class')
        quotas = dict(shares=5, gigabytes=10 * 1024, )
        deltas = dict(shares=-2, gigabytes=-2 * 1024, )
        result = sqa_api.quota_reserve(context, self.resources, quotas,
                                       quotas, deltas, self.expire, 0, 0)

        self.assertEqual(set([]), self.sync_called)
        self.compare_usage(self.usages, [dict(resource='shares',
                                              project_id='test_project',
                                              in_use=10,
                                              reserved=0,
                                              until_refresh=None),
                                         dict(resource='gigabytes',
                                              project_id='test_project',
                                              in_use=20 * 1024,
                                              reserved=0,
                                              until_refresh=None), ])
        self.assertEqual({}, self.usages_created)
        self.compare_reservation(result,
                                 [dict(resource='shares',
                                       usage_id=self.usages['shares'],
                                       project_id='test_project',
                                       delta=-2),
                                  dict(resource='gigabytes',
                                       usage_id=self.usages['gigabytes'],
                                       project_id='test_project',
                                       delta=-2 * 1024), ])
