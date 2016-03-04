# Copyright 2014 Mirantis Inc.
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

import mock

from manila.network.linux import ip_lib
from manila import test

NETNS_SAMPLE = [
    '12345678-1234-5678-abcd-1234567890ab',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    'cccccccc-cccc-cccc-cccc-cccccccccccc']

LINK_SAMPLE = [
    '1: lo: <LOOPBACK,UP,LOWER_UP> mtu 16436 qdisc noqueue state UNKNOWN \\'
    'link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00',
    '2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP '
    'qlen 1000\    link/ether cc:dd:ee:ff:ab:cd brd ff:ff:ff:ff:ff:ff'
    '\    alias openvswitch',
    '3: br-int: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN '
    '\    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff',
    '4: gw-ddc717df-49: <BROADCAST,MULTICAST> mtu 1500 qdisc noop '
    'state DOWN \    link/ether fe:dc:ba:fe:dc:ba brd ff:ff:ff:ff:ff:ff',
    '5: eth0.50@eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc '
    ' noqueue master brq0b24798c-07 state UP mode DEFAULT'
    '\    link/ether ab:04:49:b6:ab:a0 brd ff:ff:ff:ff:ff:ff']

ADDR_SAMPLE = ("""
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP qlen 1000
    link/ether dd:cc:aa:b9:76:ce brd ff:ff:ff:ff:ff:ff
    inet 172.16.77.240/24 brd 172.16.77.255 scope global eth0
    inet6 2001:470:9:1224:5595:dd51:6ba2:e788/64 scope global temporary dynamic
       valid_lft 14187sec preferred_lft 3387sec
    inet6 2001:470:9:1224:fd91:272:581e:3a32/64 scope global temporary """
               """deprecated dynamic
       valid_lft 14187sec preferred_lft 0sec
    inet6 2001:470:9:1224:4508:b885:5fb:740b/64 scope global temporary """
               """deprecated dynamic
       valid_lft 14187sec preferred_lft 0sec
    inet6 2001:470:9:1224:dfcc:aaff:feb9:76ce/64 scope global dynamic
       valid_lft 14187sec preferred_lft 3387sec
    inet6 fe80::dfcc:aaff:feb9:76ce/64 scope link
       valid_lft forever preferred_lft forever
""")

ADDR_SAMPLE2 = ("""
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP qlen 1000
    link/ether dd:cc:aa:b9:76:ce brd ff:ff:ff:ff:ff:ff
    inet 172.16.77.240/24 scope global eth0
    inet6 2001:470:9:1224:5595:dd51:6ba2:e788/64 scope global temporary dynamic
       valid_lft 14187sec preferred_lft 3387sec
    inet6 2001:470:9:1224:fd91:272:581e:3a32/64 scope global temporary """
                """deprecated dynamic
       valid_lft 14187sec preferred_lft 0sec
    inet6 2001:470:9:1224:4508:b885:5fb:740b/64 scope global temporary """
                """deprecated dynamic
       valid_lft 14187sec preferred_lft 0sec
    inet6 2001:470:9:1224:dfcc:aaff:feb9:76ce/64 scope global dynamic
       valid_lft 14187sec preferred_lft 3387sec
    inet6 fe80::dfcc:aaff:feb9:76ce/64 scope link
       valid_lft forever preferred_lft forever
""")

GATEWAY_SAMPLE1 = ("""
default via 10.35.19.254  metric 100
10.35.16.0/22  proto kernel  scope link  src 10.35.17.97
""")

GATEWAY_SAMPLE2 = ("""
default via 10.35.19.254  metric 100
""")

GATEWAY_SAMPLE3 = ("""
10.35.16.0/22  proto kernel  scope link  src 10.35.17.97
""")

GATEWAY_SAMPLE4 = ("""
default via 10.35.19.254
""")

GATEWAY_SAMPLE5 = ("""
default        via 172.24.47.1 dev eth0
10.0.0.0/24    dev tapc226b810-a0  proto kernel  scope link  src 10.0.0.3
10.254.0.0/28  dev tap6de90453-1c  proto kernel  scope link  src 10.254.0.4
10.35.16.0/22  proto kernel  scope link  src 10.35.17.97
172.24.4.0/24  via 10.35.19.254  metric 100
""")

DEVICE_ROUTE_SAMPLE = ("10.0.0.0/24  scope link  src 10.0.0.2")

SUBNET_SAMPLE1 = ("10.0.0.0/24 dev qr-23380d11-d2  scope link  src 10.0.0.1\n"
                  "10.0.0.0/24 dev tap1d7888a7-10  scope link  src 10.0.0.2")
SUBNET_SAMPLE2 = ("10.0.0.0/24 dev tap1d7888a7-10  scope link  src 10.0.0.2\n"
                  "10.0.0.0/24 dev qr-23380d11-d2  scope link  src 10.0.0.1")


class TestSubProcessBase(test.TestCase):
    def setUp(self):
        super(TestSubProcessBase, self).setUp()
        self.execute_p = mock.patch('manila.utils.execute')
        self.execute = self.execute_p.start()

    def tearDown(self):
        self.execute_p.stop()
        super(TestSubProcessBase, self).tearDown()

    def test_execute_wrapper(self):
        ip_lib.SubProcessBase._execute('o', 'link', ('list',))

        self.execute.assert_called_once_with('ip', '-o', 'link', 'list',
                                             run_as_root=False)

    def test_execute_wrapper_int_options(self):
        ip_lib.SubProcessBase._execute([4], 'link', ('list',))

        self.execute.assert_called_once_with('ip', '-4', 'link', 'list',
                                             run_as_root=False)

    def test_execute_wrapper_no_options(self):
        ip_lib.SubProcessBase._execute([], 'link', ('list',))

        self.execute.assert_called_once_with('ip', 'link', 'list',
                                             run_as_root=False)

    def test_run_no_namespace(self):
        base = ip_lib.SubProcessBase()
        base._run([], 'link', ('list',))
        self.execute.assert_called_once_with('ip', 'link', 'list',
                                             run_as_root=False)

    def test_run_namespace(self):
        base = ip_lib.SubProcessBase('ns')
        base._run([], 'link', ('list',))
        self.execute.assert_called_once_with('ip', 'netns', 'exec', 'ns',
                                             'ip', 'link', 'list',
                                             run_as_root=True)

    def test_as_root_namespace(self):
        base = ip_lib.SubProcessBase('ns')
        base._as_root([], 'link', ('list',))
        self.execute.assert_called_once_with('ip', 'netns', 'exec', 'ns',
                                             'ip', 'link', 'list',
                                             run_as_root=True)


class TestIpWrapper(test.TestCase):
    def setUp(self):
        super(TestIpWrapper, self).setUp()
        self.execute_p = mock.patch.object(ip_lib.IPWrapper, '_execute')
        self.execute = self.execute_p.start()

    def tearDown(self):
        self.execute_p.stop()
        super(TestIpWrapper, self).tearDown()

    def test_get_devices(self):
        self.execute.return_value = '\n'.join(LINK_SAMPLE)
        retval = ip_lib.IPWrapper().get_devices()
        self.assertEqual([ip_lib.IPDevice('lo'),
                          ip_lib.IPDevice('eth0'),
                          ip_lib.IPDevice('br-int'),
                          ip_lib.IPDevice('gw-ddc717df-49'),
                          ip_lib.IPDevice('eth0.50')],
                         retval)

        self.execute.assert_called_once_with('o', 'link', ('list',), None)

    def test_get_devices_malformed_line(self):
        self.execute.return_value = '\n'.join(LINK_SAMPLE + ['gibberish'])
        retval = ip_lib.IPWrapper().get_devices()
        self.assertEqual([ip_lib.IPDevice('lo'),
                          ip_lib.IPDevice('eth0'),
                          ip_lib.IPDevice('br-int'),
                          ip_lib.IPDevice('gw-ddc717df-49'),
                          ip_lib.IPDevice('eth0.50')],
                         retval)

        self.execute.assert_called_once_with('o', 'link', ('list',), None)

    def test_get_namespaces(self):
        self.execute.return_value = '\n'.join(NETNS_SAMPLE)
        retval = ip_lib.IPWrapper.get_namespaces()
        self.assertEqual(['12345678-1234-5678-abcd-1234567890ab',
                          'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
                          'cccccccc-cccc-cccc-cccc-cccccccccccc'],
                         retval)

        self.execute.assert_called_once_with('', 'netns', ('list',))

    def test_add_tuntap(self):
        ip_lib.IPWrapper().add_tuntap('tap0')
        self.execute.assert_called_once_with('', 'tuntap',
                                             ('add', 'tap0', 'mode', 'tap'),
                                             None, as_root=True)

    def test_add_veth(self):
        ip_lib.IPWrapper().add_veth('tap0', 'tap1')
        self.execute.assert_called_once_with('', 'link',
                                             ('add', 'tap0', 'type', 'veth',
                                              'peer', 'name', 'tap1'),
                                             None, as_root=True)

    def test_add_veth_with_namespaces(self):
        ns2 = 'ns2'
        with mock.patch.object(ip_lib.IPWrapper, 'ensure_namespace') as en:
            ip_lib.IPWrapper().add_veth('tap0', 'tap1', namespace2=ns2)
            en.assert_has_calls([mock.call(ns2)])
        self.execute.assert_called_once_with('', 'link',
                                             ('add', 'tap0', 'type', 'veth',
                                              'peer', 'name', 'tap1',
                                              'netns', ns2),
                                             None, as_root=True)

    def test_get_device(self):
        dev = ip_lib.IPWrapper('ns').device('eth0')
        self.assertEqual('ns', dev.namespace)
        self.assertEqual('eth0', dev.name)

    def test_ensure_namespace(self):
        with mock.patch.object(ip_lib, 'IPDevice') as ip_dev:
            ip = ip_lib.IPWrapper()
            with mock.patch.object(ip.netns, 'exists') as ns_exists:
                ns_exists.return_value = False
                ip.ensure_namespace('ns')
                self.execute.assert_has_calls(
                    [mock.call([], 'netns', ('add', 'ns'), None,
                               as_root=True)])
                ip_dev.assert_has_calls([mock.call('lo', 'ns'),
                                         mock.call().link.set_up()])

    def test_ensure_namespace_existing(self):
        with mock.patch.object(ip_lib, 'IpNetnsCommand') as ip_ns_cmd:
            ip_ns_cmd.exists.return_value = True
            ns = ip_lib.IPWrapper().ensure_namespace('ns')
            self.assertFalse(self.execute.called)
            self.assertEqual('ns', ns.namespace)

    def test_namespace_is_empty_no_devices(self):
        ip = ip_lib.IPWrapper('ns')
        with mock.patch.object(ip, 'get_devices') as get_devices:
            get_devices.return_value = []

            self.assertTrue(ip.namespace_is_empty())
            get_devices.assert_called_once_with(exclude_loopback=True)

    def test_namespace_is_empty(self):
        ip = ip_lib.IPWrapper('ns')
        with mock.patch.object(ip, 'get_devices') as get_devices:
            get_devices.return_value = [mock.Mock()]

            self.assertFalse(ip.namespace_is_empty())
            get_devices.assert_called_once_with(exclude_loopback=True)

    def test_garbage_collect_namespace_does_not_exist(self):
        with mock.patch.object(ip_lib, 'IpNetnsCommand') as ip_ns_cmd_cls:
            ip_ns_cmd_cls.return_value.exists.return_value = False
            ip = ip_lib.IPWrapper('ns')
            with mock.patch.object(ip, 'namespace_is_empty') as mock_is_empty:
                self.assertFalse(ip.garbage_collect_namespace())
                ip_ns_cmd_cls.assert_has_calls([mock.call().exists('ns')])
                self.assertNotIn(mock.call().delete('ns'),
                                 ip_ns_cmd_cls.return_value.mock_calls)
                self.assertEqual([], mock_is_empty.mock_calls)

    def test_garbage_collect_namespace_existing_empty_ns(self):
        with mock.patch.object(ip_lib, 'IpNetnsCommand') as ip_ns_cmd_cls:
            ip_ns_cmd_cls.return_value.exists.return_value = True

            ip = ip_lib.IPWrapper('ns')

            with mock.patch.object(ip, 'namespace_is_empty') as mock_is_empty:
                mock_is_empty.return_value = True
                self.assertTrue(ip.garbage_collect_namespace())

                mock_is_empty.assert_called_once_with()
                expected = [mock.call().exists('ns'),
                            mock.call().delete('ns')]
                ip_ns_cmd_cls.assert_has_calls(expected)

    def test_garbage_collect_namespace_existing_not_empty(self):
        lo_device = mock.Mock()
        lo_device.name = 'lo'
        tap_device = mock.Mock()
        tap_device.name = 'tap1'

        with mock.patch.object(ip_lib, 'IpNetnsCommand') as ip_ns_cmd_cls:
            ip_ns_cmd_cls.return_value.exists.return_value = True

            ip = ip_lib.IPWrapper('ns')

            with mock.patch.object(ip, 'namespace_is_empty') as mock_is_empty:
                mock_is_empty.return_value = False

                self.assertFalse(ip.garbage_collect_namespace())

                mock_is_empty.assert_called_once_with()
                expected = [mock.call(ip),
                            mock.call().exists('ns')]
                self.assertEqual(expected, ip_ns_cmd_cls.mock_calls)
                self.assertNotIn(mock.call().delete('ns'),
                                 ip_ns_cmd_cls.mock_calls)

    def test_add_device_to_namespace(self):
        dev = mock.Mock()
        ip_lib.IPWrapper('ns').add_device_to_namespace(dev)
        dev.assert_has_calls([mock.call.link.set_netns('ns')])

    def test_add_device_to_namespace_is_none(self):
        dev = mock.Mock()
        ip_lib.IPWrapper().add_device_to_namespace(dev)
        self.assertEqual([], dev.mock_calls)


class TestIPDevice(test.TestCase):
    def test_eq_same_name(self):
        dev1 = ip_lib.IPDevice('tap0')
        dev2 = ip_lib.IPDevice('tap0')
        self.assertEqual(dev1, dev2)

    def test_eq_diff_name(self):
        dev1 = ip_lib.IPDevice('tap0')
        dev2 = ip_lib.IPDevice('tap1')
        self.assertNotEqual(dev1, dev2)

    def test_eq_same_namespace(self):
        dev1 = ip_lib.IPDevice('tap0', 'ns1')
        dev2 = ip_lib.IPDevice('tap0', 'ns1')
        self.assertEqual(dev1, dev2)

    def test_eq_diff_namespace(self):
        dev1 = ip_lib.IPDevice('tap0', 'ns1')
        dev2 = ip_lib.IPDevice('tap0', 'ns2')
        self.assertNotEqual(dev1, dev2)

    def test_eq_other_is_none(self):
        dev1 = ip_lib.IPDevice('tap0', 'ns1')
        self.assertIsNotNone(dev1)

    def test_str(self):
        self.assertEqual('tap0', str(ip_lib.IPDevice('tap0')))


class TestIPCommandBase(test.TestCase):
    def setUp(self):
        super(TestIPCommandBase, self).setUp()
        self.ip = mock.Mock()
        self.ip.namespace = 'namespace'
        self.ip_cmd = ip_lib.IpCommandBase(self.ip)
        self.ip_cmd.COMMAND = 'foo'

    def test_run(self):
        self.ip_cmd._run('link', 'show')
        self.ip.assert_has_calls([mock.call._run([], 'foo', ('link', 'show'))])

    def test_run_with_options(self):
        self.ip_cmd._run('link', options='o')
        self.ip.assert_has_calls([mock.call._run('o', 'foo', ('link', ))])

    def test_as_root(self):
        self.ip_cmd._as_root('link')
        self.ip.assert_has_calls(
            [mock.call._as_root([], 'foo', ('link', ), False)])

    def test_as_root_with_options(self):
        self.ip_cmd._as_root('link', options='o')
        self.ip.assert_has_calls(
            [mock.call._as_root('o', 'foo', ('link', ), False)])


class TestIPDeviceCommandBase(test.TestCase):
    def setUp(self):
        super(TestIPDeviceCommandBase, self).setUp()
        self.ip_dev = mock.Mock()
        self.ip_dev.name = 'eth0'
        self.ip_dev._execute = mock.Mock(return_value='executed')
        self.ip_cmd = ip_lib.IpDeviceCommandBase(self.ip_dev)
        self.ip_cmd.COMMAND = 'foo'

    def test_name_property(self):
        self.assertEqual('eth0', self.ip_cmd.name)


class TestIPCmdBase(test.TestCase):
    def setUp(self):
        super(TestIPCmdBase, self).setUp()
        self.parent = mock.Mock()
        self.parent.name = 'eth0'

    def _assert_call(self, options, args):
        self.parent.assert_has_calls([
            mock.call._run(options, self.command, args)])

    def _assert_sudo(self, options, args, force_root_namespace=False):
        self.parent.assert_has_calls(
            [mock.call._as_root(options, self.command, args,
                                force_root_namespace)])


class TestIpLinkCommand(TestIPCmdBase):
    def setUp(self):
        super(TestIpLinkCommand, self).setUp()
        self.parent._run.return_value = LINK_SAMPLE[1]
        self.command = 'link'
        self.link_cmd = ip_lib.IpLinkCommand(self.parent)

    def test_set_address(self):
        self.link_cmd.set_address('aa:bb:cc:dd:ee:ff')
        self._assert_sudo([], ('set', 'eth0', 'address', 'aa:bb:cc:dd:ee:ff'))

    def test_set_mtu(self):
        self.link_cmd.set_mtu(1500)
        self._assert_sudo([], ('set', 'eth0', 'mtu', 1500))

    def test_set_up(self):
        self.link_cmd.set_up()
        self._assert_sudo([], ('set', 'eth0', 'up'))

    def test_set_down(self):
        self.link_cmd.set_down()
        self._assert_sudo([], ('set', 'eth0', 'down'))

    def test_set_netns(self):
        self.link_cmd.set_netns('foo')
        self._assert_sudo([], ('set', 'eth0', 'netns', 'foo'))
        self.assertEqual('foo', self.parent.namespace)

    def test_set_name(self):
        self.link_cmd.set_name('tap1')
        self._assert_sudo([], ('set', 'eth0', 'name', 'tap1'))
        self.assertEqual('tap1', self.parent.name)

    def test_set_alias(self):
        self.link_cmd.set_alias('openvswitch')
        self._assert_sudo([], ('set', 'eth0', 'alias', 'openvswitch'))

    def test_delete(self):
        self.link_cmd.delete()
        self._assert_sudo([], ('delete', 'eth0'))

    def test_address_property(self):
        self.parent._execute = mock.Mock(return_value=LINK_SAMPLE[1])
        self.assertEqual('cc:dd:ee:ff:ab:cd', self.link_cmd.address)

    def test_mtu_property(self):
        self.parent._execute = mock.Mock(return_value=LINK_SAMPLE[1])
        self.assertEqual(1500, self.link_cmd.mtu)

    def test_qdisc_property(self):
        self.parent._execute = mock.Mock(return_value=LINK_SAMPLE[1])
        self.assertEqual('mq', self.link_cmd.qdisc)

    def test_qlen_property(self):
        self.parent._execute = mock.Mock(return_value=LINK_SAMPLE[1])
        self.assertEqual(1000, self.link_cmd.qlen)

    def test_alias_property(self):
        self.parent._execute = mock.Mock(return_value=LINK_SAMPLE[1])
        self.assertEqual('openvswitch', self.link_cmd.alias)

    def test_state_property(self):
        self.parent._execute = mock.Mock(return_value=LINK_SAMPLE[1])
        self.assertEqual('UP', self.link_cmd.state)

    def test_settings_property(self):
        expected = {'mtu': 1500,
                    'qlen': 1000,
                    'state': 'UP',
                    'qdisc': 'mq',
                    'brd': 'ff:ff:ff:ff:ff:ff',
                    'link/ether': 'cc:dd:ee:ff:ab:cd',
                    'alias': 'openvswitch'}
        self.parent._execute = mock.Mock(return_value=LINK_SAMPLE[1])
        self.assertEqual(expected, self.link_cmd.attributes)
        self._assert_call('o', ('show', 'eth0'))


class TestIpAddrCommand(TestIPCmdBase):
    def setUp(self):
        super(TestIpAddrCommand, self).setUp()
        self.parent.name = 'tap0'
        self.command = 'addr'
        self.addr_cmd = ip_lib.IpAddrCommand(self.parent)

    def test_add_address(self):
        self.addr_cmd.add(4, '192.168.45.100/24', '192.168.45.255')
        self._assert_sudo([4],
                          ('add', '192.168.45.100/24', 'brd', '192.168.45.255',
                           'scope', 'global', 'dev', 'tap0'))

    def test_add_address_scoped(self):
        self.addr_cmd.add(4, '192.168.45.100/24', '192.168.45.255',
                          scope='link')
        self._assert_sudo([4],
                          ('add', '192.168.45.100/24', 'brd', '192.168.45.255',
                           'scope', 'link', 'dev', 'tap0'))

    def test_del_address(self):
        self.addr_cmd.delete(4, '192.168.45.100/24')
        self._assert_sudo([4],
                          ('del', '192.168.45.100/24', 'dev', 'tap0'))

    def test_flush(self):
        self.addr_cmd.flush()
        self._assert_sudo([], ('flush', 'tap0'))

    def test_list(self):
        expected = [
            dict(ip_version=4, scope='global',
                 dynamic=False, cidr='172.16.77.240/24',
                 broadcast='172.16.77.255'),
            dict(ip_version=6, scope='global',
                 dynamic=True, cidr='2001:470:9:1224:5595:dd51:6ba2:e788/64',
                 broadcast='::'),
            dict(ip_version=6, scope='global',
                 dynamic=True, cidr='2001:470:9:1224:fd91:272:581e:3a32/64',
                 broadcast='::'),
            dict(ip_version=6, scope='global',
                 dynamic=True, cidr='2001:470:9:1224:4508:b885:5fb:740b/64',
                 broadcast='::'),
            dict(ip_version=6, scope='global',
                 dynamic=True, cidr='2001:470:9:1224:dfcc:aaff:feb9:76ce/64',
                 broadcast='::'),
            dict(ip_version=6, scope='link',
                 dynamic=False, cidr='fe80::dfcc:aaff:feb9:76ce/64',
                 broadcast='::')]

        test_cases = [ADDR_SAMPLE, ADDR_SAMPLE2]

        for test_case in test_cases:
            self.parent._run = mock.Mock(return_value=test_case)
            self.assertEqual(expected, self.addr_cmd.list())
            self._assert_call([], ('show', 'tap0'))

    def test_list_filtered(self):
        expected = [
            dict(ip_version=4, scope='global',
                 dynamic=False, cidr='172.16.77.240/24',
                 broadcast='172.16.77.255')]

        test_cases = [ADDR_SAMPLE, ADDR_SAMPLE2]

        for test_case in test_cases:
            output = '\n'.join(test_case.split('\n')[0:4])
            self.parent._run.return_value = output
            self.assertEqual(expected, self.addr_cmd.list('global',
                             filters=['permanent']))
            self._assert_call([], ('show', 'tap0', 'permanent', 'scope',
                              'global'))


class TestIpRouteCommand(TestIPCmdBase):
    def setUp(self):
        super(TestIpRouteCommand, self).setUp()
        self.parent.name = 'eth0'
        self.command = 'route'
        self.route_cmd = ip_lib.IpRouteCommand(self.parent)

    def test_add_gateway(self):
        gateway = '192.168.45.100'
        metric = 100
        self.route_cmd.add_gateway(gateway, metric)
        self._assert_sudo([],
                          ('replace', 'default', 'via', gateway,
                           'metric', metric,
                           'dev', self.parent.name))

    def test_del_gateway(self):
        gateway = '192.168.45.100'
        self.route_cmd.delete_gateway(gateway)
        self._assert_sudo([],
                          ('del', 'default', 'via', gateway,
                           'dev', self.parent.name))

    def test_get_gateway(self):
        test_cases = [{'sample': GATEWAY_SAMPLE1,
                       'expected': {'gateway': '10.35.19.254',
                                    'metric': 100}},
                      {'sample': GATEWAY_SAMPLE2,
                       'expected': {'gateway': '10.35.19.254',
                                    'metric': 100}},
                      {'sample': GATEWAY_SAMPLE3,
                       'expected': None},
                      {'sample': GATEWAY_SAMPLE4,
                       'expected': {'gateway': '10.35.19.254'}}]
        for test_case in test_cases:
            self.parent._run = mock.Mock(return_value=test_case['sample'])
            self.assertEqual(test_case['expected'],
                             self.route_cmd.get_gateway())

    def test_pullup_route(self):
        # interface is not the first in the list - requires
        # deleting and creating existing entries
        output = [DEVICE_ROUTE_SAMPLE, SUBNET_SAMPLE1]

        def pullup_side_effect(self, *args):
            result = output.pop(0)
            return result

        self.parent._run = mock.Mock(side_effect=pullup_side_effect)
        self.route_cmd.pullup_route('tap1d7888a7-10')
        self._assert_sudo([], ('del', '10.0.0.0/24', 'dev', 'qr-23380d11-d2'))
        self._assert_sudo([], ('append', '10.0.0.0/24', 'proto', 'kernel',
                               'src', '10.0.0.1', 'dev', 'qr-23380d11-d2'))

    def test_pullup_route_first(self):
        # interface is first in the list - no changes
        output = [DEVICE_ROUTE_SAMPLE, SUBNET_SAMPLE2]

        def pullup_side_effect(self, *args):
            result = output.pop(0)
            return result

        self.parent._run = mock.Mock(side_effect=pullup_side_effect)
        self.route_cmd.pullup_route('tap1d7888a7-10')
        # Check two calls - device get and subnet get
        self.assertEqual(2, len(self.parent._run.mock_calls))

    def test_list(self):
        self.route_cmd._as_root = mock.Mock(return_value=GATEWAY_SAMPLE5)
        expected = [{'Destination': 'default',
                     'Device': 'eth0',
                     'Gateway': '172.24.47.1'},
                    {'Destination': '10.0.0.0/24',
                     'Device': 'tapc226b810-a0'},
                    {'Destination': '10.254.0.0/28',
                     'Device': 'tap6de90453-1c'},
                    {'Destination': '10.35.16.0/22'},
                    {'Destination': '172.24.4.0/24',
                     'Gateway': '10.35.19.254'}]
        result = self.route_cmd.list()
        self.assertEqual(expected, result)
        self.route_cmd._as_root.assert_called_once_with('list')

    def test_delete_net_route(self):
        self.route_cmd._as_root = mock.Mock()
        self.route_cmd.delete_net_route('10.0.0.0/24', 'br-ex')
        self.route_cmd._as_root.assert_called_once_with(
            'delete', '10.0.0.0/24', 'dev', 'br-ex')

    def test_clear_outdated_routes(self):
        self.route_cmd.delete_net_route = mock.Mock()
        list_result = [{'Destination': 'default',
                        'Device': 'eth0',
                        'Gateway': '172.24.47.1'},
                       {'Destination': '10.0.0.0/24',
                        'Device': 'eth0'},
                       {'Destination': '10.0.0.0/24',
                        'Device': 'br-ex'}]
        self.route_cmd.list = mock.Mock(return_value=list_result)
        self.route_cmd.clear_outdated_routes('10.0.0.0/24')
        self.route_cmd.delete_net_route.assert_called_once_with(
            '10.0.0.0/24', 'br-ex')


class TestIpNetnsCommand(TestIPCmdBase):
    def setUp(self):
        super(TestIpNetnsCommand, self).setUp()
        self.command = 'netns'
        self.netns_cmd = ip_lib.IpNetnsCommand(self.parent)

    def test_add_namespace(self):
        ns = self.netns_cmd.add('ns')
        self._assert_sudo([], ('add', 'ns'), force_root_namespace=True)
        self.assertEqual('ns', ns.namespace)

    def test_delete_namespace(self):
        with mock.patch('manila.utils.execute'):
            self.netns_cmd.delete('ns')
            self._assert_sudo([], ('delete', 'ns'), force_root_namespace=True)

    def test_namespace_exists(self):
        retval = '\n'.join(NETNS_SAMPLE)
        self.parent._as_root.return_value = retval
        self.assertTrue(
            self.netns_cmd.exists('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'))
        self._assert_sudo('o', ('list',), force_root_namespace=True)

    def test_namespace_doest_not_exist(self):
        retval = '\n'.join(NETNS_SAMPLE)
        self.parent._as_root.return_value = retval
        self.assertFalse(
            self.netns_cmd.exists('bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb'))
        self._assert_sudo('o', ('list',), force_root_namespace=True)

    def test_execute(self):
        self.parent.namespace = 'ns'
        with mock.patch('manila.utils.execute') as execute:
            self.netns_cmd.execute(['ip', 'link', 'list'])
            execute.assert_called_once_with('ip', 'netns', 'exec', 'ns', 'ip',
                                            'link', 'list',
                                            run_as_root=True,
                                            check_exit_code=True)

    def test_execute_env_var_prepend(self):
        self.parent.namespace = 'ns'
        with mock.patch('manila.utils.execute') as execute:
            env = dict(FOO=1, BAR=2)
            self.netns_cmd.execute(['ip', 'link', 'list'], env)
            execute.assert_called_once_with(
                'ip', 'netns', 'exec', 'ns', 'env', 'BAR=2', 'FOO=1',
                'ip', 'link', 'list',
                run_as_root=True, check_exit_code=True)


class TestDeviceExists(test.TestCase):
    def test_device_exists(self):
        with mock.patch.object(ip_lib.IPDevice, '_execute') as _execute:
            _execute.return_value = LINK_SAMPLE[1]
            self.assertTrue(ip_lib.device_exists('eth0'))
            _execute.assert_called_once_with('o', 'link', ('show', 'eth0'))

    def test_device_does_not_exist(self):
        with mock.patch.object(ip_lib.IPDevice, '_execute') as _execute:
            _execute.return_value = ''
            _execute.side_effect = RuntimeError('Device does not exist.')
            self.assertFalse(ip_lib.device_exists('eth0'))
