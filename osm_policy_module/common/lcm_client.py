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
import datetime
import json
import logging
import time
import uuid

from kafka import KafkaProducer
from osm_common import dbmongo

from osm_policy_module.core.config import Config

log = logging.getLogger(__name__)


class LcmClient:
    def __init__(self):
        cfg = Config.instance()
        self.kafka_server = '{}:{}'.format(cfg.OSMPOL_MESSAGE_HOST,
                                           cfg.OSMPOL_MESSAGE_PORT)
        self.producer = KafkaProducer(bootstrap_servers=self.kafka_server,
                                      key_serializer=str.encode,
                                      value_serializer=str.encode)
        self.common_db = dbmongo.DbMongo()
        self.common_db.db_connect({'host': cfg.OSMPOL_DATABASE_HOST,
                                   'port': int(cfg.OSMPOL_DATABASE_PORT),
                                   'name': 'osm'})

    def scale(self, nsr_id: str, scaling_group_name: str, vnf_member_index: int, action: str):
        nslcmop = self._generate_nslcmop(nsr_id, scaling_group_name, vnf_member_index, action)
        self.common_db.create("nslcmops", nslcmop)
        log.info("Sending scale action message: %s", json.dumps(nslcmop))
        self.producer.send(topic='ns', key='scale', value=json.dumps(nslcmop))
        self.producer.flush()

    def _generate_nslcmop(self, nsr_id: str, scaling_group_name: str, vnf_member_index: int, action: str):
        _id = str(uuid.uuid4())
        now = time.time()
        params = {
            "scaleType": "SCALE_VNF",
            "scaleVnfData": {
                "scaleVnfType": action.upper(),
                "scaleByStepData": {
                    "scaling-group-descriptor": scaling_group_name,
                    "member-vnf-index": str(vnf_member_index)
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
