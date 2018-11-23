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
from osm_policy_module.core.exceptions import ManagementVduNotFound


class VnfdUtils:

    @staticmethod
    def get_mgmt_vdu(vnfd: dict):
        if 'cp' in vnfd['mgmt-interface']:
            for vdu in vnfd['vdu']:
                for interface in vdu['interface']:
                    if 'external-connection-point-ref' in interface:
                        if interface['external-connection-point-ref'] == vnfd['mgmt-interface']['cp']:
                            return vdu
        elif 'vdu-id' in vnfd['mgmt-interface']:
            for vdu in vnfd['vdu']:
                if vdu['id'] == vnfd['mgmt-interface']['vdu-id']:
                    return vdu
        raise ManagementVduNotFound("Management vdu not founr in vnfd %s", vnfd['id'])
