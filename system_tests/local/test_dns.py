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

from time import sleep

import dns.resolver

from cosmo_tester.framework.testenv import TestCase

from . import GCPTest


class GCPDNSTestB(GCPTest, TestCase):
    blueprint_name = 'dns/simple-blueprint.yaml'

    inputs = (
            'gcp_auth',
            'project',
            'zone',
            'network',
            )

    def assertions(self):

        # get the GCP nameservers as an IP addresses
        res = dns.resolver.Resolver()
        dns_ips = [
                res.query(address, 'A').response.answer[0][0].address
                for address
                in self.outputs['nameservers']
                ]
        # replace the resolver's nameservers
        res.nameservers = dns_ips

        print('sleeping for 30s to allow NSs to catch up...')
        sleep(30)

        for subdomain, ip in [
                ['direct-to-ip', self.outputs['ip']],
                ['test', self.outputs['ip']],
                ['literal-only', '10.9.8.7'],
                ['names-are-relative', '127.3.4.5'],
                ]:
            self.assertEqual(
                    ip,
                    res.query(
                        '{}.getcloudify.org.'.format(subdomain),
                        'A',
                        ).response.answer[0][0].address)
