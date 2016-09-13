# #######
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

from cloudify import ctx
from cloudify.decorators import operation

from .. import utils
from cloudify_gcp.gcp import GoogleCloudPlatform
from cloudify_gcp.gcp import check_response


class FirewallRule(GoogleCloudPlatform):
    def __init__(self,
                 config,
                 logger,
                 name,
                 network,
                 allowed=None,
                 sources=None,
                 tags=None,
                 security_group=False,
                 ):
        """
        Create Firewall rule object

        :param config:
        :param logger:
        :param firewall: firewall dictionary with a following structure:
        firewall = {'name': 'firewallname',
                    'allowed: [{ 'IPProtocol': 'tcp', 'ports': ['80']}],
                    'sourceRanges':['0.0.0.0/0'],
                    'sourceTags':['tag'], (optional)
                    'targetTags':['tag2'] (optional)
                    }
        ref. https://cloud.google.com/compute/docs/reference/latest/firewalls
        :param network: network name the firewall rule is connected to
        """
        super(FirewallRule, self).__init__(config, logger, ctx.instance.id)

        if utils.should_use_external_resource():
            self.name = utils.assure_resource_id_correct()
        elif name:
            self.name = utils.get_gcp_resource_name(name)
        else:
            self.name = utils.get_gcp_resource_name(ctx.instance.id)

        self.network = network
        self.allowed, self.sources, self.tags = allowed, sources, tags

        self.security_group = security_group

    @check_response
    def create(self):
        """
        Create GCP firewall rule in a GCP network.
        Global operation.

        :return: REST response with operation responsible for the firewall rule
        creation process and its status
        """
        self.logger.info(
            'Create firewall rule {0} in network {1}'.format(
                self.name,
                self.network))

        return self.discovery.firewalls().insert(
            project=self.project,
            body=self.to_dict()).execute()

    @check_response
    def delete(self):
        """
        Delete GCP firewall rule from GCP network.
        Global operation.

        :return: REST response with operation responsible for the firewall rule
        deletion process and its status
        """
        self.logger.info(
            'Delete firewall rule {0} from network {1}'.format(
                self.name,
                self.network))

        return self.discovery.firewalls().delete(
            project=self.project,
            firewall=self.name).execute()

    @check_response
    def get(self):
        """
        Get GCP firewall rule details.

        :return: REST response with operation responsible for the firewall
        rule details retrieval
        """
        self.logger.info('Get firewall rule {0} details'.format(self.name))

        return self.discovery.firewalls().get(
            project=self.project,
            firewall=self.name).execute()

    @check_response
    def update(self):
        """
        Update GCP firewall rule.
        Global operation.

        :return: REST response with operation responsible for the firewall rule
        update process and its status
        """
        self.logger.info('Update firewall rule {0}'.format(self.name))

        return self.discovery.firewalls().update(
            project=self.project,
            firewall=self.name,
            body=self.firewall).execute()

    @check_response
    def list(self):
        """
        List GCP firewall rules in all networks.

        :return: REST response with list of firewall rules in a project
        """
        self.logger.info(
            'List firewall rules in project {0}'.format(self.project))

        return self.discovery.firewalls().list(
            project=self.project).execute()

    def to_dict(self):
        body = {
            'name': self.name,
            'description': 'Cloudify generated {}'.format(
                'SG part' if self.security_group else 'FirewallRule'),
            'network': self.network,
            'allowed': [],
            'sourceTags': [],
            'sourceRanges': [],
            }

        for source in self.sources:
            if source[0].isdigit():
                body['sourceRanges'].append(source)
            else:
                body['sourceTags'].append(source)

        for k, v in self.allowed.items():
            rule = {'IPProtocol': k}
            if v:
                rule['ports'] = v
            body['allowed'].append(rule)

        if self.tags:
            body['targetTags'] = self.tags

        return body


@operation
@utils.throw_cloudify_exceptions
def create(name, allowed, sources, target_tags, **kwargs):
    gcp_config = utils.get_gcp_config()
    network = utils.get_network(ctx)

    firewall = FirewallRule(gcp_config,
                            ctx.logger,
                            network=network,
                            name=name,
                            allowed=allowed,
                            sources=sources,
                            tags=target_tags,
                            )

    utils.create(firewall)
    ctx.instance.runtime_properties['name'] = firewall.name


@operation
@utils.retry_on_failure('Retrying deleting firewall rule')
@utils.throw_cloudify_exceptions
def delete(**kwargs):
    gcp_config = utils.get_gcp_config()
    firewall_name = ctx.instance.runtime_properties.get('name', None)
    if firewall_name:
        network = utils.get_network(ctx)
        firewall = FirewallRule(gcp_config,
                                ctx.logger,
                                name=ctx.instance.runtime_properties['name'],
                                network=network)
        utils.delete_if_not_external(firewall)
        ctx.instance.runtime_properties.pop('name', None)


@operation
@utils.retry_on_failure('Retrying creating security group')
@utils.throw_cloudify_exceptions
def create_security_group(name, rules, **kwargs):
    gcp_config = utils.get_gcp_config()
    network = utils.get_network(ctx)
    name = utils.get_gcp_resource_name(
            'ctx-sg-{}'.format(name if name else ctx.instance.id))

    firewalls = [
        FirewallRule(
                gcp_config,
                ctx.logger,
                name=create_rule_name(name, rule),
                network=network,
                allowed=rule['allowed'],
                sources=rule['sources'],
                tags=[name],
                security_group=True,
                )
        for rule in rules]

    ctx.instance.runtime_properties['name'] = name
    return handle_multiple_calls(firewalls, 'create', ctx.logger)


def create_rule_name(name, rule):
    """
    Produce a gcp compatible rule name
    """
    rule_name = '{name}-from-{rule[sources]}-to-{rule[allowed]}'.format(
            name=name,
            rule=rule)
    return utils.get_gcp_resource_name(rule_name)


@utils.retry_on_failure('Retrying creating security group')
@utils.throw_cloudify_exceptions
def configure_security_group(**kwargs):
    props = ctx.instance.runtime_properties
    props['rules'] = []
    network = utils.get_network(ctx)
    for name, op in props['_operations'].items():
        firewall = FirewallRule(
                utils.get_gcp_config(),
                ctx.logger,
                network=network,
                name=name,
                )
        props['rules'].append(firewall.get())
    del props['_operations']


def handle_multiple_calls(objects, call, logger):
    """
    Manage running several API calls which all must succeed for the node to be
    successfully created.

    objects must be passed in a consistent order or bad things will happen.
    """
    props = ctx.instance.runtime_properties
    # Can be removed when
    # https://github.com/cloudify-cosmo/cloudify-plugins-common/pull/251
    # is finished:
    props.dirty = True
    operations = props.setdefault('_operations', {})

    for obj in objects:
        if obj.name in operations:
            if operations[obj.name]['status'] == 'DONE':
                # This one is finished
                continue
            else:
                op = utils.response_to_operation(
                        operations[obj.name],
                        utils.get_gcp_config(),
                        logger,
                        )
                operations[obj.name] = op.get()
        else:
            operations[obj.name] = getattr(obj, call)()

    not_done = [k for k, v in operations.items() if v['status'] != 'DONE']
    if not_done:
        return ctx.operation.retry(
                'Rules {} not yet {}d'.format(str(not_done), call))


@operation
@utils.throw_cloudify_exceptions
def delete_security_group(**kwargs):
    gcp_config = utils.get_gcp_config()
    network = utils.get_network(ctx)
    props = ctx.instance.runtime_properties

    firewalls = [
            FirewallRule(
                gcp_config,
                ctx.logger,
                name=rule['name'],
                network=network,
                )
            for rule in props['rules']]

    return handle_multiple_calls(firewalls, 'delete', ctx.logger)
