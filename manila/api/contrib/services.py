# Copyright 2012 IBM Corp.
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

from oslo_log import log
import webob.exc

from manila.api import extensions
from manila import db
from manila import exception
from manila import utils

LOG = log.getLogger(__name__)
authorize = extensions.extension_authorizer('share', 'services')


class ServiceController(object):
    def index(self, req):
        """Return a list of all running services."""
        context = req.environ['manila.context']
        authorize(context)
        all_services = db.service_get_all(context)

        services = []
        for service in all_services:
            service = {
                'id': service['id'],
                'binary': service['binary'],
                'host': service['host'],
                'zone': service['availability_zone']['name'],
                'status': 'disabled' if service['disabled'] else 'enabled',
                'state': 'up' if utils.service_is_up(service) else 'down',
                'updated_at': service['updated_at'],
            }
            services.append(service)

        search_opts = [
            'host',
            'binary',
            'zone',
            'state',
            'status',
        ]
        for search_opt in search_opts:
            value = ''
            if search_opt in req.GET:
                value = req.GET[search_opt]
                services = [s for s in services if s[search_opt] == value]
            if len(services) == 0:
                break

        return {'services': services}

    def update(self, req, id, body):
        """Enable/Disable scheduling for a service."""
        context = req.environ['manila.context']
        authorize(context)

        if id == "enable":
            disabled = False
        elif id == "disable":
            disabled = True
        else:
            raise webob.exc.HTTPNotFound("Unknown action")

        try:
            host = body['host']
            binary = body['binary']
        except (TypeError, KeyError):
            raise webob.exc.HTTPBadRequest()

        try:
            svc = db.service_get_by_args(context, host, binary)
            if not svc:
                raise webob.exc.HTTPNotFound('Unknown service')

            db.service_update(context, svc['id'], {'disabled': disabled})
        except exception.ServiceNotFound:
            raise webob.exc.HTTPNotFound("service not found")

        return {'host': host, 'binary': binary, 'disabled': disabled}


class Services(extensions.ExtensionDescriptor):
    """Services support."""

    name = "Services"
    alias = "os-services"
    updated = "2012-10-28T00:00:00-00:00"

    def get_resources(self):
        resources = []
        resource = extensions.ResourceExtension('os-services',
                                                ServiceController())
        resources.append(resource)
        return resources
