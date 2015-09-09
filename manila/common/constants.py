# Copyright 2013 Openstack Foundation
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

STATUS_NEW = 'new'
STATUS_CREATING = 'creating'
STATUS_DELETING = 'deleting'
STATUS_DELETED = 'deleted'
STATUS_ERROR = 'error'
STATUS_ERROR_DELETING = 'error_deleting'
STATUS_AVAILABLE = 'available'
STATUS_ACTIVE = 'active'
STATUS_INACTIVE = 'inactive'
STATUS_MANAGING = 'manage_starting'
STATUS_MANAGE_ERROR = 'manage_error'
STATUS_UNMANAGING = 'unmanage_starting'
STATUS_UNMANAGE_ERROR = 'unmanage_error'
STATUS_UNMANAGED = 'unmanaged'
STATUS_EXTENDING = 'extending'
STATUS_EXTENDING_ERROR = 'extending_error'
STATUS_SHRINKING = 'shrinking'
STATUS_SHRINKING_ERROR = 'shrinking_error'
STATUS_SHRINKING_POSSIBLE_DATA_LOSS_ERROR = (
    'shrinking_possible_data_loss_error'
)

TRANSITIONAL_STATUSES = (
    STATUS_CREATING, STATUS_DELETING,
    STATUS_MANAGING, STATUS_UNMANAGING,
    STATUS_EXTENDING, STATUS_SHRINKING,
)

SUPPORTED_SHARE_PROTOCOLS = (
    'NFS', 'CIFS', 'GLUSTERFS', 'HDFS')

SECURITY_SERVICES_ALLOWED_TYPES = ['active_directory', 'ldap', 'kerberos']

NFS_EXPORTS_FILE = '/etc/exports'
NFS_EXPORTS_FILE_TEMP = '/var/lib/nfs/etab'

MOUNT_FILE = '/etc/fstab'
MOUNT_FILE_TEMP = '/etc/mtab'

# Below represented ports are ranges (from, to)
CIFS_PORTS = (
    ("tcp", (445, 445)),
    ("tcp", (137, 139)),
    ("udp", (137, 139)),
    ("udp", (445, 445)),
)
NFS_PORTS = (
    ("tcp", (2049, 2049)),
    ("udp", (2049, 2049)),
)
SSH_PORTS = (
    ("tcp", (22, 22)),
)
PING_PORTS = (
    ("icmp", (-1, -1)),
)

SERVICE_INSTANCE_SECGROUP_DATA = (
    CIFS_PORTS + NFS_PORTS + SSH_PORTS + PING_PORTS)

ACCESS_LEVEL_RW = 'rw'
ACCESS_LEVEL_RO = 'ro'

ACCESS_LEVELS = (
    ACCESS_LEVEL_RW,
    ACCESS_LEVEL_RO,
)


class ExtraSpecs(object):

    # Extra specs key names
    DRIVER_HANDLES_SHARE_SERVERS = "driver_handles_share_servers"
    SNAPSHOT_SUPPORT = "snapshot_support"

    # Extra specs containers
    REQUIRED = (
        DRIVER_HANDLES_SHARE_SERVERS,
    )
    UNDELETABLE = (
        DRIVER_HANDLES_SHARE_SERVERS,
        SNAPSHOT_SUPPORT,
    )
    BOOLEAN = (
        DRIVER_HANDLES_SHARE_SERVERS,
        SNAPSHOT_SUPPORT,
    )
