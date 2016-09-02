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

from time import sleep

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

from .. import utils
from .dns import DNSZone


def get_current_records(zone, name=None, type=None):
    """Expects a DNSZone object and the DNS name and record type to filter
    on"""
    return zone.list_records(name=name, type=type)


def get_current_data(zone, name, type):
    return get_current_records(zone, name, type)['rrsets'][0]['rrdatas']


def generate_changes(dns_zone, action, data):
    """
    Produces a change request (additions, deletions) with the specified data
    """
    return dns_zone.discovery.changes().create(
            project=utils.get_gcp_config()['project'],
            managedZone=dns_zone.name,
            body={action: data})


def wait_for_change_completion(dns_zone, response):
    while response['status'] == 'pending':
        response = dns_zone.discovery.changes().get(
                project=utils.get_gcp_config()['project'],
                managedZone=dns_zone.name,
                changeId=response['id'],
                )
    return response


@operation
@utils.throw_cloudify_exceptions
def create(type, name, resources, ttl, **kwargs):
    ctx.instance.runtime_properties['created'] = False

    gcp_config = utils.get_gcp_config()

    zone = [
        rel.target.instance
        for rel in ctx.relationships
        if rel.type == 'cloudify.relationships.dns_record_contained_in_zone'
        ]

    dns_zone = DNSZone(
            gcp_config,
            ctx.logger,
            zone.runtime_properties['name'],
            )

    response = generate_changes(dns_zone.name, 'additions', {
            "name": '{}.{}'
                    .format(name, zone.runtime_properties['dnsName']),
            "ttl": ttl,
            "type": ctx.node.properties['type'],
            "rrdatas": resources,
        }).execute()

    while response['status'] == 'pending':
        sleep(2)
        response = dns_zone.discovery.changes().get(
                project=gcp_config['project'],
                managedZone=zone.runtime_properties['name'],
                changeId=response['id'],
                )

    if response['status'] != 'done':
        raise NonRecoverableError('unexpected response status: {}'.format(
            response))

    ctx.instance.runtime_properties['created'] = True


@operation
@utils.retry_on_failure('Retrying deleting DNS Record')
@utils.throw_cloudify_exceptions
def delete(**kwargs):
    gcp_config = utils.get_gcp_config()
    if ctx.instance.runtime_properties.get('created'):
        dns_zone = DNSZone(
                gcp_config,
                ctx.logger,
                ctx.instance.runtime_properties['name'])

        rrsets = get_current_records(
                dns_zone,
                name=ctx.instance.runtime_properties['name'],
                type=ctx.node.properties['type'],
                )

        wait_for_change_completion(
                generate_changes(dns_zone.name, 'deletions', rrsets))

        ctx.instance.runtime_properties.pop('created', None)


def validate_contained_in(**kwargs):
    if (ctx.target.type != 'cloudify.gcp.nodes.DNSZone' or
            ctx.source.type != 'cloudify.gcp.nodes.DNSRecord'):
        raise NonRecoverableError(
                'Unsupported types for {} relationship'.format(ctx.type))
