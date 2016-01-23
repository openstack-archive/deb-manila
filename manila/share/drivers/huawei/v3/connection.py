# Copyright (c) 2015 Huawei Technologies Co., Ltd.
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

import random
import string
import time

from oslo_log import log
from oslo_serialization import jsonutils
from oslo_utils import strutils
from oslo_utils import units

from manila.common import constants as common_constants
from manila import exception
from manila.i18n import _
from manila.i18n import _LI
from manila.i18n import _LW
from manila.share.drivers.huawei import base as driver
from manila.share.drivers.huawei import constants
from manila.share.drivers.huawei import huawei_utils
from manila.share.drivers.huawei.v3 import helper
from manila.share.drivers.huawei.v3 import smartx
from manila.share import share_types
from manila.share import utils as share_utils
from manila import utils

LOG = log.getLogger(__name__)


class V3StorageConnection(driver.HuaweiBase):
    """Helper class for Huawei OceanStor V3 storage system."""

    def __init__(self, configuration):
        super(V3StorageConnection, self).__init__(configuration)

    def connect(self):
        """Try to connect to V3 server."""
        if self.configuration:
            self.helper = helper.RestHelper(self.configuration)
        else:
            raise exception.InvalidInput(_("Huawei configuration missing."))
        self.helper.login()

    def create_share(self, share, share_server=None):
        """Create a share."""
        share_name = share['name']
        share_proto = share['share_proto']

        pool_name = share_utils.extract_host(share['host'], level='pool')

        if not pool_name:
            msg = _("Pool is not available in the share host field.")
            raise exception.InvalidHost(reason=msg)

        result = self.helper._find_all_pool_info()
        poolinfo = self.helper._find_pool_info(pool_name, result)
        if not poolinfo:
            msg = (_("Can not find pool info by pool name: %s") % pool_name)
            raise exception.InvalidHost(reason=msg)

        fs_id = None
        # We sleep here to ensure the newly created filesystem can be read.
        wait_interval = self._get_wait_interval()
        timeout = self._get_timeout()

        try:
            fs_id = self.allocate_container(share, poolinfo)
            fs = self.helper._get_fs_info_by_id(fs_id)
            end_time = time.time() + timeout

            while not (self.check_fs_status(fs['HEALTHSTATUS'],
                                            fs['RUNNINGSTATUS'])
                       or time.time() > end_time):
                time.sleep(wait_interval)
                fs = self.helper._get_fs_info_by_id(fs_id)

            if not self.check_fs_status(fs['HEALTHSTATUS'],
                                        fs['RUNNINGSTATUS']):
                raise exception.InvalidShare(
                    reason=(_('Invalid status of filesystem: %(health)s '
                              '%(running)s.')
                            % {'health': fs['HEALTHSTATUS'],
                               'running': fs['RUNNINGSTATUS']}))
        except Exception as err:
            if fs_id is not None:
                qos_id = self.helper.get_qosid_by_fsid(fs_id)
                if qos_id:
                    self.remove_qos_fs(fs_id, qos_id)
                self.helper._delete_fs(fs_id)
            message = (_('Failed to create share %(name)s.'
                         'Reason: %(err)s.')
                       % {'name': share_name,
                          'err': err})
            raise exception.InvalidShare(reason=message)

        try:
            self.helper._create_share(share_name, fs_id, share_proto)
        except Exception as err:
            if fs_id is not None:
                qos_id = self.helper.get_qosid_by_fsid(fs_id)
                if qos_id:
                    self.remove_qos_fs(fs_id, qos_id)
                self.helper._delete_fs(fs_id)
            raise exception.InvalidShare(
                reason=(_('Failed to create share %(name)s. Reason: %(err)s.')
                        % {'name': share_name, 'err': err}))

        ip = self._get_share_ip(share_server)
        location = self._get_location_path(share_name, share_proto, ip)
        return location

    def _get_share_ip(self, share_server):
        """"Get share logical ip."""
        if share_server:
            ip = share_server['backend_details'].get('ip')
        else:
            root = self.helper._read_xml()
            ip = root.findtext('Storage/LogicalPortIP').strip()

        return ip

    def extend_share(self, share, new_size, share_server):
        share_proto = share['share_proto']
        share_name = share['name']

        # The unit is in sectors.
        size = int(new_size) * units.Mi * 2
        share_url_type = self.helper._get_share_url_type(share_proto)

        share = self.helper._get_share_by_name(share_name, share_url_type)
        if not share:
            err_msg = (_("Can not get share ID by share %s.")
                       % share_name)
            LOG.error(err_msg)
            raise exception.InvalidShareAccess(reason=err_msg)

        fsid = share['FSID']
        fs_info = self.helper._get_fs_info_by_id(fsid)

        current_size = int(fs_info['CAPACITY']) / units.Mi / 2
        if current_size > new_size:
            err_msg = (_("New size for extend must be equal or bigger than "
                         "current size on array. (current: %(size)s, "
                         "new: %(new_size)s).")
                       % {'size': current_size, 'new_size': new_size})

            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)
        self.helper._change_share_size(fsid, size)

    def shrink_share(self, share, new_size, share_server):
        """Shrinks size of existing share."""
        share_proto = share['share_proto']
        share_name = share['name']

        # The unit is in sectors.
        size = int(new_size) * units.Mi * 2
        share_url_type = self.helper._get_share_url_type(share_proto)

        share = self.helper._get_share_by_name(share_name, share_url_type)
        if not share:
            err_msg = (_("Can not get share ID by share %s.")
                       % share_name)
            LOG.error(err_msg)
            raise exception.InvalidShare(reason=err_msg)

        fsid = share['FSID']
        fs_info = self.helper._get_fs_info_by_id(fsid)
        if not fs_info:
            err_msg = (_("Can not get filesystem info by filesystem ID: %s.")
                       % fsid)
            LOG.error(err_msg)
            raise exception.InvalidShare(reason=err_msg)

        current_size = int(fs_info['CAPACITY']) / units.Mi / 2
        if current_size < new_size:
            err_msg = (_("New size for shrink must be less than current "
                         "size on array. (current: %(size)s, "
                         "new: %(new_size)s).")
                       % {'size': current_size, 'new_size': new_size})
            LOG.error(err_msg)
            raise exception.InvalidShare(reason=err_msg)

        if fs_info['ALLOCTYPE'] != constants.ALLOC_TYPE_THIN_FLAG:
            err_msg = (_("Share (%s) can not be shrunk. only 'Thin' shares "
                         "support shrink.")
                       % share_name)
            LOG.error(err_msg)
            raise exception.InvalidShare(reason=err_msg)

        self.helper._change_share_size(fsid, size)

    def check_fs_status(self, health_status, running_status):
        if (health_status == constants.STATUS_FS_HEALTH
                and running_status == constants.STATUS_FS_RUNNING):
            return True
        else:
            return False

    def assert_filesystem(self, fsid):
        fs = self.helper._get_fs_info_by_id(fsid)
        if not self.check_fs_status(fs['HEALTHSTATUS'],
                                    fs['RUNNINGSTATUS']):
            err_msg = (_('Invalid status of filesystem: '
                         'HEALTHSTATUS=%(health)s '
                         'RUNNINGSTATUS=%(running)s.')
                       % {'health': fs['HEALTHSTATUS'],
                          'running': fs['RUNNINGSTATUS']})
            raise exception.StorageResourceException(reason=err_msg)

    def create_snapshot(self, snapshot, share_server=None):
        """Create a snapshot."""
        snap_name = snapshot['id']
        share_proto = snapshot['share']['share_proto']

        share_url_type = self.helper._get_share_url_type(share_proto)
        share = self.helper._get_share_by_name(snapshot['share_name'],
                                               share_url_type)

        if not share:
            err_msg = _('Can not create snapshot,'
                        ' because share id is not provided.')
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

        sharefsid = share['FSID']
        snapshot_name = "share_snapshot_" + snap_name
        snap_id = self.helper._create_snapshot(sharefsid,
                                               snapshot_name)
        LOG.info(_LI('Creating snapshot id %s.'), snap_id)

    def delete_snapshot(self, snapshot, share_server=None):
        """Delete a snapshot."""
        LOG.debug("Delete a snapshot.")
        snap_name = snapshot['id']

        sharefsid = self.helper._get_fsid_by_name(snapshot['share_name'])

        if sharefsid is None:
            LOG.warning(_LW('Delete snapshot share id %s fs has been '
                        'deleted.'), snap_name)
            return

        snapshot_id = self.helper._get_snapshot_id(sharefsid, snap_name)
        snapshot_flag = self.helper._check_snapshot_id_exist(snapshot_id)

        if snapshot_flag:
            self.helper._delete_snapshot(snapshot_id)
        else:
            LOG.warning(_LW("Can not find snapshot %s on array."), snap_name)

    def update_share_stats(self, stats_dict):
        """Retrieve status info from share group."""
        root = self.helper._read_xml()
        all_pool_info = self.helper._find_all_pool_info()
        stats_dict["pools"] = []

        pool_name_list = root.findtext('Filesystem/StoragePool')
        pool_name_list = pool_name_list.split(";")
        for pool_name in pool_name_list:
            pool_name = pool_name.strip().strip('\n')
            capacity = self._get_capacity(pool_name, all_pool_info)
            if capacity:
                pool = dict(
                    pool_name=pool_name,
                    total_capacity_gb=capacity['TOTALCAPACITY'],
                    free_capacity_gb=capacity['CAPACITY'],
                    provisioned_capacity_gb=(
                        capacity['PROVISIONEDCAPACITYGB']),
                    max_over_subscription_ratio=(
                        self.configuration.safe_get(
                            'max_over_subscription_ratio')),
                    allocated_capacity_gb=capacity['CONSUMEDCAPACITY'],
                    qos=True,
                    reserved_percentage=0,
                    thin_provisioning=[True, False],
                    dedupe=[True, False],
                    compression=[True, False],
                    huawei_smartcache=[True, False],
                    huawei_smartpartition=[True, False],
                )
                stats_dict["pools"].append(pool)

        if not stats_dict["pools"]:
            err_msg = _("The StoragePool is None.")
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

    def delete_share(self, share, share_server=None):
        """Delete share."""
        share_name = share['name']
        share_url_type = self.helper._get_share_url_type(share['share_proto'])
        share = self.helper._get_share_by_name(share_name, share_url_type)

        if not share:
            LOG.warning(_LW('The share was not found. Share name:%s'),
                        share_name)
            fsid = self.helper._get_fsid_by_name(share_name)
            if fsid:
                self.helper._delete_fs(fsid)
                return
            LOG.warning(_LW('The filesystem was not found.'))
            return

        share_id = share['ID']
        share_fs_id = share['FSID']

        if share_id:
            self.helper._delete_share_by_id(share_id, share_url_type)

        if share_fs_id:
            qos_id = self.helper.get_qosid_by_fsid(share_fs_id)
            if qos_id:
                self.remove_qos_fs(share_fs_id, qos_id)
            self.helper._delete_fs(share_fs_id)

        return share

    def get_network_allocations_number(self):
        """Get number of network interfaces to be created."""
        if self.configuration.driver_handles_share_servers:
            return constants.IP_ALLOCATIONS_DHSS_TRUE
        else:
            return constants.IP_ALLOCATIONS_DHSS_FALSE

    def _get_capacity(self, pool_name, result):
        """Get free capacity and total capacity of the pools."""
        poolinfo = self.helper._find_pool_info(pool_name, result)

        if poolinfo:
            total = float(poolinfo['TOTALCAPACITY']) / units.Mi / 2
            free = float(poolinfo['CAPACITY']) / units.Mi / 2
            consumed = float(poolinfo['CONSUMEDCAPACITY']) / units.Mi / 2
            poolinfo['TOTALCAPACITY'] = total
            poolinfo['CAPACITY'] = free
            poolinfo['CONSUMEDCAPACITY'] = consumed
            poolinfo['PROVISIONEDCAPACITYGB'] = round(
                float(total) - float(free), 2)

        return poolinfo

    def _init_filesys_para(self, share, poolinfo, extra_specs):
        """Init basic filesystem parameters."""
        name = share['name']
        size = int(share['size']) * units.Mi * 2
        fileparam = {
            "NAME": name.replace("-", "_"),
            "DESCRIPTION": "",
            "ALLOCTYPE": constants.ALLOC_TYPE_THIN_FLAG,
            "CAPACITY": size,
            "PARENTID": poolinfo['ID'],
            "INITIALALLOCCAPACITY": units.Ki * 20,
            "PARENTTYPE": 216,
            "SNAPSHOTRESERVEPER": 20,
            "INITIALDISTRIBUTEPOLICY": 0,
            "ISSHOWSNAPDIR": True,
            "RECYCLESWITCH": 0,
            "RECYCLEHOLDTIME": 15,
            "RECYCLETHRESHOLD": 0,
            "RECYCLEAUTOCLEANSWITCH": 0,
            "ENABLEDEDUP": extra_specs['dedupe'],
            "ENABLECOMPRESSION": extra_specs['compression'],
        }

        if 'LUNType' in extra_specs:
            fileparam['ALLOCTYPE'] = extra_specs['LUNType']
        else:
            root = self.helper._read_xml()
            fstype = root.findtext('Filesystem/AllocType')
            if fstype:
                fstype = fstype.strip().strip('\n')
                if fstype == 'Thin':
                    fileparam['ALLOCTYPE'] = constants.ALLOC_TYPE_THIN_FLAG
                elif fstype == 'Thick':
                    fileparam['ALLOCTYPE'] = constants.ALLOC_TYPE_THICK_FLAG
                else:
                    err_msg = (_(
                        'Config file is wrong. AllocType type must be set to'
                        ' "Thin" or "Thick". AllocType:%(fetchtype)s') %
                        {'fetchtype': fstype})
                    LOG.error(err_msg)
                    raise exception.InvalidShare(reason=err_msg)

        if fileparam['ALLOCTYPE'] == 0:
            if (extra_specs['dedupe'] or
                    extra_specs['compression']):
                err_msg = _(
                    'The filesystem type is "Thick",'
                    ' so dedupe or compression cannot be set.')
                LOG.error(err_msg)
                raise exception.InvalidInput(reason=err_msg)

        return fileparam

    def deny_access(self, share, access, share_server=None):
        """Deny access to share."""
        share_proto = share['share_proto']
        share_name = share['name']
        share_url_type = self.helper._get_share_url_type(share_proto)
        share_client_type = self.helper._get_share_client_type(share_proto)
        access_type = access['access_type']
        if share_proto == 'NFS' and access_type not in ('ip', 'user'):
            LOG.warning(_LW('Only IP or USER access types are allowed for '
                            'NFS shares.'))
            return
        elif share_proto == 'CIFS' and access_type != 'user':
            LOG.warning(_LW('Only USER access type is allowed for'
                            ' CIFS shares.'))
            return

        access_to = access['access_to']
        share = self.helper._get_share_by_name(share_name, share_url_type)
        if not share:
            LOG.warning(_LW('Can not get share. share_name: %s'), share_name)
            return

        access_id = self.helper._get_access_from_share(share['ID'], access_to,
                                                       share_client_type)
        if not access_id:
            LOG.warning(_LW('Can not get access id from share. '
                            'share_name: %s'), share_name)
            return

        self.helper._remove_access_from_share(access_id, share_client_type)

    def allow_access(self, share, access, share_server=None):
        """Allow access to the share."""
        share_proto = share['share_proto']
        share_name = share['name']
        share_url_type = self.helper._get_share_url_type(share_proto)
        access_type = access['access_type']
        access_level = access['access_level']
        access_to = access['access_to']

        if access_level not in common_constants.ACCESS_LEVELS:
            raise exception.InvalidShareAccess(
                reason=(_('Unsupported level of access was provided - %s') %
                        access_level))

        if share_proto == 'NFS':
            if access_type == 'user':
                # Use 'user' as 'netgroup' for NFS.
                # A group name starts with @.
                access_to = '@' + access_to
            elif access_type != 'ip':
                message = _('Only IP or USER access types '
                            'are allowed for NFS shares.')
                raise exception.InvalidShareAccess(reason=message)
            if access_level == common_constants.ACCESS_LEVEL_RW:
                access_level = constants.ACCESS_NFS_RW
            else:
                access_level = constants.ACCESS_NFS_RO
        elif share_proto == 'CIFS':
            if access_type == 'user':
                if access_level == common_constants.ACCESS_LEVEL_RW:
                    access_level = constants.ACCESS_CIFS_RW
                else:
                    access_level = constants.ACCESS_CIFS_RO
            else:
                message = _('Only USER access type is allowed'
                            ' for CIFS shares.')
                raise exception.InvalidShareAccess(reason=message)

        share = self.helper._get_share_by_name(share_name, share_url_type)
        if not share:
            err_msg = (_("Can not get share ID by share %s.")
                       % share_name)
            LOG.error(err_msg)
            raise exception.InvalidShareAccess(reason=err_msg)

        share_id = share['ID']
        self.helper._allow_access_rest(share_id, access_to,
                                       share_proto, access_level)

    def get_pool(self, share):
        pool_name = share_utils.extract_host(share['host'], level='pool')
        if pool_name:
            return pool_name
        share_name = share['name']
        share_url_type = self.helper._get_share_url_type(share['share_proto'])
        share = self.helper._get_share_by_name(share_name, share_url_type)

        pool_name = None
        if share:
            pool = self.helper._get_fs_info_by_id(share['FSID'])
            pool_name = pool['POOLNAME']

        return pool_name

    def allocate_container(self, share, poolinfo):
        """Creates filesystem associated to share by name."""
        opts = huawei_utils.get_share_extra_specs_params(
            share['share_type_id'])

        smartx_opts = constants.OPTS_CAPABILITIES
        if opts is not None:
            smart = smartx.SmartX()
            smartx_opts, qos = smart.get_smartx_extra_specs_opts(opts)

        fileParam = self._init_filesys_para(share, poolinfo, smartx_opts)
        fsid = self.helper._create_filesystem(fileParam)

        try:
            if qos:
                smart_qos = smartx.SmartQos(self.helper)
                smart_qos.create_qos(qos, fsid)

            smartpartition = smartx.SmartPartition(self.helper)
            smartpartition.add(opts, fsid)

            smartcache = smartx.SmartCache(self.helper)
            smartcache.add(opts, fsid)
        except Exception as err:
            if fsid is not None:
                qos_id = self.helper.get_qosid_by_fsid(fsid)
                if qos_id:
                    self.remove_qos_fs(fsid, qos_id)
                self.helper._delete_fs(fsid)
            message = (_('Failed to add smartx. Reason: %(err)s.')
                       % {'err': err})
            raise exception.InvalidShare(reason=message)
        return fsid

    def manage_existing(self, share, driver_options):
        """Manage existing share."""

        share_proto = share['share_proto']
        share_name = share['name']
        old_export_location = share['export_locations'][0]['path']
        pool_name = share_utils.extract_host(share['host'], level='pool')
        share_url_type = self.helper._get_share_url_type(share_proto)
        old_share_name = self.helper._get_share_name_by_export_location(
            old_export_location, share_proto)

        share_storage = self.helper._get_share_by_name(old_share_name,
                                                       share_url_type)
        if not share_storage:
            err_msg = (_("Can not get share ID by share %s.")
                       % old_export_location)
            LOG.error(err_msg)
            raise exception.InvalidShare(reason=err_msg)

        fs_id = share_storage['FSID']
        fs = self.helper._get_fs_info_by_id(fs_id)
        if not self.check_fs_status(fs['HEALTHSTATUS'],
                                    fs['RUNNINGSTATUS']):
            raise exception.InvalidShare(
                reason=(_('Invalid status of filesystem: %(health)s '
                          '%(running)s.')
                        % {'health': fs['HEALTHSTATUS'],
                           'running': fs['RUNNINGSTATUS']}))

        if pool_name and pool_name != fs['POOLNAME']:
            raise exception.InvalidHost(
                reason=(_('The current pool(%(fs_pool)s) of filesystem '
                          'does not match the input pool(%(host_pool)s).')
                        % {'fs_pool': fs['POOLNAME'],
                           'host_pool': pool_name}))

        result = self.helper._find_all_pool_info()
        poolinfo = self.helper._find_pool_info(pool_name, result)

        opts = huawei_utils.get_share_extra_specs_params(
            share['share_type_id'])
        specs = share_types.get_share_type_extra_specs(share['share_type_id'])
        if ('capabilities:thin_provisioning' not in specs.keys()
                and 'thin_provisioning' not in specs.keys()):
            if fs['ALLOCTYPE'] == constants.ALLOC_TYPE_THIN_FLAG:
                opts['thin_provisioning'] = constants.THIN_PROVISIONING
            else:
                opts['thin_provisioning'] = constants.THICK_PROVISIONING

        change_opts = self.check_retype_change_opts(opts, poolinfo, fs)
        LOG.info(_LI('Retyping share (%(share)s), changed options are : '
                     '(%(change_opts)s).'),
                 {'share': old_share_name, 'change_opts': change_opts})
        try:
            self.retype_share(change_opts, fs_id)
        except Exception as err:
            message = (_("Retype share error. Share: %(share)s. "
                         "Reason: %(reason)s.")
                       % {'share': old_share_name,
                          'reason': err})
            raise exception.InvalidShare(reason=message)

        share_size = int(fs['CAPACITY']) / units.Mi / 2
        self.helper._change_fs_name(fs_id, share_name)
        location = self._get_location_path(share_name, share_proto)
        return (share_size, [location])

    def check_retype_change_opts(self, opts, poolinfo, fs):
        change_opts = {
            "partitionid": None,
            "cacheid": None,
            "dedupe&compression": None,
        }

        # SmartPartition
        old_partition_id = fs['SMARTPARTITIONID']
        old_partition_name = None
        new_partition_id = None
        new_partition_name = None
        if strutils.bool_from_string(opts['huawei_smartpartition']):
            if not opts['partitionname']:
                raise exception.InvalidInput(
                    reason=_('Partition name is None, please set '
                             'huawei_smartpartition:partitionname in key.'))
            new_partition_name = opts['partitionname']
            new_partition_id = self.helper._get_partition_id_by_name(
                new_partition_name)
            if new_partition_id is None:
                raise exception.InvalidInput(
                    reason=(_("Can't find partition name on the array, "
                              "partition name is: %(name)s.")
                            % {"name": new_partition_name}))

        if old_partition_id != new_partition_id:
            if old_partition_id:
                partition_info = self.helper.get_partition_info_by_id(
                    old_partition_id)
                old_partition_name = partition_info['NAME']
            change_opts["partitionid"] = ([old_partition_id,
                                           old_partition_name],
                                          [new_partition_id,
                                           new_partition_name])

        # SmartCache
        old_cache_id = fs['SMARTCACHEID']
        old_cache_name = None
        new_cache_id = None
        new_cache_name = None
        if strutils.bool_from_string(opts['huawei_smartcache']):
            if not opts['cachename']:
                raise exception.InvalidInput(
                    reason=_('Cache name is None, please set '
                             'huawei_smartcache:cachename in key.'))
            new_cache_name = opts['cachename']
            new_cache_id = self.helper._get_cache_id_by_name(
                new_cache_name)
            if new_cache_id is None:
                raise exception.InvalidInput(
                    reason=(_("Can't find cache name on the array, "
                              "cache name is: %(name)s.")
                            % {"name": new_cache_name}))

        if old_cache_id != new_cache_id:
            if old_cache_id:
                cache_info = self.helper.get_cache_info_by_id(
                    old_cache_id)
                old_cache_name = cache_info['NAME']
            change_opts["cacheid"] = ([old_cache_id, old_cache_name],
                                      [new_cache_id, new_cache_name])

        # SmartDedupe&SmartCompression
        smartx_opts = constants.OPTS_CAPABILITIES
        if opts is not None:
            smart = smartx.SmartX()
            smartx_opts, qos = smart.get_smartx_extra_specs_opts(opts)

        old_compression = fs['COMPRESSION']
        new_compression = smartx_opts['compression']
        old_dedupe = fs['DEDUP']
        new_dedupe = smartx_opts['dedupe']

        if fs['ALLOCTYPE'] == constants.ALLOC_TYPE_THIN_FLAG:
            fs['ALLOCTYPE'] = constants.ALLOC_TYPE_THIN
        else:
            fs['ALLOCTYPE'] = constants.ALLOC_TYPE_THICK

        if strutils.bool_from_string(opts['thin_provisioning']):
            opts['thin_provisioning'] = constants.ALLOC_TYPE_THIN
        else:
            opts['thin_provisioning'] = constants.ALLOC_TYPE_THICK

        if fs['ALLOCTYPE'] != opts['thin_provisioning']:
            msg = (_("Manage existing share "
                     "fs type and new_share_type mismatch. "
                     "fs type is: %(fs_type)s, "
                     "new_share_type is: %(new_share_type)s")
                   % {"fs_type": fs['ALLOCTYPE'],
                      "new_share_type": opts['thin_provisioning']})
            raise exception.InvalidHost(reason=msg)
        else:
            if fs['ALLOCTYPE'] == constants.ALLOC_TYPE_THICK:
                if new_compression or new_dedupe:
                    raise exception.InvalidInput(
                        reason=_("Dedupe or compression cannot be set for "
                                 "thick filesystem."))
            else:
                if (old_dedupe != new_dedupe
                        or old_compression != new_compression):
                    change_opts["dedupe&compression"] = ([old_dedupe,
                                                          old_compression],
                                                         [new_dedupe,
                                                          new_compression])
        return change_opts

    def retype_share(self, change_opts, fs_id):
        if change_opts.get('partitionid'):
            old, new = change_opts['partitionid']
            old_id = old[0]
            old_name = old[1]
            new_id = new[0]
            new_name = new[1]

            if old_id:
                self.helper._remove_fs_from_partition(fs_id, old_id)
            if new_id:
                self.helper._add_fs_to_partition(fs_id, new_id)
                msg = (_("Retype FS(id: %(fs_id)s) smartpartition from "
                         "(name: %(old_name)s, id: %(old_id)s) to "
                         "(name: %(new_name)s, id: %(new_id)s) "
                         "performed successfully.")
                       % {"fs_id": fs_id,
                          "old_id": old_id, "old_name": old_name,
                          "new_id": new_id, "new_name": new_name})
                LOG.info(msg)

        if change_opts.get('cacheid'):
            old, new = change_opts['cacheid']
            old_id = old[0]
            old_name = old[1]
            new_id = new[0]
            new_name = new[1]
            if old_id:
                self.helper._remove_fs_from_cache(fs_id, old_id)
            if new_id:
                self.helper._add_fs_to_cache(fs_id, new_id)
                msg = (_("Retype FS(id: %(fs_id)s) smartcache from "
                         "(name: %(old_name)s, id: %(old_id)s) to "
                         "(name: %(new_name)s, id: %(new_id)s) "
                         "performed successfully.")
                       % {"fs_id": fs_id,
                          "old_id": old_id, "old_name": old_name,
                          "new_id": new_id, "new_name": new_name})
                LOG.info(msg)

        if change_opts.get('dedupe&compression'):
            old, new = change_opts['dedupe&compression']
            old_dedupe = old[0]
            old_compression = old[1]
            new_dedupe = new[0]
            new_compression = new[1]
            if ((old_dedupe != new_dedupe)
                    or (old_compression != new_compression)):

                new_smartx_opts = {"dedupe": new_dedupe,
                                   "compression": new_compression}

                self.helper._change_extra_specs(fs_id, new_smartx_opts)
                msg = (_("Retype FS(id: %(fs_id)s) dedupe from %(old_dedupe)s "
                         "to %(new_dedupe)s performed successfully, "
                         "compression from "
                         "%(old_compression)s to %(new_compression)s "
                         "performed successfully.")
                       % {"fs_id": fs_id,
                          "old_dedupe": old_dedupe,
                          "new_dedupe": new_dedupe,
                          "old_compression": old_compression,
                          "new_compression": new_compression})
                LOG.info(msg)

    def remove_qos_fs(self, fs_id, qos_id):
        fs_list = self.helper.get_fs_list_in_qos(qos_id)
        fs_count = len(fs_list)
        if fs_count <= 1:
            qos = smartx.SmartQos(self.helper)
            qos.delete_qos(qos_id)
        else:
            self.helper.remove_fs_from_qos(fs_id,
                                           fs_list,
                                           qos_id)

    def _get_location_path(self, share_name, share_proto, ip=None):
        location = None
        if ip is None:
            root = self.helper._read_xml()
            ip = root.findtext('Storage/LogicalPortIP').strip()
        if share_proto == 'NFS':
            location = '%s:/%s' % (ip, share_name.replace("-", "_"))
        elif share_proto == 'CIFS':
            location = '\\\\%s\\%s' % (ip, share_name.replace("-", "_"))
        else:
            raise exception.InvalidShareAccess(
                reason=(_('Invalid NAS protocol supplied: %s.')
                        % share_proto))

        return location

    def _get_wait_interval(self):
        """Get wait interval from huawei conf file."""
        root = self.helper._read_xml()
        wait_interval = root.findtext('Filesystem/WaitInterval')
        if wait_interval:
            return int(wait_interval)
        else:
            LOG.info(_LI(
                "Wait interval is not configured in huawei "
                "conf file. Use default: %(default_wait_interval)d."),
                {"default_wait_interval": constants.DEFAULT_WAIT_INTERVAL})
            return constants.DEFAULT_WAIT_INTERVAL

    def _get_timeout(self):
        """Get timeout from huawei conf file."""
        root = self.helper._read_xml()
        timeout = root.findtext('Filesystem/Timeout')
        if timeout:
            return int(timeout)
        else:
            LOG.info(_LI(
                "Timeout is not configured in huawei conf file. "
                "Use default: %(default_timeout)d."),
                {"default_timeout": constants.DEFAULT_TIMEOUT})
            return constants.DEFAULT_TIMEOUT

    def check_conf_file(self):
        """Check the config file, make sure the essential items are set."""
        root = self.helper._read_xml()
        resturl = root.findtext('Storage/RestURL')
        username = root.findtext('Storage/UserName')
        pwd = root.findtext('Storage/UserPassword')
        product = root.findtext('Storage/Product')
        pool_node = root.findtext('Filesystem/StoragePool')
        logical_port_ip = root.findtext('Storage/LogicalPortIP')

        if product != "V3":
            err_msg = (_(
                'check_conf_file: Config file invalid. '
                'Product must be set to V3.'))
            LOG.error(err_msg)
            raise exception.InvalidInput(err_msg)

        if not (resturl and username and pwd):
            err_msg = (_(
                'check_conf_file: Config file invalid. RestURL,'
                ' UserName and UserPassword must be set.'))
            LOG.error(err_msg)
            raise exception.InvalidInput(err_msg)

        if not pool_node:
            err_msg = (_(
                'check_conf_file: Config file invalid. '
                'StoragePool must be set.'))
            LOG.error(err_msg)
            raise exception.InvalidInput(err_msg)

        if not (self.configuration.driver_handles_share_servers
                or logical_port_ip):
            err_msg = (_(
                'check_conf_file: Config file invalid. LogicalPortIP '
                'must be set when driver_handles_share_servers is False.'))
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

    def check_service(self):
        running_status = self.helper._get_cifs_service_status()
        if running_status != constants.STATUS_SERVICE_RUNNING:
            self.helper._start_cifs_service_status()

        service = self.helper._get_nfs_service_status()
        if ((service['RUNNINGSTATUS'] != constants.STATUS_SERVICE_RUNNING) or
                (service['SUPPORTV3'] == 'false') or
                (service['SUPPORTV4'] == 'false')):
            self.helper._start_nfs_service_status()

    def setup_server(self, network_info, metadata=None):
        """Set up share server with given network parameters."""
        self._check_network_type_validate(network_info['network_type'])

        vlan_tag = network_info['segmentation_id'] or 0
        ip = network_info['network_allocations'][0]['ip_address']
        subnet = utils.cidr_to_netmask(network_info['cidr'])
        if not utils.is_valid_ip_address(ip, '4'):
            err_msg = (_(
                "IP (%s) is invalid. Only IPv4 addresses are supported.") % ip)
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

        ad_created = False
        ldap_created = False
        try:
            if network_info.get('security_services'):
                active_directory, ldap = self._get_valid_security_service(
                    network_info.get('security_services'))

                # Configure AD or LDAP Domain.
                if active_directory:
                    self._configure_AD_domain(active_directory)
                    ad_created = True
                if ldap:
                    self._configure_LDAP_domain(ldap)
                    ldap_created = True

            # Create vlan and logical_port.
            vlan_id, logical_port_id = (
                self._create_vlan_and_logical_port(vlan_tag, ip, subnet))
        except exception.ManilaException:
            if ad_created:
                dns_ip_list = []
                user = active_directory['user']
                password = active_directory['password']
                self.helper.set_DNS_ip_address(dns_ip_list)
                self.helper.delete_AD_config(user, password)
                self._check_AD_expected_status(constants.STATUS_EXIT_DOMAIN)
            if ldap_created:
                self.helper.delete_LDAP_config()
            raise

        return {
            'share_server_name': network_info['server_id'],
            'share_server_id': network_info['server_id'],
            'vlan_id': vlan_id,
            'logical_port_id': logical_port_id,
            'ip': ip,
            'subnet': subnet,
            'vlan_tag': vlan_tag,
            'ad_created': ad_created,
            'ldap_created': ldap_created,
        }

    def _check_network_type_validate(self, network_type):
        if network_type not in ('flat', 'vlan'):
            err_msg = (_(
                'Invalid network type. Network type must be flat or vlan.'))
            raise exception.NetworkBadConfigurationException(reason=err_msg)

    def _get_valid_security_service(self, security_services):
        """Validate security services and return AD/LDAP config."""
        service_number = len(security_services)
        err_msg = _("Unsupported security services. "
                    "Only AD and LDAP are supported.")
        if service_number > 2:
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

        active_directory = None
        ldap = None
        for ss in security_services:
            if ss['type'] == 'active_directory':
                active_directory = ss
            elif ss['type'] == 'ldap':
                ldap = ss
            else:
                LOG.error(err_msg)
                raise exception.InvalidInput(reason=err_msg)

        return active_directory, ldap

    def _configure_AD_domain(self, active_directory):
        dns_ip = active_directory['dns_ip']
        user = active_directory['user']
        password = active_directory['password']
        domain = active_directory['domain']
        if not (dns_ip and user and password and domain):
            raise exception.InvalidInput(
                reason=_("dns_ip or user or password or domain "
                         "in security_services is None."))

        # Check DNS server exists or not.
        ip_address = self.helper.get_DNS_ip_address()
        if ip_address and ip_address[0]:
            err_msg = (_("DNS server (%s) has already been configured.")
                       % ip_address[0])
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

        # Check AD config exists or not.
        ad_exists, AD_domain = self.helper.get_AD_domain_name()
        if ad_exists:
            err_msg = (_("AD domain (%s) has already been configured.")
                       % AD_domain)
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

        # Set DNS server ip.
        dns_ip_list = dns_ip.split(",")
        DNS_config = self.helper.set_DNS_ip_address(dns_ip_list)

        # Set AD config.
        digits = string.digits
        random_id = ''.join([random.choice(digits) for i in range(9)])
        system_name = constants.SYSTEM_NAME_PREFIX + random_id

        try:
            self.helper.add_AD_config(user, password, domain, system_name)
            self._check_AD_expected_status(constants.STATUS_JOIN_DOMAIN)
        except exception.ManilaException as err:
            if DNS_config:
                dns_ip_list = []
                self.helper.set_DNS_ip_address(dns_ip_list)
            raise exception.InvalidShare(
                reason=(_('Failed to add AD config. '
                          'Reason: %s.') % err))

    def _check_AD_expected_status(self, expected_status):
        wait_interval = self._get_wait_interval()
        timeout = self._get_timeout()
        retries = timeout / wait_interval
        interval = wait_interval
        backoff_rate = 1

        @utils.retry(exception.InvalidShare,
                     interval,
                     retries,
                     backoff_rate)
        def _check_AD_status():
            ad = self.helper.get_AD_config()
            if ad['DOMAINSTATUS'] != expected_status:
                raise exception.InvalidShare(
                    reason=(_('AD domain (%s) status is not expected.')
                            % ad['FULLDOMAINNAME']))

        _check_AD_status()

    def _configure_LDAP_domain(self, ldap):
        server = ldap['server']
        domain = ldap['domain']
        if not server or not domain:
            raise exception.InvalidInput(reason=_("Server or domain is None."))

        # Check LDAP config exists or not.
        ldap_exists, LDAP_domain = self.helper.get_LDAP_domain_server()
        if ldap_exists:
            err_msg = (_("LDAP domain (%s) has already been configured.")
                       % LDAP_domain)
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

        # Set LDAP config.
        server_number = len(server.split(','))
        if server_number == 1:
            server = server + ",,"
        elif server_number == 2:
            server = server + ","
        elif server_number > 3:
            raise exception.InvalidInput(
                reason=_("Cannot support more than three LDAP servers."))

        self.helper.add_LDAP_config(server, domain)

    def _create_vlan_and_logical_port(self, vlan_tag, ip, subnet):
        optimal_port, port_type = self._get_optimal_port()
        port_id = self.helper.get_port_id(optimal_port, port_type)
        home_port_id = port_id
        home_port_type = port_type
        vlan_id = 0
        vlan_exists = True

        if port_type is None or port_id is None:
            err_msg = _("No appropriate port found to create logical port.")
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)
        if vlan_tag:
            vlan_exists, vlan_id = self.helper.get_vlan(port_id, vlan_tag)
            if not vlan_exists:
                # Create vlan.
                vlan_id = self.helper.create_vlan(
                    port_id, port_type, vlan_tag)
            home_port_id = vlan_id
            home_port_type = constants.PORT_TYPE_VLAN

        logical_port_exists, logical_port_id = (
            self.helper.get_logical_port(home_port_id, ip, subnet))
        if not logical_port_exists:
            try:
                # Create logical port.
                logical_port_id = (
                    self.helper.create_logical_port(
                        home_port_id, home_port_type, ip, subnet))
            except exception.ManilaException as err:
                if not vlan_exists:
                    self.helper.delete_vlan(vlan_id)
                raise exception.InvalidShare(
                    reason=(_('Failed to create logical port. '
                              'Reason: %s.') % err))

        return vlan_id, logical_port_id

    def _get_optimal_port(self):
        """Get an optimal physical port or bond port."""
        root = self.helper._read_xml()
        port_info = []
        port_list = root.findtext('Storage/Port')
        if port_list:
            port_list = port_list.split(";")
            for port in port_list:
                port = port.strip().strip('\n')
                if port:
                    port_info.append(port)

        eth_port, bond_port = self._get_online_port(port_info)
        optimal_port, port_type = (
            self._get_least_vlan_port(eth_port, bond_port))

        if not optimal_port:
            err_msg = (_("Cannot find optimal port. port_info: %s.")
                       % port_info)
            LOG.error(err_msg)
            raise exception.InvalidInput(reason=err_msg)

        return optimal_port, port_type

    def _get_online_port(self, all_port_list):
        eth_port = self.helper.get_all_eth_port()
        bond_port = self.helper.get_all_bond_port()

        eth_status = constants.STATUS_ETH_RUNNING
        online_eth_port = []
        for eth in eth_port:
            if (eth_status == eth['RUNNINGSTATUS']
                    and not eth['IPV4ADDR'] and not eth['BONDNAME']):
                online_eth_port.append(eth['LOCATION'])

        online_bond_port = []
        for bond in bond_port:
            if eth_status == bond['RUNNINGSTATUS']:
                port_id = jsonutils.loads(bond['PORTIDLIST'])
                bond_eth_port = self.helper.get_eth_port_by_id(port_id[0])
                if bond_eth_port and not bond_eth_port['IPV4ADDR']:
                    online_bond_port.append(bond['NAME'])

        filtered_eth_port = []
        filtered_bond_port = []
        if len(all_port_list) == 0:
            filtered_eth_port = online_eth_port
            filtered_bond_port = online_bond_port
        else:
            all_port_list = list(set(all_port_list))
            for port in all_port_list:
                is_eth_port = False
                for eth in online_eth_port:
                    if port == eth:
                        filtered_eth_port.append(port)
                        is_eth_port = True
                        break
                if is_eth_port:
                    continue
                for bond in online_bond_port:
                    if port == bond:
                        filtered_bond_port.append(port)
                        break

        return filtered_eth_port, filtered_bond_port

    def _get_least_vlan_port(self, eth_port, bond_port):
        sorted_eth = []
        sorted_bond = []

        if eth_port:
            sorted_eth = self._get_sorted_least_port(eth_port)
        if bond_port:
            sorted_bond = self._get_sorted_least_port(bond_port)

        if sorted_eth and sorted_bond:
            if sorted_eth[1] >= sorted_bond[1]:
                return sorted_bond[0], constants.PORT_TYPE_BOND
            else:
                return sorted_eth[0], constants.PORT_TYPE_ETH
        elif sorted_eth and not sorted_bond:
            return sorted_eth[0], constants.PORT_TYPE_ETH
        elif not sorted_eth and sorted_bond:
            return sorted_bond[0], constants.PORT_TYPE_BOND
        else:
            return None, None

    def _get_sorted_least_port(self, port_list):
        if not port_list:
            return None

        vlan_list = self.helper.get_all_vlan()
        count = {}
        for item in port_list:
            count[item] = 0

        for item in port_list:
            for vlan in vlan_list:
                pos = vlan['NAME'].rfind('.')
                if vlan['NAME'][:pos] == item:
                    count[item] += 1

        sort_port = sorted(count.items(), key=lambda count: count[1])

        return sort_port[0]

    def teardown_server(self, server_details, security_services=None):
        if not server_details:
            LOG.debug('Server details are empty.')
            return

        logical_port_id = server_details.get('logical_port_id')
        vlan_id = server_details.get('vlan_id')
        ad_created = server_details.get('ad_created')
        ldap_created = server_details.get('ldap_created')

        # Delete logical_port.
        if logical_port_id:
            logical_port_exists = (
                self.helper.check_logical_port_exists_by_id(logical_port_id))
            if logical_port_exists:
                self.helper.delete_logical_port(logical_port_id)

        # Delete vlan.
        if vlan_id and vlan_id != '0':
            vlan_exists = self.helper.check_vlan_exists_by_id(vlan_id)
            if vlan_exists:
                self.helper.delete_vlan(vlan_id)

        if security_services:
            active_directory, ldap = (
                self._get_valid_security_service(security_services))

            if ad_created and ad_created == '1' and active_directory:
                dns_ip = active_directory['dns_ip']
                user = active_directory['user']
                password = active_directory['password']
                domain = active_directory['domain']

                # Check DNS server exists or not.
                ip_address = self.helper.get_DNS_ip_address()
                if ip_address and ip_address[0] == dns_ip:
                    dns_ip_list = []
                    self.helper.set_DNS_ip_address(dns_ip_list)

                # Check AD config exists or not.
                ad_exists, AD_domain = self.helper.get_AD_domain_name()
                if ad_exists and AD_domain == domain:
                    self.helper.delete_AD_config(user, password)
                    self._check_AD_expected_status(
                        constants.STATUS_EXIT_DOMAIN)

            if ldap_created and ldap_created == '1' and ldap:
                server = ldap['server']
                domain = ldap['domain']

                # Check LDAP config exists or not.
                ldap_exists, LDAP_domain = (
                    self.helper.get_LDAP_domain_server())
                if ldap_exists:
                    LDAP_config = self.helper.get_LDAP_config()
                    if (LDAP_config['LDAPSERVER'] == server
                            and LDAP_config['BASEDN'] == domain):
                        self.helper.delete_LDAP_config()

    def ensure_share(self, share, share_server=None):
        """Ensure that share is exported."""
        share_proto = share['share_proto']
        share_name = share['name']
        share_id = share['id']
        share_url_type = self.helper._get_share_url_type(share_proto)

        share_storage = self.helper._get_share_by_name(share_name,
                                                       share_url_type)
        if not share_storage:
            raise exception.ShareResourceNotFound(share_id=share_id)

        fs_id = share_storage['FSID']
        self.assert_filesystem(fs_id)

        ip = self._get_share_ip(share_server)
        location = self._get_location_path(share_name, share_proto, ip)
        return [location]
