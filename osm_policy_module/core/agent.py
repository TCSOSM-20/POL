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
from json import JSONDecodeError

import yaml
from aiokafka import AIOKafkaConsumer

from osm_policy_module.common.common_db_client import CommonDbClient
from osm_policy_module.common.lcm_client import LcmClient
from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core import database
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import ScalingGroup, ScalingAlarm, ScalingPolicy, ScalingCriteria, DatabaseManager

log = logging.getLogger(__name__)

ALLOWED_KAFKA_KEYS = ['instantiated', 'scaled', 'notify_alarm']


class PolicyModuleAgent:
    def __init__(self, loop=None):
        cfg = Config.instance()
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.db_client = CommonDbClient()
        self.mon_client = MonClient(loop=self.loop)
        self.lcm_client = LcmClient(loop=self.loop)
        self.kafka_server = '{}:{}'.format(cfg.OSMPOL_MESSAGE_HOST,
                                           cfg.OSMPOL_MESSAGE_PORT)
        self.database_manager = DatabaseManager()

    def run(self):
        self.loop.run_until_complete(self.start())

    async def start(self):
        consumer = AIOKafkaConsumer(
            "ns",
            "alarm_response",
            loop=self.loop,
            bootstrap_servers=self.kafka_server,
            group_id="pol-consumer",
            key_deserializer=bytes.decode,
            value_deserializer=bytes.decode,
        )
        await consumer.start()
        try:
            async for msg in consumer:
                await self._process_msg(msg.topic, msg.key, msg.value)
        finally:
            await consumer.stop()

    async def _process_msg(self, topic, key, msg):
        log.debug("_process_msg topic=%s key=%s msg=%s", topic, key, msg)
        try:
            if key in ALLOWED_KAFKA_KEYS:
                try:
                    content = json.loads(msg)
                except JSONDecodeError:
                    content = yaml.safe_load(msg)

                if key == 'instantiated' or key == 'scaled':
                    await self._handle_instantiated_or_scaled(content)

                if key == 'notify_alarm':
                    await self._handle_alarm_notification(content)
            else:
                log.debug("Key %s is not in ALLOWED_KAFKA_KEYS", key)
        except Exception:
            log.exception("Error consuming message: ")

    async def _handle_alarm_notification(self, content):
        log.debug("_handle_alarm_notification: %s", content)
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
            alarm = self.database_manager.get_alarm(alarm_id)
            delta = datetime.datetime.now() - alarm.scaling_criteria.scaling_policy.last_scale
            log.debug("last_scale: %s", alarm.scaling_criteria.scaling_policy.last_scale)
            log.debug("now: %s", datetime.datetime.now())
            log.debug("delta: %s", delta)
            if delta.total_seconds() < alarm.scaling_criteria.scaling_policy.cooldown_time:
                log.info("Time between last scale and now is less than cooldown time. Skipping.")
                return
            log.info("Sending scaling action message for ns: %s", alarm_id)
            await self.lcm_client.scale(ns_id,
                                        alarm.scaling_criteria.scaling_policy.scaling_group.name,
                                        alarm.vnf_member_index,
                                        alarm.action)
            alarm.scaling_criteria.scaling_policy.last_scale = datetime.datetime.now()
            alarm.scaling_criteria.scaling_policy.save()
        except ScalingAlarm.DoesNotExist:
            log.info("There is no action configured for alarm %s.", alarm_id)

    async def _handle_instantiated_or_scaled(self, content):
        log.debug("_handle_instantiated_or_scaled: %s", content)
        nslcmop_id = content['nslcmop_id']
        nslcmop = self.db_client.get_nslcmop(nslcmop_id)
        if nslcmop['operationState'] == 'COMPLETED' or nslcmop['operationState'] == 'PARTIALLY_COMPLETED':
            nsr_id = nslcmop['nsInstanceId']
            log.info("Configuring scaling groups for network service with nsr_id: %s", nsr_id)
            await self._configure_scaling_groups(nsr_id)
        else:
            log.info(
                "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                nslcmop['operationState'])

    async def _configure_scaling_groups(self, nsr_id: str):
        log.debug("_configure_scaling_groups: %s", nsr_id)
        # TODO: Add support for non-nfvi metrics
        alarms_created = []
        with database.db.atomic() as tx:
            try:
                vnfrs = self.db_client.get_vnfrs(nsr_id)
                for vnfr in vnfrs:
                    log.info("Processing vnfr: %s", vnfr)
                    vnfd = self.db_client.get_vnfd(vnfr['vnfd-id'])
                    log.info("Looking for vnfd %s", vnfr['vnfd-id'])
                    if 'scaling-group-descriptor' not in vnfd:
                        continue
                    scaling_groups = vnfd['scaling-group-descriptor']
                    vnf_monitoring_params = vnfd['monitoring-param']
                    for scaling_group in scaling_groups:
                        try:
                            scaling_group_record = ScalingGroup.select().where(
                                ScalingGroup.nsr_id == nsr_id,
                                ScalingGroup.vnf_member_index == int(vnfr['member-vnf-index-ref']),
                                ScalingGroup.name == scaling_group['name']
                            ).get()
                            log.info("Found existing scaling group record in DB...")
                        except ScalingGroup.DoesNotExist:
                            log.info("Creating scaling group record in DB...")
                            scaling_group_record = ScalingGroup.create(
                                nsr_id=nsr_id,
                                vnf_member_index=vnfr['member-vnf-index-ref'],
                                name=scaling_group['name'],
                                content=json.dumps(scaling_group)
                            )
                            log.info(
                                "Created scaling group record in DB : nsr_id=%s, vnf_member_index=%s, name=%s",
                                scaling_group_record.nsr_id,
                                scaling_group_record.vnf_member_index,
                                scaling_group_record.name)
                        for scaling_policy in scaling_group['scaling-policy']:
                            if scaling_policy['scaling-type'] != 'automatic':
                                continue
                            try:
                                scaling_policy_record = ScalingPolicy.select().join(ScalingGroup).where(
                                    ScalingPolicy.name == scaling_policy['name'],
                                    ScalingGroup.id == scaling_group_record.id
                                ).get()
                                log.info("Found existing scaling policy record in DB...")
                            except ScalingPolicy.DoesNotExist:
                                log.info("Creating scaling policy record in DB...")
                                scaling_policy_record = ScalingPolicy.create(
                                    nsr_id=nsr_id,
                                    name=scaling_policy['name'],
                                    cooldown_time=scaling_policy['cooldown-time'],
                                    scaling_group=scaling_group_record
                                )
                                log.info("Created scaling policy record in DB : name=%s, scaling_group.name=%s",
                                         scaling_policy_record.name,
                                         scaling_policy_record.scaling_group.name)

                            for scaling_criteria in scaling_policy['scaling-criteria']:
                                try:
                                    scaling_criteria_record = ScalingCriteria.select().join(ScalingPolicy).where(
                                        ScalingPolicy.id == scaling_policy_record.id,
                                        ScalingCriteria.name == scaling_criteria['name']
                                    ).get()
                                    log.info("Found existing scaling criteria record in DB...")
                                except ScalingCriteria.DoesNotExist:
                                    log.info("Creating scaling criteria record in DB...")
                                    scaling_criteria_record = ScalingCriteria.create(
                                        nsr_id=nsr_id,
                                        name=scaling_criteria['name'],
                                        scaling_policy=scaling_policy_record
                                    )
                                    log.info(
                                        "Created scaling criteria record in DB : name=%s, scaling_policy.name=%s",
                                        scaling_criteria_record.name,
                                        scaling_criteria_record.scaling_policy.name)

                                vnf_monitoring_param = next(
                                    filter(
                                        lambda param: param['id'] == scaling_criteria[
                                            'vnf-monitoring-param-ref'
                                        ],
                                        vnf_monitoring_params)
                                )
                                if 'vdu-monitoring-param' in vnf_monitoring_param:
                                    vdurs = list(
                                        filter(
                                            lambda vdur: vdur['vdu-id-ref'] == vnf_monitoring_param
                                            ['vdu-monitoring-param']
                                            ['vdu-ref'],
                                            vnfr['vdur']
                                        )
                                    )
                                elif 'vdu-metric' in vnf_monitoring_param:
                                    vdurs = list(
                                        filter(
                                            lambda vdur: vdur['vdu-id-ref'] == vnf_monitoring_param
                                            ['vdu-metric']
                                            ['vdu-ref'],
                                            vnfr['vdur']
                                        )
                                    )
                                elif 'vnf-metric' in vnf_monitoring_param:
                                    log.warning("vnf-metric is not currently supported.")
                                    continue
                                else:
                                    log.warning(
                                        "Scaling criteria is referring to a vnf-monitoring-param that does not "
                                        "contain a reference to a vdu or vnf metric.")
                                    continue
                                for vdur in vdurs:
                                    log.info("Creating alarm for vdur %s ", vdur)
                                    try:
                                        (ScalingAlarm.select()
                                         .join(ScalingCriteria)
                                         .join(ScalingPolicy)
                                         .join(ScalingGroup)
                                         .where(
                                            ScalingAlarm.vdu_name == vdur['name'],
                                            ScalingCriteria.name == scaling_criteria['name'],
                                            ScalingPolicy.name == scaling_policy['name'],
                                            ScalingGroup.nsr_id == nsr_id
                                        ).get())
                                        log.debug("vdu %s already has an alarm configured", vdur['name'])
                                        continue
                                    except ScalingAlarm.DoesNotExist:
                                        pass
                                    alarm_uuid = await self.mon_client.create_alarm(
                                        metric_name=vnf_monitoring_param['id'],
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
                                    alarm_uuid = await self.mon_client.create_alarm(
                                        metric_name=vnf_monitoring_param['id'],
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

            except Exception as e:
                log.exception("Error configuring scaling groups:")
                tx.rollback()
                if len(alarms_created) > 0:
                    log.info("Cleaning alarm resources in MON")
                    for alarm in alarms_created:
                        await self.mon_client.delete_alarm(*alarm)
                raise e
