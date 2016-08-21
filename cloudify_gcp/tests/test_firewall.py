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

from cloudify_gcp.compute import firewall


@patch('cloudify_gcp.utils.assure_resource_id_correct', return_value=True)
@patch('cloudify_gcp.gcp.ServiceAccountCredentials.from_json_keyfile_dict')
@patch('cloudify_gcp.utils.get_gcp_resource_name', return_value='valid_name')
@patch('cloudify_gcp.gcp.build')
class TestGCPFirewall(unittest.TestCase):

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
        firewall.create(
                {},
                'name',
                )

        mock_build.assert_called_once()
        mock_build().firewalls().insert.assert_called_with(
                body={
                    'name': 'valid_name',
                    'network': 'global/networks/valid_name',
                    },
                project='not really a project'
                )

    def test_create_external(self, mock_build, *args):
        self.ctxmock.node.properties['use_external_resource'] = True

        firewall.create(
                {},
                'name',
                )

        mock_build.assert_called_once()
        mock_build().firewalls().get.assert_called_once_with(
                firewall=True,
                project='not really a project'
                )

    def test_delete(self, mock_build, *args):
        self.ctxmock.instance.runtime_properties['gcp_name'] = 'delete_name'
        firewall.delete()

        mock_build.assert_called_once()
        mock_build().firewalls().delete.assert_called_with(
                firewall='delete_name',
                project='not really a project',
                )

    def test_create_security_group(self, mock_build, *args):
        firewall.create_security_group(
                {},
                'name',
                )

        mock_build.assert_called_once()
        mock_build().firewalls().insert.assert_called_with(
                body={
                    'network': 'global/networks/not a real network',
                    'sourceTags': [],
                    'sourceRanges': [],
                    'targetTags': [],
                    'allowed': [],
                    'name': 'valid_name'
                    },
                project='not really a project',
                )

    def test_delete_security_group(self, mock_build, *args):
        self.ctxmock.instance.runtime_properties['gcp_name'] = 'delete_name'
        firewall.delete_security_group()

        mock_build.assert_called_once()
        mock_build().firewalls().delete.assert_called_with(
                firewall='delete_name',
                project='not really a project',
                )
