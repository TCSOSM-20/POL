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
import os
import sys
import unittest

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from kafka.errors import KafkaError

from osm_policy_module.core.config import Config

log = logging.getLogger()
log.level = logging.INFO
stream_handler = logging.StreamHandler(sys.stdout)
log.addHandler(stream_handler)


class KafkaMessagesTest(unittest.TestCase):
    def setUp(self):
        super()
        cfg = Config.instance()
        self.kafka_server = '{}:{}'.format(cfg.OSMPOL_MESSAGE_HOST,
                                           cfg.OSMPOL_MESSAGE_PORT)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    def tearDown(self):
        super()

    def test_send_instantiated_msg(self):
        async def test_send_instantiated_msg():
            producer = AIOKafkaProducer(loop=self.loop,
                                        bootstrap_servers=self.kafka_server,
                                        key_serializer=str.encode,
                                        value_serializer=str.encode)
            await producer.start()
            consumer = AIOKafkaConsumer(
                "ns",
                loop=self.loop,
                bootstrap_servers=self.kafka_server,
                consumer_timeout_ms=10000,
                auto_offset_reset='earliest',
                value_deserializer=bytes.decode,
                key_deserializer=bytes.decode)
            await consumer.start()
            try:
                with open(
                        os.path.join(os.path.dirname(__file__), '../examples/instantiated.json')) as file:
                    payload = json.load(file)
                    await producer.send_and_wait("ns", key="instantiated", value=json.dumps(payload))
            finally:
                await producer.stop()
            try:
                async for message in consumer:
                    if message.key == 'instantiated':
                        self.assertIsNotNone(message.value)
                        return
            finally:
                await consumer.stop()

        try:
            self.loop.run_until_complete(test_send_instantiated_msg())
        except KafkaError:
            self.skipTest('Kafka server not present.')


if __name__ == '__main__':
    unittest.main()
