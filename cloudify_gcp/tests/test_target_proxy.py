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

from cloudify.exceptions import NonRecoverableError
from cloudify.state import current_ctx

from cloudify_gcp.compute import target_proxy


@patch('cloudify_gcp.utils.assure_resource_id_correct', return_value=True)
@patch('cloudify_gcp.gcp.ServiceAccountCredentials.from_json_keyfile_dict')
@patch('cloudify_gcp.utils.get_gcp_resource_name', return_value='valid_name')
@patch('cloudify_gcp.gcp.build')
class TestTargetProxy(unittest.TestCase):

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

    def test_create_http(self, mock_build, *args):
        target_proxy.create(
                'name',
                'http',
                'url map',
                ssl_certificate=None,
                )

        mock_build.assert_called_once()
        mock_build().targetHttpProxies().insert.assert_called_with(
                body={
                    'urlMap': 'url map',
                    'description': 'Cloudify generated TargetHttpProxy',
                    'name': 'name'},
                project='not really a project'
                )

    def test_create_https(self, mock_build, *args):
        target_proxy.create(
                'name',
                'https',
                'url map',
                ssl_certificate='cert',
                )

        mock_build.assert_called_once()
        mock_build().targetHttpsProxies().insert.assert_called_with(
                body={
                    'urlMap': 'url map',
                    'sslCertificates': ['cert'],
                    'description': 'Cloudify generated TargetHttpsProxy',
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

        target_proxy.delete()

        mock_build.assert_called_once()
        mock_build().targetHttpProxies().delete.assert_called_with(
                targetHttpProxy='delete_name',
                project='not really a project',
                )


class TestTargetProxyHelpers(unittest.TestCase):

    def test_target_proxy_of_type_raises(self):
        with self.assertRaises(NonRecoverableError) as e:
            target_proxy.target_proxy_of_type('http', ssl_certificate=' ')

        self.assertIn('SSL', e.exception.message)

        with self.assertRaises(NonRecoverableError) as e:
            target_proxy.target_proxy_of_type('carrots', ssl_certificate=' ')

        self.assertIn('Unexpected type', e.exception.message)
