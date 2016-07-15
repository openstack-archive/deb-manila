# Copyright (c) 2015 Mirantis Inc.
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

from oslo_utils import strutils

from manila.api import common


class ViewBuilder(common.ViewBuilder):
    """Model export-locations API responses as a python dictionary."""

    _collection_name = "export_locations"

    _detail_version_modifiers = [
        'add_preferred_path_attribute',
    ]

    def _get_export_location_view(self, request, export_location,
                                  detail=False):

        context = request.environ['manila.context']

        view = {
            'id': export_location['uuid'],
            'path': export_location['path'],
        }
        self.update_versioned_resource_dict(request, view, export_location)
        if context.is_admin:
            view['share_instance_id'] = export_location[
                'share_instance_id']
            view['is_admin_only'] = export_location['is_admin_only']

        if detail:
            view['created_at'] = export_location['created_at']
            view['updated_at'] = export_location['updated_at']

        return {'export_location': view}

    def summary(self, request, export_location):
        """Summary view of a single export location."""
        return self._get_export_location_view(request, export_location,
                                              detail=False)

    def detail(self, request, export_location):
        """Detailed view of a single export location."""
        return self._get_export_location_view(request, export_location,
                                              detail=True)

    def _list_export_locations(self, request, export_locations, detail=False):
        """View of export locations list."""
        view_method = self.detail if detail else self.summary
        return {self._collection_name: [
            view_method(request, export_location)['export_location']
            for export_location in export_locations
        ]}

    def detail_list(self, request, export_locations):
        """Detailed View of export locations list."""
        return self._list_export_locations(request, export_locations,
                                           detail=True)

    def summary_list(self, request, export_locations):
        """Summary View of export locations list."""
        return self._list_export_locations(request, export_locations,
                                           detail=False)

    @common.ViewBuilder.versioned_method('2.14')
    def add_preferred_path_attribute(self, context, view_dict,
                                     export_location):
        view_dict['preferred'] = strutils.bool_from_string(
            export_location['el_metadata'].get('preferred'))
