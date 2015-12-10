# Copyright (c) 2010 OpenStack, LLC.
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

"""
Chance (Random) Scheduler implementation
"""

import random

from oslo_config import cfg

from manila import exception
from manila.i18n import _
from manila.scheduler.drivers import base

CONF = cfg.CONF


class ChanceScheduler(base.Scheduler):
    """Implements Scheduler as a random node selector."""

    def _filter_hosts(self, request_spec, hosts, **kwargs):
        """Filter a list of hosts based on request_spec."""

        filter_properties = kwargs.get('filter_properties', {})
        ignore_hosts = filter_properties.get('ignore_hosts', [])
        hosts = [host for host in hosts if host not in ignore_hosts]
        return hosts

    def _schedule(self, context, topic, request_spec, **kwargs):
        """Picks a host that is up at random."""

        elevated = context.elevated()
        hosts = self.hosts_up(elevated, topic)
        if not hosts:
            msg = _("Is the appropriate service running?")
            raise exception.NoValidHost(reason=msg)

        hosts = self._filter_hosts(request_spec, hosts, **kwargs)
        if not hosts:
            msg = _("Could not find another host")
            raise exception.NoValidHost(reason=msg)

        return hosts[int(random.random() * len(hosts))]

    def schedule_create_share(self, context, request_spec, filter_properties):
        """Picks a host that is up at random."""
        topic = CONF.share_topic
        host = self._schedule(context, topic, request_spec,
                              filter_properties=filter_properties)
        share_id = request_spec['share_id']
        snapshot_id = request_spec['snapshot_id']

        updated_share = base.share_update_db(context, share_id, host)
        self.share_rpcapi.create_share_instance(
            context,
            updated_share.instance,
            host,
            request_spec,
            filter_properties,
            snapshot_id
        )
