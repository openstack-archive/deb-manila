# Copyright 2016 Nexenta Systems, Inc.
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
:mod:`nexenta.jsonrpc` -- Nexenta-specific JSON RPC client
=====================================================================

.. automodule:: nexenta.jsonrpc
"""

import base64
import json
import requests

from oslo_log import log
from oslo_serialization import jsonutils

from manila import exception
from manila import utils

LOG = log.getLogger(__name__)


class NexentaJSONProxy(object):

    retry_exc_tuple = (requests.exceptions.ConnectionError,)

    def __init__(self, scheme, host, port, path, user, password, auto=False,
                 obj=None, method=None):
        self.scheme = scheme.lower()
        self.host = host
        self.port = port
        self.path = path
        self.user = user
        self.password = password
        self.auto = auto
        self.obj = obj
        self.method = method

    def __getattr__(self, name):
        if not self.obj:
            obj, method = name, None
        elif not self.method:
            obj, method = self.obj, name
        else:
            obj, method = '%s.%s' % (self.obj, self.method), name
        return NexentaJSONProxy(self.scheme, self.host, self.port, self.path,
                                self.user, self.password, self.auto, obj,
                                method)

    @property
    def url(self):
        return '%s://%s:%s%s' % (self.scheme, self.host, self.port, self.path)

    def __hash__(self):
        return self.url.__hash__()

    def __repr__(self):
        return 'NMS proxy: %s' % self.url

    @utils.retry(retry_exc_tuple, retries=6)
    def __call__(self, *args):
        data = jsonutils.dumps({
            'object': self.obj,
            'method': self.method,
            'params': args,
        })
        auth = base64.b64encode(
            ('%s:%s' % (self.user, self.password)).encode('utf-8'))
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic %s' % auth,
        }
        LOG.debug('Sending JSON data: %s', data)
        r = requests.post(self.url, data=data, headers=headers)
        response = json.loads(r.content) if r.content else None
        LOG.debug('Got response: %s', response)
        if response.get('error') is not None:
            message = response['error'].get('message', '')
            raise exception.NexentaException(reason=message)
        return response.get('result')
