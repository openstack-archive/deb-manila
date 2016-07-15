# Copyright (c) 2014 Red Hat, Inc.
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
import socket

import ddt
import mock
from oslo_config import cfg

from manila import context
from manila import exception
from manila.share import configuration as config
from manila.share.drivers import ganesha
from manila.share.drivers import glusterfs
from manila.share.drivers.glusterfs import layout
from manila import test
from manila.tests import fake_share
from manila.tests import fake_utils


CONF = cfg.CONF


fake_gluster_manager_attrs = {
    'export': '127.0.0.1:/testvol',
    'host': '127.0.0.1',
    'qualified': 'testuser@127.0.0.1:/testvol',
    'user': 'testuser',
    'volume': 'testvol',
    'path_to_private_key': '/fakepath/to/privatekey',
    'remote_server_password': 'fakepassword',
}

fake_share_name = 'fakename'
NFS_EXPORT_DIR = 'nfs.export-dir'
NFS_EXPORT_VOL = 'nfs.export-volumes'
NFS_RPC_AUTH_ALLOW = 'nfs.rpc-auth-allow'
NFS_RPC_AUTH_REJECT = 'nfs.rpc-auth-reject'


@ddt.ddt
class GlusterfsShareDriverTestCase(test.TestCase):
    """Tests GlusterfsShareDriver."""

    def setUp(self):
        super(GlusterfsShareDriverTestCase, self).setUp()
        fake_utils.stub_out_utils_execute(self)
        self._execute = fake_utils.fake_execute
        self._context = context.get_admin_context()
        self.addCleanup(fake_utils.fake_execute_set_repliers, [])
        self.addCleanup(fake_utils.fake_execute_clear_log)

        CONF.set_default('reserved_share_percentage', 50)
        CONF.set_default('driver_handles_share_servers', False)

        self.fake_conf = config.Configuration(None)
        self._driver = glusterfs.GlusterfsShareDriver(
            execute=self._execute,
            configuration=self.fake_conf)
        self.share = fake_share.fake_share(share_proto='NFS')

    def test_do_setup(self):
        self.mock_object(self._driver, '_get_helper')
        self.mock_object(layout.GlusterfsShareDriverBase, 'do_setup')
        _context = mock.Mock()

        self._driver.do_setup(_context)

        self._driver._get_helper.assert_called_once_with()
        layout.GlusterfsShareDriverBase.do_setup.assert_called_once_with(
            _context)

    @ddt.data(True, False)
    def test_setup_via_manager(self, has_parent):
        gmgr = mock.Mock()
        share_mgr_parent = mock.Mock() if has_parent else None
        nfs_helper = mock.Mock()
        nfs_helper.get_export = mock.Mock(return_value='host:/vol')
        self._driver.nfs_helper = mock.Mock(return_value=nfs_helper)

        ret = self._driver._setup_via_manager(
            {'manager': gmgr, 'share': self.share},
            share_manager_parent=share_mgr_parent)

        gmgr.set_vol_option.assert_called_once_with(
            'nfs.export-volumes', False)
        self._driver.nfs_helper.assert_called_once_with(
            self._execute, self.fake_conf, gluster_manager=gmgr)
        nfs_helper.get_export.assert_called_once_with(self.share)
        self.assertEqual('host:/vol', ret)

    @ddt.data({'helpercls': None, 'path': '/fakepath'},
              {'helpercls': None, 'path': None},
              {'helpercls': glusterfs.GlusterNFSHelper, 'path': '/fakepath'},
              {'helpercls': glusterfs.GlusterNFSHelper, 'path': None})
    @ddt.unpack
    def test_setup_via_manager_path(self, helpercls, path):
        gmgr = mock.Mock()
        gmgr.path = path
        if not helpercls:
            helper = mock.Mock()
            helper.get_export = mock.Mock(return_value='host:/vol')
            helpercls = mock.Mock(return_value=helper)
        self._driver.nfs_helper = helpercls
        if helpercls == glusterfs.GlusterNFSHelper and path is None:
            gmgr.get_vol_option = mock.Mock(return_value=True)

        self._driver._setup_via_manager(
            {'manager': gmgr, 'share': self.share})

        if helpercls == glusterfs.GlusterNFSHelper and path is None:
            gmgr.get_vol_option.assert_called_once_with(
                NFS_EXPORT_VOL, boolean=True)
            args = (NFS_RPC_AUTH_REJECT, '*')
        else:
            args = (NFS_EXPORT_VOL, False)
        gmgr.set_vol_option.assert_called_once_with(*args)

    def test_setup_via_manager_export_volumes_off(self):
        gmgr = mock.Mock()
        gmgr.path = None
        gmgr.get_vol_option = mock.Mock(return_value=False)
        self._driver.nfs_helper = glusterfs.GlusterNFSHelper

        self.assertRaises(exception.GlusterfsException,
                          self._driver._setup_via_manager,
                          {'manager': gmgr, 'share': self.share})

        gmgr.get_vol_option.assert_called_once_with(NFS_EXPORT_VOL,
                                                    boolean=True)

    def test_check_for_setup_error(self):
        self._driver.check_for_setup_error()

    def test_update_share_stats(self):
        self.mock_object(layout.GlusterfsShareDriverBase,
                         '_update_share_stats')

        self._driver._update_share_stats()

        (layout.GlusterfsShareDriverBase._update_share_stats.
         assert_called_once_with({'storage_protocol': 'NFS',
                                  'vendor_name': 'Red Hat',
                                  'share_backend_name': 'GlusterFS',
                                  'reserved_percentage': 50}))

    def test_get_network_allocations_number(self):
        self.assertEqual(0, self._driver.get_network_allocations_number())

    def test_get_helper(self):
        ret = self._driver._get_helper()
        self.assertIsInstance(ret, self._driver.nfs_helper)

    @ddt.data({'path': '/fakepath', 'helper': glusterfs.GlusterNFSHelper},
              {'path': None, 'helper': glusterfs.GlusterNFSVolHelper})
    @ddt.unpack
    def test_get_helper_vol(self, path, helper):
        self._driver.nfs_helper = glusterfs.GlusterNFSHelper

        gmgr = mock.Mock(path=path)
        ret = self._driver._get_helper(gmgr)

        self.assertIsInstance(ret, helper)

    @ddt.data('type', 'level')
    def test_supported_access_features(self, feature):
        nfs_helper = mock.Mock()
        supported_access_feature = mock.Mock()
        setattr(nfs_helper, 'supported_access_%ss' % feature,
                supported_access_feature)
        self.mock_object(self._driver, 'nfs_helper', nfs_helper)

        ret = getattr(self._driver, 'supported_access_%ss' % feature)

        self.assertEqual(supported_access_feature, ret)

    def test_update_access_via_manager(self):
        self.mock_object(self._driver, '_get_helper')
        gmgr = mock.Mock()
        add_rules = mock.Mock()
        delete_rules = mock.Mock()

        self._driver._update_access_via_manager(
            gmgr, self._context, self.share,
            add_rules, delete_rules, recovery=True)

        self._driver._get_helper.assert_called_once_with(gmgr)
        self._driver._get_helper().update_access.assert_called_once_with(
            '/', self.share, add_rules, delete_rules, recovery=True)


@ddt.ddt
class GlusterNFSHelperTestCase(test.TestCase):
    """Tests GlusterNFSHelper."""

    def setUp(self):
        super(GlusterNFSHelperTestCase, self).setUp()
        fake_utils.stub_out_utils_execute(self)
        gluster_manager = mock.Mock(**fake_gluster_manager_attrs)
        self._execute = mock.Mock(return_value=('', ''))
        self.fake_conf = config.Configuration(None)
        self._helper = glusterfs.GlusterNFSHelper(
            self._execute, self.fake_conf, gluster_manager=gluster_manager)

    def test_get_export(self):
        ret = self._helper.get_export(mock.Mock())

        self.assertEqual(fake_gluster_manager_attrs['export'], ret)

    @ddt.data({'output_str': '/foo(10.0.0.1|10.0.0.2),/bar(10.0.0.1)',
               'expected': {'foo': ['10.0.0.1', '10.0.0.2'],
                            'bar': ['10.0.0.1']}},
              {'output_str': None, 'expected': {}})
    @ddt.unpack
    def test_get_export_dir_dict(self, output_str, expected):
        self.mock_object(self._helper.gluster_manager,
                         'get_vol_option',
                         mock.Mock(return_value=output_str))

        ret = self._helper._get_export_dir_dict()

        self.assertEqual(expected, ret)
        (self._helper.gluster_manager.get_vol_option.
         assert_called_once_with(NFS_EXPORT_DIR))

    @ddt.data({'delta': (['10.0.0.2'], []), 'extra_exports': {},
               'new_exports': '/fakename(10.0.0.1|10.0.0.2)'},
              {'delta': (['10.0.0.1'], []), 'extra_exports': {},
               'new_exports': '/fakename(10.0.0.1)'},
              {'delta': ([], ['10.0.0.2']), 'extra_exports': {},
               'new_exports': '/fakename(10.0.0.1)'},
              {'delta': ([], ['10.0.0.1']), 'extra_exports': {},
               'new_exports': None},
              {'delta': ([], ['10.0.0.1']),
               'extra_exports': {'elsewhere': ['10.0.1.3']},
               'new_exports': '/elsewhere(10.0.1.3)'})
    @ddt.unpack
    def test_update_access(self, delta, extra_exports, new_exports):
        gluster_manager_attrs = {'path': '/fakename'}
        gluster_manager_attrs.update(fake_gluster_manager_attrs)
        gluster_mgr = mock.Mock(**gluster_manager_attrs)
        helper = glusterfs.GlusterNFSHelper(
            self._execute, self.fake_conf, gluster_manager=gluster_mgr)
        export_dir_dict = {'fakename': ['10.0.0.1']}
        export_dir_dict.update(extra_exports)
        helper._get_export_dir_dict = mock.Mock(return_value=export_dir_dict)
        _share = mock.Mock()

        add_rules, delete_rules = (
            map(lambda a: {'access_to': a}, r) for r in delta)
        helper.update_access('/', _share, add_rules, delete_rules)

        helper._get_export_dir_dict.assert_called_once_with()
        gluster_mgr.set_vol_option.assert_called_once_with(NFS_EXPORT_DIR,
                                                           new_exports)

    @ddt.data({}, {'elsewhere': '10.0.1.3'})
    def test_update_access_disjoint(self, export_dir_dict):
        gluster_manager_attrs = {'path': '/fakename'}
        gluster_manager_attrs.update(fake_gluster_manager_attrs)
        gluster_mgr = mock.Mock(**gluster_manager_attrs)
        helper = glusterfs.GlusterNFSHelper(
            self._execute, self.fake_conf, gluster_manager=gluster_mgr)
        helper._get_export_dir_dict = mock.Mock(return_value=export_dir_dict)
        _share = mock.Mock()

        helper.update_access('/', _share, [], [{'access_to': '10.0.0.2'}])

        helper._get_export_dir_dict.assert_called_once_with()
        self.assertFalse(gluster_mgr.set_vol_option.called)


@ddt.ddt
class GlusterNFSVolHelperTestCase(test.TestCase):
    """Tests GlusterNFSVolHelper."""

    def setUp(self):
        super(GlusterNFSVolHelperTestCase, self).setUp()
        fake_utils.stub_out_utils_execute(self)
        gluster_manager = mock.Mock(**fake_gluster_manager_attrs)
        self._execute = mock.Mock(return_value=('', ''))
        self.fake_conf = config.Configuration(None)
        self._helper = glusterfs.GlusterNFSVolHelper(
            self._execute, self.fake_conf, gluster_manager=gluster_manager)

    @ddt.data({'output_str': '10.0.0.1,10.0.0.2',
               'expected': ['10.0.0.1', '10.0.0.2']},
              {'output_str': None, 'expected': []})
    @ddt.unpack
    def test_get_vol_exports(self, output_str, expected):
        self.mock_object(self._helper.gluster_manager,
                         'get_vol_option',
                         mock.Mock(return_value=output_str))

        ret = self._helper._get_vol_exports()

        self.assertEqual(expected, ret)
        (self._helper.gluster_manager.get_vol_option.
         assert_called_once_with(NFS_RPC_AUTH_ALLOW))

    @ddt.data({'delta': (["10.0.0.1"], []), 'expected': "10.0.0.1,10.0.0.3"},
              {'delta': (["10.0.0.2"], []),
               'expected': "10.0.0.1,10.0.0.2,10.0.0.3"},
              {'delta': ([], ["10.0.0.1"]), 'expected': "10.0.0.3"},
              {'delta': ([], ["10.0.0.2"]), 'expected': "10.0.0.1,10.0.0.3"})
    @ddt.unpack
    def test_update_access(self, delta, expected):
        self.mock_object(self._helper, '_get_vol_exports', mock.Mock(
            return_value=["10.0.0.1", "10.0.0.3"]))
        _share = mock.Mock()

        add_rules, delete_rules = (
            map(lambda a: {'access_to': a}, r) for r in delta)
        self._helper.update_access("/", _share, add_rules, delete_rules)

        self._helper._get_vol_exports.assert_called_once_with()
        argseq = [(NFS_RPC_AUTH_ALLOW, expected), (NFS_RPC_AUTH_REJECT, None)]
        self.assertEqual(
            [mock.call(*a) for a in argseq],
            self._helper.gluster_manager.set_vol_option.call_args_list)

    def test_update_access_empty(self):
        self.mock_object(self._helper, '_get_vol_exports', mock.Mock(
            return_value=["10.0.0.1"]))
        _share = mock.Mock()

        self._helper.update_access("/", _share, [],
                                   [{'access_to': "10.0.0.1"}])

        self._helper._get_vol_exports.assert_called_once_with()
        argseq = [(NFS_RPC_AUTH_ALLOW, None), (NFS_RPC_AUTH_REJECT, "*")]
        self.assertEqual(
            [mock.call(*a) for a in argseq],
            self._helper.gluster_manager.set_vol_option.call_args_list)


class GaneshaNFSHelperTestCase(test.TestCase):
    """Tests GaneshaNFSHelper."""

    def setUp(self):
        super(GaneshaNFSHelperTestCase, self).setUp()
        self.gluster_manager = mock.Mock(**fake_gluster_manager_attrs)
        self._execute = mock.Mock(return_value=('', ''))
        self._root_execute = mock.Mock(return_value=('', ''))
        self.access = fake_share.fake_access()
        self.fake_conf = config.Configuration(None)
        self.fake_template = {'key': 'value'}
        self.share = fake_share.fake_share()
        self.mock_object(glusterfs.ganesha_utils, 'RootExecutor',
                         mock.Mock(return_value=self._root_execute))
        self.mock_object(glusterfs.ganesha.GaneshaNASHelper, '__init__',
                         mock.Mock())
        socket.gethostname = mock.Mock(return_value='example.com')
        self._helper = glusterfs.GaneshaNFSHelper(
            self._execute, self.fake_conf,
            gluster_manager=self.gluster_manager)
        self._helper.tag = 'GLUSTER-Ganesha-localhost'

    def test_init_local_ganesha_server(self):
        glusterfs.ganesha_utils.RootExecutor.assert_called_once_with(
            self._execute)
        socket.gethostname.assert_has_calls([mock.call()])
        glusterfs.ganesha.GaneshaNASHelper.__init__.assert_has_calls(
            [mock.call(self._root_execute, self.fake_conf,
                       tag='GLUSTER-Ganesha-example.com')])

    def test_get_export(self):
        ret = self._helper.get_export(self.share)

        self.assertEqual('example.com:/fakename--<access-id>', ret)

    def test_init_remote_ganesha_server(self):
        ssh_execute = mock.Mock(return_value=('', ''))
        CONF.set_default('glusterfs_ganesha_server_ip', 'fakeip')
        self.mock_object(glusterfs.ganesha_utils, 'SSHExecutor',
                         mock.Mock(return_value=ssh_execute))
        glusterfs.GaneshaNFSHelper(
            self._execute, self.fake_conf,
            gluster_manager=self.gluster_manager)
        glusterfs.ganesha_utils.SSHExecutor.assert_called_once_with(
            'fakeip', 22, None, 'root', password=None, privatekey=None)
        glusterfs.ganesha.GaneshaNASHelper.__init__.assert_has_calls(
            [mock.call(ssh_execute, self.fake_conf,
                       tag='GLUSTER-Ganesha-fakeip')])

    def test_init_helper(self):
        ganeshelper = mock.Mock()
        exptemp = mock.Mock()

        def set_attributes(*a, **kw):
            self._helper.ganesha = ganeshelper
            self._helper.export_template = exptemp

        self.mock_object(ganesha.GaneshaNASHelper, 'init_helper',
                         mock.Mock(side_effect=set_attributes))
        self.assertEqual({}, glusterfs.GaneshaNFSHelper.shared_data)

        self._helper.init_helper()

        ganesha.GaneshaNASHelper.init_helper.assert_called_once_with()
        self.assertEqual(ganeshelper, self._helper.ganesha)
        self.assertEqual(exptemp, self._helper.export_template)
        self.assertEqual({
            'GLUSTER-Ganesha-localhost': {
                'ganesha': ganeshelper,
                'export_template': exptemp}},
            glusterfs.GaneshaNFSHelper.shared_data)

        other_helper = glusterfs.GaneshaNFSHelper(
            self._execute, self.fake_conf,
            gluster_manager=self.gluster_manager)
        other_helper.tag = 'GLUSTER-Ganesha-localhost'

        other_helper.init_helper()

        self.assertEqual(ganeshelper, other_helper.ganesha)
        self.assertEqual(exptemp, other_helper.export_template)

    def test_default_config_hook(self):
        fake_conf_dict = {'key': 'value1'}
        mock_ganesha_utils_patch = mock.Mock()

        def fake_patch_run(tmpl1, tmpl2):
            mock_ganesha_utils_patch(
                copy.deepcopy(tmpl1), tmpl2)
            tmpl1.update(tmpl2)

        self.mock_object(glusterfs.ganesha.GaneshaNASHelper,
                         '_default_config_hook',
                         mock.Mock(return_value=self.fake_template))
        self.mock_object(glusterfs.ganesha_utils, 'path_from',
                         mock.Mock(return_value='/fakedir/glusterfs/conf'))
        self.mock_object(self._helper, '_load_conf_dir',
                         mock.Mock(return_value=fake_conf_dict))
        self.mock_object(glusterfs.ganesha_utils, 'patch',
                         mock.Mock(side_effect=fake_patch_run))

        ret = self._helper._default_config_hook()

        glusterfs.ganesha.GaneshaNASHelper._default_config_hook.\
            assert_called_once_with()
        glusterfs.ganesha_utils.path_from.assert_called_once_with(
            glusterfs.__file__, 'conf')
        self._helper._load_conf_dir.assert_called_once_with(
            '/fakedir/glusterfs/conf')
        glusterfs.ganesha_utils.patch.assert_called_once_with(
            self.fake_template, fake_conf_dict)
        self.assertEqual(fake_conf_dict, ret)

    def test_fsal_hook(self):
        self._helper.gluster_manager.path = '/fakename'
        output = {
            'Hostname': '127.0.0.1',
            'Volume': 'testvol',
            'Volpath': '/fakename'
        }

        ret = self._helper._fsal_hook('/fakepath', self.share, self.access)

        self.assertEqual(output, ret)
