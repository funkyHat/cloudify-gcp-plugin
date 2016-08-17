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

from mock import patch, Mock

from cloudify.state import current_ctx

from cloudify_gcp.compute import keypair


@patch('cloudify_gcp.utils.assure_resource_id_correct', return_value=True)
@patch('cloudify_gcp.utils.get_key_user_string', side_effect=lambda x: x)
@patch('cloudify_gcp.utils.get_gcp_resource_name', return_value='valid_name')
@patch('os.chmod')
@patch('cloudify_gcp.compute.keypair.open')
@patch('cloudify_gcp.compute.keypair.RSA.generate')
class TestGCPKeypair(unittest.TestCase):

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

    def test_create(self, mock_rsa, *args):
        keypair.create(
                'user',
                'private',
                'public',
                )

        mock_rsa.assert_called_once_with(2048)

        self.assertEqual(
                {'gcp_private_key': mock_rsa().exportKey(),
                 'gcp_public_key': mock_rsa().exportKey(),
                 'user': 'user'},
                self.ctxmock.instance.runtime_properties)

    def test_create_external(self, mock_get_resource, *args):
        self.ctxmock.node.properties['use_external_resource'] = True

        keypair.create(
                'user',
                'private',
                'public'
                )

        self.assertEqual(2, self.ctxmock.get_resource.call_count)

        for call_arg in 'public', 'private':
            self.ctxmock.get_resource.assert_any_call(call_arg)

        self.assertEqual(
                {'gcp_private_key': self.ctxmock.get_resource(),
                 'gcp_public_key': self.ctxmock.get_resource(),
                 'user': 'user'},
                self.ctxmock.instance.runtime_properties)

    def test_delete(self, mock_rsa, *args):
        self.ctxmock.instance.runtime_properties[
                'gcp_public_key'] = 'delete_pubkey'

        keypair.delete(
                'user',
                'private',
                )

        self.assertEqual(
                {},
                self.ctxmock.instance.runtime_properties)
