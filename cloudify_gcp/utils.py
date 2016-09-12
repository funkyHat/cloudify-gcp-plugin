########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

import re
import string
import time
from abc import ABCMeta, abstractmethod
from copy import deepcopy
from functools import wraps

from proxy_tools import Proxy
from googleapiclient.errors import HttpError

from cloudify import ctx
from cloudify.context import CloudifyContext
from cloudify.exceptions import NonRecoverableError

from . import constants
from cloudify_gcp.gcp import GCPError, GoogleCloudPlatform
from cloudify_gcp.gcp import check_response
from cloudify_gcp.gcp import is_missing_resource_error, is_resource_used_error


def camel_farm(identifier):
    """
    Convert from underscored to camelCase.
    """
    words = identifier.split('_')
    return ''.join([words[0]] + map(string.capitalize, words[1:]))


def get_item_from_gcp_response(key_field, key_name, items):
    """
    Get item from GCP REST response JSON list by name.
    items = [{ 'key_field': 'key_name', 'key_field_value': 'value'}]
    :param key_field: item dictionary key
    :param key_value: item dictionary value
    :param items: list of items(dictionaries)
    :return: item if found in collection, None otherwise
    """
    for item in items.get('items', []):
        if item.get(key_field) == key_name:
            return item
    return None


def get_gcp_resource_name(name):
    """
    Create GCP accepted name of resource. From GCP specification:
    "Specifically, the name must be 1-63 characters long and match the regular
    expression [a-z]([-a-z0-9]*[a-z0-9])? which means the first character must
    be a lowercase letter, and all following characters must be a dash,
    lowercase letter, or digit, except the last character,
    which cannot be a dash."
    :param name: name of resource to be given
    :return: GCP accepted instance name
    """
    # replace underscores with hyphens
    final_name = name.replace('_', '-')
    # remove all non-alphanumeric characters except hyphens
    final_name = re.sub(r'[^a-zA-Z0-9-]+', '', final_name)
    # assure the first character is alpha
    if not final_name[0].isalpha():
        final_name = '{0}{1}'.format('a', final_name)
    # trim to the length limit
    if len(final_name) > constants.MAX_GCP_NAME:
        remain_len = constants.MAX_GCP_NAME - len(final_name)
        final_name = '{0}{1}'.format(
            final_name[:remain_len - constants.ID_HASH_CONST],
            final_name[-constants.ID_HASH_CONST:])
    # convert string to lowercase
    return final_name.lower()


def should_use_external_resource():
    return ctx.node.properties.get(constants.USE_EXTERNAL_RESOURCE, False)


def assure_resource_id_correct():
    resource_id = ctx.node.properties.get(constants.RESOURCE_ID)
    if not resource_id:
        raise NonRecoverableError('Resource id is missing.')

    if resource_id != get_gcp_resource_name(resource_id):
        raise NonRecoverableError('{} cannot be used as resource id.'
                                  .format(resource_id))
    return resource_id


def get_final_resource_name(name):
    if should_use_external_resource():
        return assure_resource_id_correct()
    else:
        return name or get_gcp_resource_name(ctx.instance.id)


def create_resource(func):
    def _decorator(resource, *args, **kwargs):
        if should_use_external_resource():
            try:
                resource.body = resource.get()
                resource.update_model()
            except HttpError as error:
                if is_missing_resource_error(error):
                    name = ctx.node.properties.get(constants.RESOURCE_ID)
                    raise NonRecoverableError(
                        'Resource {0} defined as external, '
                        'but does not exist. Error: {1}'.
                        format(name, str(error)))
                else:
                    raise error
        else:
            return func(resource, *args, **kwargs)

    return wraps(func)(_decorator)


@create_resource
def create(resource):
    return resource.create()


def delete_if_not_external(resource):
    if not should_use_external_resource():
        resource.delete()


def sync_operation(func):
    def _decorator(resource, *args, **kwargs):
        response = func(resource, *args, **kwargs)
        operation = response_to_operation(
            response, resource.config, resource.logger)
        while not operation.has_finished():
            time.sleep(1)
        return operation.last_response

    return wraps(func)(_decorator)


def retry_on_failure(msg, delay=constants.RETRY_DEFAULT_DELAY):
    def _retry_on_failure(func):
        def _decorator(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HttpError as error:
                if is_resource_used_error(error):
                    ctx.operation.retry(msg, delay)
                else:
                    raise error

        return wraps(func)(_decorator)

    return _retry_on_failure


def throw_cloudify_exceptions(func):
    def _decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except GCPError as e:
            raise NonRecoverableError(e.message)

    return wraps(func)(_decorator)


def get_gcp_config():
    def _get_gcp_config_from_properties():
        try:
            return ctx.node.properties[constants.GCP_CONFIG]
        except NonRecoverableError:
            return ctx.source.node.properties[constants.GCP_CONFIG]

    gcp_config_from_properties = _get_gcp_config_from_properties()
    if gcp_config_from_properties:
        gcp_config = gcp_config_from_properties
    else:
        try:
            config = ctx.provider_context['resources'][constants.GCP_CONFIG]
        except KeyError:
            raise NonRecoverableError(
                    '{} not provided as a property and the provider context '
                    'is not set up either'.format(constants.GCP_CONFIG))
        gcp_config = deepcopy(config)

    return update_zone(gcp_config)


def update_zone(gcp_config):
    def _get_zone_from_runtime_properties():
        try:
            return ctx.instance.runtime_properties.get(constants.GCP_ZONE)
        except NonRecoverableError:
            src = ctx.source.instance.runtime_properties
            tar = ctx.target.instance.runtime_properties
            return src.get(constants.GCP_ZONE) or tar.get(constants.GCP_ZONE)

    non_default_zone = _get_zone_from_runtime_properties()
    if non_default_zone:
        gcp_config['zone'] = non_default_zone

    return gcp_config


def get_manager_provider_config():
    provider_config = ctx.provider_context.get('resources', {})
    agents_security_group = provider_config.get('agents_security_group', {})
    manager_agent_security_group = \
        provider_config.get('manager_agent_security_group', {})
    provider_context = {
        'agents_security_group': agents_security_group,
        'manager_security_group': manager_agent_security_group
    }
    return provider_context


def is_object_deleted(obj):
    try:
        obj.get()
    except HttpError as error:
        if is_missing_resource_error(error):
            return True
    return False


def is_manager_instance():
    return not ctx.provider_context


def get_key_user_string(user, public_key):
    cleaned_user = re.sub(r'\s+', ' ', user).strip()
    cleaned_public_key = re.sub(r'\s+', ' ', public_key).strip()

    if cleaned_public_key.count(' ') >= 1:
        keytype, key_blob = cleaned_public_key.split(' ')[:2]
    else:
        raise NonRecoverableError('Incorrect format of public key')
    protocol = '{0}:{1}'.format(cleaned_user, keytype)

    return '{0} {1} {2}'.format(protocol, key_blob, cleaned_user)


def get_agent_ssh_key_string():
    try:
        return ctx.provider_context['resources'][
                'cloudify_agent']['public_key']
    except KeyError:
        # means that we are bootstrapping the manager
        return ''


def response_to_operation(response, config, logger):
    operation_name = response['name']

    if 'zone' in response:
        return ZoneOperation(config, logger, operation_name)
    elif 'region' in response:
        raise NonRecoverableError('RegionOperation is not implemented')
    else:
        return GlobalOperation(config, logger, operation_name)


class Operation(GoogleCloudPlatform):
    __metaclass__ = ABCMeta

    def __init__(self, config, logger, name):
        super(Operation, self).__init__(config, logger, name)
        self.last_response = None
        self.last_status = None

    def has_finished(self):
        if self.last_status != constants.GCP_OP_DONE:
            self.get()

        return self.last_status == constants.GCP_OP_DONE

    @check_response
    def get(self):
        self.last_response = self._get()
        self.last_status = self.last_response['status']
        return self.last_response

    @abstractmethod
    def _get(self): pass


class GlobalOperation(Operation):
    def _get(self):
        return self.discovery.globalOperations().get(
            project=self.project,
            operation=self.name).execute()


class ZoneOperation(Operation):
    def _get(self):
        return self.discovery.zoneOperations().get(
            project=self.project,
            zone=self.zone,
            operation=self.name).execute()


def get_relationships(
        relationships,
        filter_relationships=None,
        filter_nodes=None):
    """
    Get all relationships of a particular node or the current context.

    Optionally filter based on relationship type, node type.
    """
    if isinstance(relationships, (CloudifyContext, Proxy)):
        # Shortcut to support supplying ctx directly
        relationships = relationships.instance.relationships
    # And coerce the other inputs to lists if they are strings:
    if isinstance(filter_relationships, basestring):
        filter_relationships = [filter_relationships]
    if isinstance(filter_nodes, basestring):
        filter_nodes = [filter_nodes]
    results = []
    for rel in relationships:
        if filter_relationships and rel.type not in filter_relationships:
            rel = None
        if filter_nodes and rel.target.node.type not in filter_nodes:
            rel = None
        if rel:
            results.append(rel)
    return results


def get_network(ctx):
    """
    Get the containing network for the current node.

    Returns either the network the node is contained in, or the network
    specified in the GCP config.
    """

    rels = get_relationships(
            ctx,
            filter_relationships='cloudify.gcp.relationships.'
                                 'contained_in_network')
    if rels:
        network = rels[0].target.instance.runtime_properties['name']
    else:
        network = get_gcp_config()['network']

    if network == 'default':
        network = 'global/networks/default'

    return network
