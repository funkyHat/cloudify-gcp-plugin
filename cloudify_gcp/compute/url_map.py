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
from cloudify.exceptions import NonRecoverableError

from .. import utils
from .. import constants
from ..utils import operation
from cloudify_gcp.gcp import (
        check_response,
        GoogleCloudPlatform,
        )


class UrlMap(GoogleCloudPlatform):
    def __init__(self,
                 config,
                 logger,
                 name,
                 default_service=None):
        super(UrlMap, self).__init__(config, logger, name)
        self.default_service = default_service

    def to_dict(self):
        body = {
            'description': 'Cloudify generated URL Map',
            'name': self.name,
            'defaultService': self.default_service
        }
        return body

    def get_self_url(self):
        return 'global/urlMaps/{0}'.format(self.name)

    @check_response
    def get(self):
        return self.discovery.urlMaps().get(
            project=self.project,
            urlMap=self.name).execute()

    @check_response
    def list(self):
        return self.discovery.urlMaps().list(project=self.project).execute()

    @check_response
    def create(self):
        return self.discovery.urlMaps().insert(
            project=self.project,
            body=self.to_dict()).execute()

    @check_response
    def delete(self):
        return self.discovery.urlMaps().delete(
            project=self.project,
            urlMap=self.name).execute()


@operation
@utils.throw_cloudify_exceptions
def create(name, default_service, **kwargs):
    props = ctx.instance.runtime_properties
    name = utils.get_final_resource_name(name)
    gcp_config = utils.get_gcp_config()
    url_map = UrlMap(gcp_config,
                     ctx.logger,
                     name,
                     default_service)

    if utils.async_operation():
        props.update(url_map.get())
    else:
        response = utils.create(url_map)
        props['_operation'] = response
        ctx.operation.retry('UrlMap is not yet created. Retrying:',
                            constants.RETRY_DEFAULT_DELAY)


def creation_validation(*args, **kwargs):
    props = ctx.node.properties

    if not props['default_service']:
        raise NonRecoverableError(
                'A default backend service must be supplied as default_service'
                )


@operation
@utils.retry_on_failure('Retrying deleting URL map')
@utils.throw_cloudify_exceptions
def delete(**kwargs):
    gcp_config = utils.get_gcp_config()
    name = ctx.instance.runtime_properties.get(constants.NAME, None)
    if name:
        url_map = UrlMap(gcp_config,
                         ctx.logger,
                         name=name)
        if not utils.async_operation():
            utils.delete_if_not_external(url_map)
            ctx.operation.retry('UrlMap is not yet deleted. Retrying:',
                                constants.RETRY_DEFAULT_DELAY)
