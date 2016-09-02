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

from .. import constants
from .. import utils
from cloudify_gcp.gcp import GoogleCloudPlatform
from cloudify_gcp.gcp import check_response


class DNSZone(GoogleCloudPlatform):
    def __init__(self,
                 config,
                 logger,
                 name,
                 dns_name=None,
                 ):
        """
        Create DNSZone object

        :param config: gcp auth file
        :param logger: logger object
        :param network: network dictionary having at least 'name' key

        """
        super(DNSZone, self).__init__(
            config,
            logger,
            utils.get_gcp_resource_name(name),
            discovery='dns',
            )
        self.name = name
        self.dns_name = dns_name

    @check_response
    def create(self):
        """
        Create GCP DNS Zone.
        Global operation.

        :return: REST response with operation responsible for the network
        creation process and its status
        """
        self.logger.info("Create DNS Zone '{0}'".format(self.name))
        return self.discovery.managedZones().create(
                project=self.project,
                body=self.to_dict()).execute()

    @check_response
    def delete(self):
        """
        Delete GCP DNS Zone.
        Global operation

        :param network: network name
        :return: REST response with operation responsible for the network
        deletion process and its status
        """
        self.logger.info("Delete DNS Zone '{0}'".format(self.name))
        return self.discovery.managedZones().delete(
            project=self.project,
            managedZone=self.name).execute()

    def to_dict(self):
        body = {
            'description': 'Cloudify generated DNS Zone',
            'name': self.name,
            'dnsName': self.dns_name,
        }
        self.body.update(body)
        return self.body

    def list_records(self, name=None, type=None):
        rrsets = []

        resources = self.discovery.managedZones().resourceRecordSets()

        request = resources.list(
                project=self.project,
                managedZone=self.name,
                type=type,
                name=name,
                )

        while request is not None:
            response = request.execute()

            rrsets.extend(response['rrsets'])

            request = resources.list_next(
                    previous_request=request,
                    previous_response=response)

        return rrsets


@operation
@utils.throw_cloudify_exceptions
def create(name, dns_name, **kwargs):
    gcp_config = utils.get_gcp_config()
    if not name:
        name = ctx.node.id
    if not dns_name:
        dns_name = name
    name = utils.get_final_resource_name(name)
    dns_zone = DNSZone(
            gcp_config,
            ctx.logger,
            name,
            dns_name)
    utils.create(dns_zone)
    ctx.instance.runtime_properties = dns_zone


@operation
@utils.retry_on_failure('Retrying deleting network')
@utils.throw_cloudify_exceptions
def delete(**kwargs):
    gcp_config = utils.get_gcp_config()
    name = ctx.instance.runtime_properties.get('name')
    if name:
        dns_zone = DNSZone(
                gcp_config,
                ctx.logger,
                name)
        utils.delete_if_not_external(dns_zone)
        ctx.instance.runtime_properties.pop(constants.NAME, None)

        if not utils.is_object_deleted(dns_zone):
            ctx.operation.retry('Zone is not yet deleted. Retrying:',
                                constants.RETRY_DEFAULT_DELAY)
