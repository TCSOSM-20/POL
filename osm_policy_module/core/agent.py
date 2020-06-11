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
from pathlib import Path
import os

import peewee

from osm_policy_module.alarming.service import AlarmingService
from osm_policy_module.autoscaling.service import AutoscalingService
from osm_policy_module.common.common_db_client import CommonDbClient
from osm_policy_module.common.message_bus_client import MessageBusClient
from osm_policy_module.core.config import Config

log = logging.getLogger(__name__)

ALLOWED_KAFKA_KEYS = ['instantiated', 'scaled', 'terminated', 'notify_alarm']


class PolicyModuleAgent:
    def __init__(self, config: Config, loop=None):
        self.conf = config
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.msg_bus = MessageBusClient(config)
        self.db_client = CommonDbClient(config)
        self.autoscaling_service = AutoscalingService(config, loop)
        self.alarming_service = AlarmingService(config, loop)

    def run(self):
        self.loop.run_until_complete(self.start())

    async def start(self):
        Path('/tmp/osm_pol_agent_health_flag').touch()
        topics = [
            "ns",
            "alarm_response"
        ]
        await self.msg_bus.aioread(topics, self._process_msg)
        log.critical("Exiting...")
        if os.path.exists('/tmp/osm_pol_agent_health_flag'):
            os.remove('/tmp/osm_pol_agent_health_flag')

    async def _process_msg(self, topic, key, msg):
        Path('/tmp/osm_pol_agent_health_flag').touch()
        log.debug("_process_msg topic=%s key=%s msg=%s", topic, key, msg)
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
        status = content['notify_details']['status']
        await self.autoscaling_service.handle_alarm(alarm_uuid, status)
        await self.alarming_service.handle_alarm(alarm_uuid, status, content)

    async def _handle_instantiated(self, content):
        log.debug("_handle_instantiated: %s", content)
        nslcmop_id = content['nslcmop_id']
        nslcmop = self.db_client.get_nslcmop(nslcmop_id)
        if nslcmop['operationState'] == 'COMPLETED' or nslcmop['operationState'] == 'PARTIALLY_COMPLETED':
            nsr_id = nslcmop['nsInstanceId']
            log.info("Configuring nsr_id: %s", nsr_id)
            await self.autoscaling_service.configure_scaling_groups(nsr_id)
            await self.alarming_service.configure_vnf_alarms(nsr_id)
        else:
            log.info(
                "Network_service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                nslcmop['operationState'])

    async def _handle_scaled(self, content):
        log.debug("_handle_scaled: %s", content)
        nslcmop_id = content['nslcmop_id']
        nslcmop = self.db_client.get_nslcmop(nslcmop_id)
        if nslcmop['operationState'] == 'COMPLETED' or nslcmop['operationState'] == 'PARTIALLY_COMPLETED':
            nsr_id = nslcmop['nsInstanceId']
            log.info("Configuring scaled service with nsr_id: %s", nsr_id)
            await self.autoscaling_service.configure_scaling_groups(nsr_id)
            await self.autoscaling_service.delete_orphaned_alarms(nsr_id)
            await self.alarming_service.configure_vnf_alarms(nsr_id)
        else:
            log.debug(
                "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                nslcmop['operationState'])

    async def _handle_terminated(self, content):
        log.debug("_handle_deleted: %s", content)
        nsr_id = content['nsr_id']
        if content['operationState'] == 'COMPLETED' or content['operationState'] == 'PARTIALLY_COMPLETED':
            log.info("Deleting scaling groups and alarms for network autoscaling_service with nsr_id: %s", nsr_id)
            await self.autoscaling_service.delete_scaling_groups(nsr_id)
            await self.alarming_service.delete_vnf_alarms(nsr_id)
        else:
            log.info(
                "Network service is not in COMPLETED or PARTIALLY_COMPLETED state. "
                "Current state is %s. Skipping...",
                content['operationState'])
