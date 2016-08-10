########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import unittest

from mock import patch, Mock

from cloudify.state import current_ctx

from cloudify_gcp.compute.instance import (
        create,
        start,
        delete,
        )


@patch('cloudify_gcp.utils.get_gcp_resource_name', return_value='valid_name')
@patch('cloudify_gcp.utils.assure_resource_id_correct', return_value=True)
@patch('cloudify_gcp.gcp.ServiceAccountCredentials.from_json_keyfile_dict')
@patch('cloudify_gcp.gcp.build')
class TestGCPInstance(unittest.TestCase):

    def setUp(self):
        ctx = self.ctxmock = Mock()
        ctx.node.name = 'name'
        ctx.node.id = 'id'
        ctx.node.properties = {
            'gcp_config': {
                'auth': {
                    'type': 'service_account',
                    'client_email': 'nobody@invalid',
                    'private_key_id': "This isn't even an ID!",
                    'private_key': 'nope!'
                    },
                'zone': 'a very fake zone',
                'network': 'not a real network',
                'project': 'not really a project',
                },
            }
        ctx.instance.runtime_properties = {}
        ctx.provider_context = {
            'resources': {
                'cloudify_agent': {
                    'public_key': 'Fakey McFakeface',
                    },
                },
            }
        current_ctx.set(ctx)

    def test_create(self, mock_build, *args):
        create(
                'instance_type',
                'image_id',
                'name',
                'zone',
                external_ip=False,
                startup_script={'type': 'string'},
                scopes='scopes',
                tags=['tags'],
                )

        mock_build.assert_called_once()
        mock_build().instances().insert.assert_called_with(
                body={
                    'machineType': 'zones/zone/machineTypes/instance_type',
                    'name': 'valid_name',
                    'tags': {'items': ['valid_name', 'tags']},
                    'description': 'Cloudify generated instance',
                    'disks': [{
                        'initializeParams': {'sourceImage': 'image_id'},
                        'boot': True, 'autoDelete': True}],
                    'serviceAccounts': [{
                        'scopes': 'scopes',
                        'email': 'default'}],
                    'metadata': {
                        'items': [
                            {'value': 'not really a project', 'key': 'bucket'},
                            {'value': 'Fakey McFakeface', 'key': 'sshKeys'}]},
                    'networkInterfaces': [{
                        'network': 'global/networks/valid_name'}]
                    },
                project='not really a project',
                zone='zone'
                )

        self.assertEqual(
                self.ctxmock.instance.runtime_properties,
                {'gcp_zone': 'zone',
                 'gcp_name': 'valid_name',
                 })

    def test_delete(self, mock_build, *args):
        self.ctxmock.instance.runtime_properties['gcp_name'] = 'delete_name'
        delete()

        mock_build.assert_called_once()
        mock_build().instances().delete.assert_called_with(
                instance='valid_name',
                project='not really a project',
                zone='a very fake zone')
