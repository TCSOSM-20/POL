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
import json
import logging
import random
from json import JSONDecodeError

import yaml
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from osm_policy_module.core.config import Config

log = logging.getLogger(__name__)


class MonClient:
    def __init__(self, config: Config, loop=None):
        self.kafka_server = '{}:{}'.format(config.get('message', 'host'),
                                           config.get('message', 'port'))
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop

    async def create_alarm(self, metric_name: str, ns_id: str, vdu_name: str, vnf_member_index: str, threshold: int,
                           statistic: str, operation: str):
        cor_id = random.randint(1, 10e7)
        msg = self._build_create_alarm_payload(cor_id,
                                               metric_name,
                                               ns_id,
                                               vdu_name,
                                               vnf_member_index,
                                               threshold,
                                               statistic,
                                               operation)
        log.debug("Sending create_alarm_request %s", msg)
        producer = AIOKafkaProducer(loop=self.loop,
                                    bootstrap_servers=self.kafka_server,
                                    key_serializer=str.encode,
                                    value_serializer=str.encode)
        await producer.start()
        try:
            await producer.send_and_wait("alarm_request", key="create_alarm_request", value=json.dumps(msg))
        finally:
            await producer.stop()
        log.debug("Waiting for create_alarm_response...")
        consumer = AIOKafkaConsumer(
            "alarm_response_" + str(cor_id),
            loop=self.loop,
            bootstrap_servers=self.kafka_server,
            key_deserializer=bytes.decode,
            value_deserializer=bytes.decode,
            auto_offset_reset='earliest')
        await consumer.start()
        alarm_uuid = None
        try:
            async for message in consumer:
                try:
                    content = json.loads(message.value)
                except JSONDecodeError:
                    content = yaml.safe_load(message.value)
                log.debug("Received create_alarm_response %s", content)
                if content['alarm_create_response']['correlation_id'] == cor_id:
                    if not content['alarm_create_response']['status']:
                        raise ValueError("Error creating alarm in MON")
                    alarm_uuid = content['alarm_create_response']['alarm_uuid']
                    break
        finally:
            await consumer.stop()
        if not alarm_uuid:
            raise ValueError('No alarm deletion response from MON. Is MON up?')
        return alarm_uuid

    async def delete_alarm(self, ns_id: str, vnf_member_index: str, vdu_name: str, alarm_uuid: str):
        cor_id = random.randint(1, 10e7)
        msg = self._build_delete_alarm_payload(cor_id, ns_id, vdu_name, vnf_member_index, alarm_uuid)
        log.debug("Sending delete_alarm_request %s", msg)
        producer = AIOKafkaProducer(loop=self.loop,
                                    bootstrap_servers=self.kafka_server,
                                    key_serializer=str.encode,
                                    value_serializer=str.encode)
        await producer.start()
        try:
            await producer.send_and_wait("alarm_request", key="delete_alarm_request", value=json.dumps(msg))
        finally:
            await producer.stop()
        log.debug("Waiting for delete_alarm_response...")
        consumer = AIOKafkaConsumer(
            "alarm_response_" + str(cor_id),
            loop=self.loop,
            bootstrap_servers=self.kafka_server,
            key_deserializer=bytes.decode,
            value_deserializer=bytes.decode,
            auto_offset_reset='earliest')
        await consumer.start()
        alarm_uuid = None
        try:
            async for message in consumer:
                try:
                    content = json.loads(message.value)
                except JSONDecodeError:
                    content = yaml.safe_load(message.value)
                if content['alarm_delete_response']['correlation_id'] == cor_id:
                    log.debug("Received delete_alarm_response %s", content)
                    if not content['alarm_delete_response']['status']:
                        raise ValueError("Error deleting alarm in MON. Response status is False.")
                    alarm_uuid = content['alarm_delete_response']['alarm_uuid']
                    break
        finally:
            await consumer.stop()
        if not alarm_uuid:
            raise ValueError('No alarm deletion response from MON. Is MON up?')
        return alarm_uuid

    def _build_create_alarm_payload(self, cor_id: int,
                                    metric_name: str,
                                    ns_id: str,
                                    vdu_name: str,
                                    vnf_member_index: str,
                                    threshold: int,
                                    statistic: str,
                                    operation: str):

        alarm_create_request = {
            'correlation_id': cor_id,
            'alarm_name': 'osm_alarm_{}_{}_{}_{}'.format(ns_id, vnf_member_index, vdu_name, metric_name),
            'metric_name': metric_name,
            'ns_id': ns_id,
            'vdu_name': vdu_name,
            'vnf_member_index': vnf_member_index,
            'operation': operation,
            'severity': 'critical',
            'threshold_value': threshold,
            'statistic': statistic
        }
        msg = {
            'alarm_create_request': alarm_create_request,
        }
        return msg

    def _build_delete_alarm_payload(self, cor_id: int, ns_id: str, vdu_name: str,
                                    vnf_member_index: str, alarm_uuid: str):
        alarm_delete_request = {
            'correlation_id': cor_id,
            'alarm_uuid': alarm_uuid,
            'ns_id': ns_id,
            'vdu_name': vdu_name,
            'vnf_member_index': vnf_member_index
        }
        msg = {
            'alarm_delete_request': alarm_delete_request,
        }
        return msg
