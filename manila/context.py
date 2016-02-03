# Copyright 2011 OpenStack LLC.
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

"""RequestContext: context for requests that persist through all of manila."""

import copy

from oslo_context import context as common_context
from oslo_log import log
from oslo_utils import timeutils
import six

from manila.i18n import _
from manila.i18n import _LW
from manila import policy

LOG = log.getLogger(__name__)


class RequestContext(object):
    """Security context and request information.

    Represents the user taking a given action within the system.

    """

    def __init__(self, user_id, project_id, is_admin=None, read_deleted="no",
                 roles=None, remote_address=None, timestamp=None,
                 request_id=None, auth_token=None, overwrite=True,
                 quota_class=None, service_catalog=None, **kwargs):
        """Initialize RequestContext.

        :param read_deleted: 'no' indicates deleted records are hidden, 'yes'
            indicates deleted records are visible, 'only' indicates that
            *only* deleted records are visible.

        :param overwrite: Set to False to ensure that the greenthread local
            copy of the index is not overwritten.

        :param kwargs: Extra arguments that might be present, but we ignore
            because they possibly came in from older rpc messages.
        """
        user = kwargs.pop('user', None)
        tenant = kwargs.pop('tenant', None)
        if kwargs:
            LOG.warning(_LW('Arguments dropped when creating context: %s.'),
                        str(kwargs))

        self.user_id = user_id or user
        self.project_id = project_id or tenant
        self.roles = roles or []
        self.is_admin = is_admin
        if self.is_admin is None:
            self.is_admin = policy.check_is_admin(self.roles)
        elif self.is_admin and 'admin' not in self.roles:
            self.roles.append('admin')
        self.read_deleted = read_deleted
        self.remote_address = remote_address
        if not timestamp:
            timestamp = timeutils.utcnow()
        if isinstance(timestamp, six.string_types):
            timestamp = timeutils.parse_strtime(timestamp)
        self.timestamp = timestamp
        if service_catalog:
            self.service_catalog = [s for s in service_catalog
                                    if s.get('type') in ('compute', 'volume')]
        else:
            self.service_catalog = []

        if not request_id:
            request_id = common_context.generate_request_id()
        self.request_id = request_id
        self.auth_token = auth_token
        self.quota_class = quota_class
        if overwrite or not common_context.get_current():
            self.update_store()

    def _get_read_deleted(self):
        return self._read_deleted

    def _set_read_deleted(self, read_deleted):
        if read_deleted not in ('no', 'yes', 'only'):
            raise ValueError(_("read_deleted can only be one of 'no', "
                               "'yes' or 'only', not %r") % read_deleted)
        self._read_deleted = read_deleted

    def _del_read_deleted(self):
        del self._read_deleted

    read_deleted = property(_get_read_deleted, _set_read_deleted,
                            _del_read_deleted)

    def update_store(self):
        common_context._request_store.context = self

    def to_dict(self):
        return {'user_id': self.user_id,
                'project_id': self.project_id,
                'is_admin': self.is_admin,
                'read_deleted': self.read_deleted,
                'roles': self.roles,
                'remote_address': self.remote_address,
                'timestamp': self.timestamp.isoformat(),
                'request_id': self.request_id,
                'auth_token': self.auth_token,
                'quota_class': self.quota_class,
                'tenant': self.tenant,
                'service_catalog': self.service_catalog,
                'user': self.user}

    @classmethod
    def from_dict(cls, values):
        return cls(**values)

    def elevated(self, read_deleted=None, overwrite=False):
        """Return a version of this context with admin flag set."""
        context = copy.deepcopy(self)
        context.is_admin = True

        if 'admin' not in context.roles:
            context.roles.append('admin')

        if read_deleted is not None:
            context.read_deleted = read_deleted

        return context

    # NOTE(sirp): the openstack/common version of RequestContext uses
    # tenant/user whereas the Manila version uses project_id/user_id. We need
    # this shim in order to use context-aware code from openstack/common, like
    # logging, until we make the switch to using openstack/common's version of
    # RequestContext.
    @property
    def tenant(self):
        return self.project_id

    @property
    def user(self):
        return self.user_id


def get_admin_context(read_deleted="no"):
    return RequestContext(user_id=None,
                          project_id=None,
                          is_admin=True,
                          read_deleted=read_deleted,
                          overwrite=False)
