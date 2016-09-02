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

from copy import copy
import os

from cosmo_tester.framework.testenv import TestCase
from cloudify.workflows import local
from cloudify_cli import constants as cli_constants


class GCPDNSTest(TestCase):
    def setUp(self):
        super(GCPDNSTest, self).setUp()

        self.ext_inputs = {
                k: self.env.cloudify_config[k]
                for k in (
                    'gcp_auth',
                    'project',
                    'zone',
                )}

        blueprints_path = os.path.split(os.path.abspath(__file__))[0]
        blueprints_path = os.path.split(blueprints_path)[0]
        self.blueprints_path = os.path.join(
            blueprints_path,
            'resources',
            'dns'
        )

    def test_blueprint(self):
        blueprint = os.path.join(
            self.blueprints_path,
            'simple-blueprint.yaml'
        )

        if self.env.install_plugins:
            self.logger.info('installing required plugins')
            self.cfy.install_plugins_locally(
                blueprint_path=blueprint)

        self.logger.info('Creating a new DNS Zone')

        inputs = copy(self.ext_inputs)

        self.dns_env = local.init_env(
            blueprint,
            inputs=inputs,
            name=self._testMethodName,
            ignored_modules=cli_constants.IGNORED_LOCAL_WORKFLOW_MODULES)

        self.addCleanup(
                self.dns_env.execute,
                'uninstall',
                task_retries=10,
                task_retry_interval=3,
                )

        self.dns_env.execute(
            'install',
            task_retries=10,
            task_retry_interval=3,
        )

        outputs = self.dns_env.outputs()
