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
import asyncio
import datetime
import json
import logging
import time
import uuid

from osm_policy_module.common.common_db_client import CommonDbClient
from osm_policy_module.common.message_bus_client import MessageBusClient
from osm_policy_module.core.config import Config

log = logging.getLogger(__name__)


class LcmClient:
    def __init__(self, config: Config, loop=None):
        self.db_client = CommonDbClient(config)
        self.msg_bus = MessageBusClient(config)
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop

    async def scale(self, nsr_id: str, scaling_group_name: str, vnf_member_index: str, action: str):
        log.debug("scale %s %s %s %s", nsr_id, scaling_group_name, vnf_member_index, action)
        nslcmop = self._generate_nslcmop(nsr_id, scaling_group_name, vnf_member_index, action)
        self.db_client.create_nslcmop(nslcmop)
        log.debug("Sending scale action message: %s", json.dumps(nslcmop))
        await self.msg_bus.aiowrite("ns", "scale", nslcmop)

    def _generate_nslcmop(self, nsr_id: str, scaling_group_name: str, vnf_member_index: str, action: str):
        log.debug("_generate_nslcmop %s %s %s %s", nsr_id, scaling_group_name, vnf_member_index, action)
        _id = str(uuid.uuid4())
        now = time.time()
        params = {
            "scaleType": "SCALE_VNF",
            "scaleVnfData": {
                "scaleVnfType": action.upper(),
                "scaleByStepData": {
                    "scaling-group-descriptor": scaling_group_name,
                    "member-vnf-index": vnf_member_index
                }
            },
            "scaleTime": "{}Z".format(datetime.datetime.utcnow().isoformat())
        }

        nslcmop = {
            "id": _id,
            "_id": _id,
            "operationState": "PROCESSING",
            "statusEnteredTime": now,
            "nsInstanceId": nsr_id,
            "lcmOperationType": "scale",
            "startTime": now,
            "isAutomaticInvocation": True,
            "operationParams": params,
            "isCancelPending": False,
            "links": {
                "self": "/osm/nslcm/v1/ns_lcm_op_occs/" + _id,
                "nsInstance": "/osm/nslcm/v1/ns_instances/" + nsr_id,
            }
        }
        return nslcmop
