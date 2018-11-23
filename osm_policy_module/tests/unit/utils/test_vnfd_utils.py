# -*- coding: utf-8 -*-

# Copyright 2018 Whitestack, LLC
# *************************************************************

# This file is part of OSM Monitoring module
# All Rights Reserved to Whitestack, LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at

#         http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# For those usages not covered by the Apache License, Version 2.0 please
# contact: bdiaz@whitestack.com or glavado@whitestack.com
##
import os
import unittest

import yaml

from osm_policy_module.utils.vnfd import VnfdUtils


class VnfdUtilsTest(unittest.TestCase):
    def test_get_mgmt_vdu_by_cp(self):
        with open(
                os.path.join(os.path.dirname(__file__), 'examples/cirros_vdu_scaling_vnfd_1.yaml'), 'r') as file:
            vnfd = yaml.safe_load(file)['vnfd:vnfd-catalog']['vnfd'][0]
            vdu = VnfdUtils.get_mgmt_vdu(vnfd)
            self.assertEqual(vdu['id'], 'cirros_vnfd-VM')

    def test_get_mgmt_vdu_by_id(self):
        with open(
                os.path.join(os.path.dirname(__file__), 'examples/cirros_vdu_scaling_vnfd_2.yaml'), 'r') as file:
            vnfd = yaml.safe_load(file)['vnfd:vnfd-catalog']['vnfd'][0]
            vdu = VnfdUtils.get_mgmt_vdu(vnfd)
            self.assertEqual(vdu['id'], 'cirros_vnfd-VM')
