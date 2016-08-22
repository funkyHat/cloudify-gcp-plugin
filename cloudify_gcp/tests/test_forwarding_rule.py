#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

from mock import patch, Mock, MagicMock

from cloudify.state import current_ctx

from cloudify_gcp.compute import forwarding_rule


@patch('cloudify_gcp.utils.assure_resource_id_correct', return_value=True)
@patch('cloudify_gcp.gcp.ServiceAccountCredentials.from_json_keyfile_dict')
@patch('cloudify_gcp.utils.get_gcp_resource_name', return_value='valid_name')
@patch('cloudify_gcp.gcp.build')
class TestForwardingRule(unittest.TestCase):

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
        forwarding_rule.create(
                'name',
                'target',
                'range',
                'ip',
                )

        mock_build.assert_called_once()
        mock_build().globalForwardingRules().insert.assert_called_with(
                body={
                    'portRange': 'range',
                    'IPAddress': 'ip',
                    'target': 'target',
                    'description': 'Cloudify generated Global Forwarding Rule',
                    'name': 'name'},
                project='not really a project'
                )

    @patch('cloudify_gcp.utils.response_to_operation')
    def test_delete(self, mock_response, mock_build, *args):
        self.ctxmock.instance.runtime_properties.update({
            'gcp_name': 'delete_name',
            'gcp_target_proxy_type': 'http',
            })

        operation = MagicMock()
        operation.has_finished.return_value = True
        mock_response.return_value = operation

        forwarding_rule.delete()

        mock_build.assert_called_once()
        mock_build().globalForwardingRules().delete.assert_called_with(
                forwardingRule='delete_name',
                project='not really a project',
                )
