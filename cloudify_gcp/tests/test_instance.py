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

from mock import patch

from cloudify.exceptions import NonRecoverableError

from cloudify_gcp.compute import instance
from . import TestGCP


@patch('cloudify_gcp.utils.assure_resource_id_correct', return_value=True)
@patch('cloudify_gcp.gcp.ServiceAccountCredentials.from_json_keyfile_dict')
@patch('cloudify_gcp.utils.get_gcp_resource_name', return_value='valid_name')
@patch('cloudify_gcp.gcp.build')
class TestGCPInstance(TestGCP):

    def test_create(self, mock_build, *args):
        self.ctxmock.instance.runtime_properties = {
                'startup_script': {'type': 'string'},
                }

        instance.create(
                'instance_type',
                'image_id',
                'name',
                'zone',
                external_ip=False,
                startup_script=None,
                scopes='scopes',
                tags=['tags'],
                )

        mock_build.assert_called_once()

        mock_build().instances().insert.call_args[1][
                'body']['tags']['items'].sort()
        mock_build().instances().insert.assert_called_with(
                body={
                    'machineType': 'zones/zone/machineTypes/instance_type',
                    'name': 'valid_name',
                    'tags': {'items': ['tags', 'valid_name']},
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
                {
                    'gcp_zone': 'zone',
                    'gcp_name': 'valid_name',
                    'instance_name': 'name',
                    'startup_script': {'type': 'string'},
                 },
                self.ctxmock.instance.runtime_properties
                )

    def test_create_with_disk(self, mock_build, *args):
        self.ctxmock.instance.runtime_properties = {
                'gcp_disk': '💾',
                }

        instance.create(
                'instance_type',
                'image_id',
                'name',
                'zone',
                external_ip=False,
                startup_script=None,
                scopes='scopes',
                tags=['tags'],
                )

        mock_build().instances().insert.call_args[1][
                'body']['tags']['items'].sort()
        mock_build().instances().insert.assert_called_with(
                body={
                    'machineType': 'zones/zone/machineTypes/instance_type',
                    'name': 'valid_name',
                    'tags': {'items': ['tags', 'valid_name']},
                    'description': 'Cloudify generated instance',
                    'disks': ['💾'],
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

    @patch('cloudify_gcp.utils.get_item_from_gcp_response',
           return_value={'networkInterfaces': [{'networkIP': 'a'}]})
    def test_start(self, mock_getitem, mock_build, *args):
        self.ctxmock.instance.runtime_properties['instance_name'] = 'name'
        instance.start()

        self.assertEqual(
                self.ctxmock.instance.runtime_properties['ip'],
                'a')

    def test_delete(self, mock_build, *args):
        self.ctxmock.instance.runtime_properties['gcp_name'] = 'delete_name'
        instance.delete()

        mock_build.assert_called_once()
        mock_build().instances().delete.assert_called_with(
                instance='valid_name',
                project='not really a project',
                zone='a very fake zone')

    @patch('cloudify_gcp.utils.is_object_deleted', return_value=True)
    def test_delete_deleted(self, mock_is_deleted, mock_build, *args):
        self.ctxmock.instance.runtime_properties = {
                'gcp_disk': 'hi',
                'gcp_name': 'hello',
                'gcp_zone': 'hey',
                'another': 'yo',
                }

        instance.delete()

        self.assertFalse(mock_build().instances().delete.called)

        self.assertEqual(
                {'another': 'yo'},
                self.ctxmock.instance.runtime_properties)

    def test_add_external_ip(self, mock_build, *args):
        self.ctxmock.target.node.properties = {
                'use_external_resource': False,
                }

        instance.add_external_ip('instance_name')

        mock_build().instances().addAccessConfig.assert_called_once_with(
                body={
                    'kind': 'compute#accessConfig',
                    'type': 'ONE_TO_ONE_NAT',
                    'name': 'External NAT'},
                instance='valid_name',
                networkInterface='nic0',
                project='not really a project',
                zone='a very fake zone')

    def test_add_external_external_ip(self, mock_build, *args):
        self.ctxmock.target.node.properties = {
                'use_external_resource': True,
                }
        self.ctxmock.target.instance.runtime_properties = {
                'gcp_ip': "1.2.3.4",
                }

        instance.add_external_ip('instance_name')

        mock_build().instances().addAccessConfig.assert_called_once_with(
                body={
                    'natIP': '1.2.3.4',
                    'kind': 'compute#accessConfig',
                    'type': 'ONE_TO_ONE_NAT',
                    'name': 'External NAT'},
                instance='valid_name',
                networkInterface='nic0',
                project='not really a project',
                zone='a very fake zone')

    def test_add_external_external_ip_raises(self, mock_build, *args):
        self.ctxmock.target.node.properties = {
                'use_external_resource': True,
                }
        self.ctxmock.target.instance.runtime_properties = {}

        with self.assertRaises(NonRecoverableError):
            instance.add_external_ip('instance_name')

    def test_remove_external_ip(self, mock_build, *args):
        instance.remove_external_ip('instance_name')

        mock_build().instances().deleteAccessConfig.assert_called_once_with(
                accessConfig='External NAT',
                instance='valid_name',
                networkInterface='nic0',
                project='not really a project',
                zone='a very fake zone',
                )

    def test_attach_disk(self, mock_build, *args):
        instance.attach_disk('instance', 'disk')

        mock_build().instances().attachDisk.assert_called_once_with(
                body='disk',
                instance='valid_name',
                project='not really a project',
                zone='a very fake zone'
                )

    def test_detach_disk(self, mock_build, *args):
        instance.detach_disk('instance', 'disk')

        mock_build().instances().detachDisk.assert_called_once_with(
                deviceName='disk',
                instance='valid_name',
                project='not really a project',
                zone='a very fake zone',
                )

    def test_add_ssh_key(self, mock_build, *args):
        self.ctxmock.target.instance.runtime_properties = {
                'gcp_public_key': 'ssh-rsa blahblabhalblah',
                'user': 'test_user',
                }
        self.ctxmock.source.instance.runtime_properties = {}

        instance.add_ssh_key()

        self.assertEqual(
                self.ctxmock.source.instance.runtime_properties['ssh_keys'],
                ['test_user:ssh-rsa blahblabhalblah test_user'])

    def test_add_instance_tag(self, mock_build, *args):
        mock_build().instances().get().execute.return_value = {
                'tags': {
                    'items': ['a', 'b', 'c'],
                    'fingerprint': u'🖐'}}

        instance.add_instance_tag('instance', ['a tag'])

        # Something weird happens so we can't be sure of the order of tags
        mock_build().instances().setTags.call_args[1]['body']['items'].sort()
        mock_build().instances().setTags.assert_called_once_with(
            body={
                'items': ['a', 'b', 'c', 'valid_name'],
                'fingerprint': u'🖐'},
            project='not really a project',
            instance='valid_name',
            zone='a very fake zone'
            )

    def test_remove_instance_tag(self, mock_build, mock_get_res, *args):
        mock_build().instances().get().execute.return_value = {
                'tags': {
                    'items': ['a tag', 'another tag'],
                    'fingerprint': u'🖐'}}

        mock_get_res.side_effect = lambda x: x

        instance.remove_instance_tag('instance', ['a tag'])

        mock_build().instances().setTags.assert_called_once_with(
            body={
                'items': ['another tag'],
                'fingerprint': u'🖐'},
            project='not really a project',
            instance='instance',
            zone='a very fake zone'
            )

    def test_contained_in(self, *args):
        self.ctxmock.source.instance.runtime_properties = {}
        self.ctxmock.target.instance.runtime_properties = {
                'ssh_keys': '🗝🔑🗝',
                }

        instance.contained_in()

        self.assertEqual(
                '🗝🔑🗝',
                self.ctxmock.source.instance.runtime_properties['ssh_keys'])
