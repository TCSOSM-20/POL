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
import logging

import peewee

from osm_policy_module.autoscaling.service import Service
from osm_policy_module.common.message_bus_client import MessageBusClient
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import ScalingAlarm

log = logging.getLogger(__name__)

ALLOWED_KAFKA_KEYS = ['instantiated', 'scaled', 'terminated', 'notify_alarm']


class PolicyModuleAgent:
    def __init__(self, config: Config, loop=None):
        self.conf = config
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.msg_bus = MessageBusClient(config)
        self.service = Service(config, loop)

    def run(self):
        self.loop.run_until_complete(self.start())

    async def start(self):
        topics = [
            "ns",
            "alarm_response"
        ]
        await self.msg_bus.aioread(topics, self._process_msg)
        log.critical("Exiting...")

    async def _process_msg(self, topic, key, msg):
        log.debug("_process_msg topic=%s key=%s msg=%s", topic, key, msg)
        log.info("Message arrived: %s", msg)
        try:
            if key in ALLOWED_KAFKA_KEYS:

                if key == 'instantiated':
                    await self._handle_instantiated(msg)

                if key == 'scaled':
                    await self._handle_scaled(msg)

                if key == 'terminated':
                    await self._handle_terminated(msg)

                if key == 'notify_alarm':
                    await self._handle_alarm_notification(msg)
            else:
                log.debug("Key %s is not in ALLOWED_KAFKA_KEYS", key)
        except peewee.PeeweeException:
            log.exception("Database error consuming message: ")
            raise
        except Exception:
            log.exception("Error consuming message: ")

    async def _handle_alarm_notification(self, content):
        log.debug("_handle_alarm_notification: %s", content)
        alarm_uuid = content['notify_details']['alarm_uuid']
        metric_name = content['notify_details']['metric_name']
        operation = content['notify_details']['operation']
        threshold = content['notify_details']['threshold_value']
        vdu_name = content['notify_details']['vdu_name']
        vnf_member_index = content['notify_details']['vnf_member_index']
        nsr_id = content['notify_details']['ns_id']
        log.info(
            "Received alarm notification for alarm %s, \
            metric %s, \
            operation %s, \
            threshold %s, \
            vdu_name %s, \
            vnf_member_index %s, \
            ns_id %s ",
            alarm_uuid, metric_name, operation, threshold, vdu_name, vnf_member_index, nsr_id)
        try:
            alarm = self.service.get_alarm(alarm_uuid)
            await self.service.scale(alarm)
        except ScalingAlarm.DoesNotExist:
            log.info("There is no action configured for alarm %s.", alarm_uuid)

    async def _handle_instantiated(self, content):
        log.debug("_handle_instantiated: %s", content)
        nslcmop_id = content['nslcmop_id']
        nslcmop = self.service.get_nslcmop(nslcmop_id)
        if nslcmop['operationState'] == 'COMPLETED' or nslcmop['operationState'] == 'PARTIALLY_COMPLETED':
            nsr_id = nslcmop['nsInstanceId']
            log.info("Configuring scaling groups for network service with nsr_id: %s", nsr_id)
            await self.service.configure_scaling_groups(nsr_id)
        else:
            log.info(
                "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                nslcmop['operationState'])

    async def _handle_scaled(self, content):
        log.debug("_handle_scaled: %s", content)
        nslcmop_id = content['nslcmop_id']
        nslcmop = self.service.get_nslcmop(nslcmop_id)
        if nslcmop['operationState'] == 'COMPLETED' or nslcmop['operationState'] == 'PARTIALLY_COMPLETED':
            nsr_id = nslcmop['nsInstanceId']
            log.info("Configuring scaling groups for network service with nsr_id: %s", nsr_id)
            await self.service.configure_scaling_groups(nsr_id)
            log.info("Checking for orphaned alarms to be deleted for network service with nsr_id: %s", nsr_id)
            await self.service.delete_orphaned_alarms(nsr_id)
        else:
            log.info(
                "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                nslcmop['operationState'])

    async def _handle_terminated(self, content):
        log.debug("_handle_deleted: %s", content)
        nsr_id = content['nsr_id']
        if content['operationState'] == 'COMPLETED' or content['operationState'] == 'PARTIALLY_COMPLETED':
            log.info("Deleting scaling groups and alarms for network service with nsr_id: %s", nsr_id)
            await self.service.delete_scaling_groups(nsr_id)
        else:
            log.info(
                "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                content['operationState'])
