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
import json
import logging
import threading
from json import JSONDecodeError

import yaml
from kafka import KafkaConsumer
from osm_common import dbmongo

from osm_policy_module.common.lcm_client import LcmClient
from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core import database
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import ScalingRecord, ScalingAlarm

log = logging.getLogger(__name__)


class PolicyModuleAgent:
    def __init__(self):
        cfg = Config.instance()
        self.common_db = dbmongo.DbMongo()
        self.common_db.db_connect({'host': cfg.OSMPOL_DATABASE_HOST,
                                   'port': int(cfg.OSMPOL_DATABASE_PORT),
                                   'name': 'osm'})
        self.mon_client = MonClient()
        self.kafka_server = '{}:{}'.format(cfg.OSMPOL_MESSAGE_HOST,
                                           cfg.OSMPOL_MESSAGE_PORT)

    def run(self):
        cfg = Config.instance()
        cfg.read_environ()

        consumer = KafkaConsumer(bootstrap_servers=self.kafka_server,
                                 key_deserializer=bytes.decode,
                                 value_deserializer=bytes.decode,
                                 consumer_timeout_ms=10000)
        consumer.subscribe(["ns", "alarm_response"])

        for message in consumer:
            t = threading.Thread(target=self._process_msg, args=(message.topic, message.key, message.value,))
            t.start()

    def _process_msg(self, topic, key, msg):
        try:
            # Check for ns instantiation
            if key == 'instantiated':
                try:
                    content = json.loads(msg)
                except JSONDecodeError:
                    content = yaml.safe_load(msg)
                log.info("Message arrived with topic: %s, key: %s, msg: %s", topic, key, content)
                nslcmop_id = content['nslcmop_id']
                nslcmop = self.common_db.get_one(table="nslcmops",
                                                 filter={"_id": nslcmop_id})
                if nslcmop['operationState'] == 'COMPLETED' or nslcmop['operationState'] == 'PARTIALLY_COMPLETED':
                    nsr_id = nslcmop['nsInstanceId']
                    log.info("Configuring scaling groups for network service with nsr_id: %s", nsr_id)
                    self._configure_scaling_groups(nsr_id)
                else:
                    log.info(
                        "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                        "Current state is %s. Skipping...",
                        nslcmop['operationState'])

            if key == 'notify_alarm':
                try:
                    content = json.loads(msg)
                except JSONDecodeError:
                    content = yaml.safe_load(msg)
                log.info("Message arrived with topic: %s, key: %s, msg: %s", topic, key, content)
                alarm_id = content['notify_details']['alarm_uuid']
                metric_name = content['notify_details']['metric_name']
                operation = content['notify_details']['operation']
                threshold = content['notify_details']['threshold_value']
                vdu_name = content['notify_details']['vdu_name']
                vnf_member_index = content['notify_details']['vnf_member_index']
                ns_id = content['notify_details']['ns_id']
                log.info(
                    "Received alarm notification for alarm %s, \
                    metric %s, \
                    operation %s, \
                    threshold %s, \
                    vdu_name %s, \
                    vnf_member_index %s, \
                    ns_id %s ",
                    alarm_id, metric_name, operation, threshold, vdu_name, vnf_member_index, ns_id)
                try:
                    alarm = ScalingAlarm.select().where(ScalingAlarm.alarm_id == alarm_id).get()
                    lcm_client = LcmClient()
                    log.info("Sending scaling action message for ns: %s", alarm_id)
                    lcm_client.scale(alarm.scaling_record.nsr_id, alarm.scaling_record.name, alarm.vnf_member_index,
                                     alarm.action)
                except ScalingAlarm.DoesNotExist:
                    log.info("There is no action configured for alarm %s.", alarm_id)
        except Exception:
            log.exception("Error consuming message: ")

    def _get_vnfr(self, nsr_id: str, member_index: int):
        vnfr = self.common_db.get_one(table="vnfrs",
                                      filter={"nsr-id-ref": nsr_id, "member-vnf-index-ref": str(member_index)})
        return vnfr

    def _get_vnfrs(self, nsr_id: str):
        return [self._get_vnfr(nsr_id, member['member-vnf-index']) for member in
                self._get_nsr(nsr_id)['nsd']['constituent-vnfd']]

    def _get_vnfd(self, vnfd_id: str):
        vnfr = self.common_db.get_one(table="vnfds",
                                      filter={"_id": vnfd_id})
        return vnfr

    def _get_nsr(self, nsr_id: str):
        nsr = self.common_db.get_one(table="nsrs",
                                     filter={"id": nsr_id})
        return nsr

    def _configure_scaling_groups(self, nsr_id: str):
        # TODO(diazb): Check for alarm creation on exception and clean resources if needed.
        with database.db.atomic():
            vnfrs = self._get_vnfrs(nsr_id)
            log.info("Checking %s vnfrs...", len(vnfrs))
            for vnfr in vnfrs:
                vnfd = self._get_vnfd(vnfr['vnfd-id'])
                log.info("Looking for vnfd %s", vnfr['vnfd-id'])
                scaling_groups = vnfd['scaling-group-descriptor']
                vnf_monitoring_params = vnfd['monitoring-param']
                for scaling_group in scaling_groups:
                    log.info("Creating scaling record in DB...")
                    scaling_record = ScalingRecord.create(
                        nsr_id=nsr_id,
                        name=scaling_group['name'],
                        content=json.dumps(scaling_group)
                    )
                    log.info("Created scaling record in DB : nsr_id=%s, name=%s, content=%s",
                             scaling_record.nsr_id,
                             scaling_record.name,
                             scaling_record.content)
                    for scaling_policy in scaling_group['scaling-policy']:
                        for vdur in vnfd['vdu']:
                            vdu_monitoring_params = vdur['monitoring-param']
                            for scaling_criteria in scaling_policy['scaling-criteria']:
                                vnf_monitoring_param = next(
                                    filter(lambda param: param['id'] == scaling_criteria['vnf-monitoring-param-ref'],
                                           vnf_monitoring_params))
                                # TODO: Add support for non-nfvi metrics
                                vdu_monitoring_param = next(
                                    filter(
                                        lambda param: param['id'] == vnf_monitoring_param['vdu-monitoring-param-ref'],
                                        vdu_monitoring_params))
                                alarm_uuid = self.mon_client.create_alarm(
                                    metric_name=vdu_monitoring_param['nfvi-metric'],
                                    ns_id=nsr_id,
                                    vdu_name=vdur['name'],
                                    vnf_member_index=vnfr['member-vnf-index-ref'],
                                    threshold=scaling_criteria['scale-in-threshold'],
                                    operation=scaling_criteria['scale-in-relational-operation'],
                                    statistic=vnf_monitoring_param['aggregation-type']
                                )
                                ScalingAlarm.create(
                                    alarm_id=alarm_uuid,
                                    action='scale_in',
                                    vnf_member_index=int(vnfr['member-vnf-index-ref']),
                                    vdu_name=vdur['name'],
                                    scaling_record=scaling_record
                                )
                                alarm_uuid = self.mon_client.create_alarm(
                                    metric_name=vdu_monitoring_param['nfvi-metric'],
                                    ns_id=nsr_id,
                                    vdu_name=vdur['name'],
                                    vnf_member_index=vnfr['member-vnf-index-ref'],
                                    threshold=scaling_criteria['scale-out-threshold'],
                                    operation=scaling_criteria['scale-out-relational-operation'],
                                    statistic=vnf_monitoring_param['aggregation-type']
                                )
                                ScalingAlarm.create(
                                    alarm_id=alarm_uuid,
                                    action='scale_out',
                                    vnf_member_index=int(vnfr['member-vnf-index-ref']),
                                    vdu_name=vdur['name'],
                                    scaling_record=scaling_record
                                )
