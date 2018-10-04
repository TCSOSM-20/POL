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

from osm_policy_module.common.db_client import DbClient
from osm_policy_module.common.lcm_client import LcmClient
from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core import database
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import ScalingGroup, ScalingAlarm, ScalingPolicy, ScalingCriteria

log = logging.getLogger(__name__)

ALLOWED_KAFKA_KEYS = ['instantiated', 'scaled', 'notify_alarm']


class PolicyModuleAgent:
    def __init__(self):
        cfg = Config.instance()
        self.db_client = DbClient()
        self.mon_client = MonClient()
        self.lcm_client = LcmClient()
        self.kafka_server = '{}:{}'.format(cfg.OSMPOL_MESSAGE_HOST,
                                           cfg.OSMPOL_MESSAGE_PORT)

    def run(self):
        consumer = KafkaConsumer(bootstrap_servers=self.kafka_server,
                                 key_deserializer=bytes.decode,
                                 value_deserializer=bytes.decode,
                                 group_id='pol-consumer')
        consumer.subscribe(["ns", "alarm_response"])

        for message in consumer:
            t = threading.Thread(target=self._process_msg, args=(message.topic, message.key, message.value,))
            t.start()

    def _process_msg(self, topic, key, msg):
        try:
            log.debug("Message arrived with topic: %s, key: %s, msg: %s", topic, key, msg)
            if key in ALLOWED_KAFKA_KEYS:
                try:
                    content = json.loads(msg)
                except JSONDecodeError:
                    content = yaml.safe_load(msg)

                if key == 'instantiated' or key == 'scaled':
                    self._handle_instantiated_or_scaled(content)

                if key == 'notify_alarm':
                    self._handle_alarm_notification(content)
            else:
                log.debug("Key %s is not in ALLOWED_KAFKA_KEYS", key)
        except Exception:
            log.exception("Error consuming message: ")

    def _handle_alarm_notification(self, content):
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
            log.info("Sending scaling action message for ns: %s", alarm_id)
            self.lcm_client.scale(alarm.scaling_record.nsr_id, alarm.scaling_record.name, alarm.vnf_member_index,
                                  alarm.action)
        except ScalingAlarm.DoesNotExist:
            log.info("There is no action configured for alarm %s.", alarm_id)

    def _handle_instantiated_or_scaled(self, content):
        nslcmop_id = content['nslcmop_id']
        nslcmop = self.db_client.get_nslcmop(nslcmop_id)
        if nslcmop['operationState'] == 'COMPLETED' or nslcmop['operationState'] == 'PARTIALLY_COMPLETED':
            nsr_id = nslcmop['nsInstanceId']
            log.info("Configuring scaling groups for network service with nsr_id: %s", nsr_id)
            self._configure_scaling_groups(nsr_id)
        else:
            log.info(
                "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                nslcmop['operationState'])

    def _configure_scaling_groups(self, nsr_id: str):
        # TODO(diazb): Check for alarm creation on exception and clean resources if needed.
        with database.db.atomic():
            vnfrs = self.db_client.get_vnfrs(nsr_id)
            log.info("Checking %s vnfrs...", len(vnfrs))
            for vnfr in vnfrs:
                vnfd = self.db_client.get_vnfd(vnfr['vnfd-id'])
                log.info("Looking for vnfd %s", vnfr['vnfd-id'])
                scaling_groups = vnfd['scaling-group-descriptor']
                vnf_monitoring_params = vnfd['monitoring-param']
                for scaling_group in scaling_groups:
                    try:
                        scaling_group_record = ScalingGroup.select().where(
                            ScalingGroup.nsr_id == nsr_id,
                            ScalingGroup.name == scaling_group['name']
                        ).get()
                    except ScalingGroup.DoesNotExist:
                        log.info("Creating scaling group record in DB...")
                        scaling_group_record = ScalingGroup.create(
                            nsr_id=nsr_id,
                            name=scaling_group['name'],
                            content=json.dumps(scaling_group)
                        )
                        log.info("Created scaling group record in DB : nsr_id=%s, name=%s, content=%s",
                                 scaling_group_record.nsr_id,
                                 scaling_group_record.name,
                                 scaling_group_record.content)
                    for scaling_policy in scaling_group['scaling-policy']:
                        if scaling_policy['scaling-type'] != 'automatic':
                            continue
                        try:
                            scaling_policy_record = ScalingPolicy.select().join(ScalingGroup).where(
                                ScalingPolicy.name == scaling_policy['name'],
                                ScalingGroup.id == scaling_group_record.id
                            ).get()
                        except ScalingPolicy.DoesNotExist:
                            log.info("Creating scaling policy record in DB...")
                            scaling_policy_record = ScalingPolicy.create(
                                nsr_id=nsr_id,
                                name=scaling_policy['name'],
                                scaling_group=scaling_group_record
                            )
                            log.info("Created scaling policy record in DB : name=%s, scaling_group.name=%s",
                                     scaling_policy_record.nsr_id,
                                     scaling_policy_record.scaling_group.name)
                        for vdu in vnfd['vdu']:
                            vdu_monitoring_params = vdu['monitoring-param']
                            for scaling_criteria in scaling_policy['scaling-criteria']:
                                try:
                                    scaling_criteria_record = ScalingCriteria.select().join(ScalingPolicy).where(
                                        ScalingPolicy.id == scaling_policy_record.id,
                                        ScalingCriteria.name == scaling_criteria['name']
                                    ).get()
                                except ScalingCriteria.DoesNotExist:
                                    log.info("Creating scaling criteria record in DB...")
                                    scaling_criteria_record = ScalingCriteria.create(
                                        nsr_id=nsr_id,
                                        name=scaling_policy['name'],
                                        scaling_policy=scaling_policy_record
                                    )
                                    log.info(
                                        "Created scaling criteria record in DB : name=%s, scaling_criteria.name=%s",
                                        scaling_criteria_record.name,
                                        scaling_criteria_record.scaling_policy.name)
                                vnf_monitoring_param = next(
                                    filter(lambda param: param['id'] == scaling_criteria['vnf-monitoring-param-ref'],
                                           vnf_monitoring_params))
                                # TODO: Add support for non-nfvi metrics
                                vdu_monitoring_param = next(
                                    filter(
                                        lambda param: param['id'] == vnf_monitoring_param['vdu-monitoring-param-ref'],
                                        vdu_monitoring_params))
                                vdurs = list(filter(lambda vdur: vdur['vdu-id-ref'] == vnf_monitoring_param['vdu-ref'],
                                                    vnfr['vdur']))
                                for vdur in vdurs:
                                    try:
                                        ScalingAlarm.select().where(
                                            ScalingAlarm.vdu_name == vdur['name']
                                        ).where(
                                            ScalingAlarm.scaling_criteria.name == scaling_criteria['name']
                                        ).get()
                                        log.debug("VDU %s already has an alarm configured")
                                        continue
                                    except ScalingAlarm.DoesNotExist:
                                        pass
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
                                        scaling_criteria=scaling_criteria_record
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
                                        scaling_criteria=scaling_criteria_record
                                    )
