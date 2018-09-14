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
import os
import sys
import unittest

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

from osm_policy_module.core.agent import PolicyModuleAgent
from osm_policy_module.core.config import Config

log = logging.getLogger()
log.level = logging.INFO
stream_handler = logging.StreamHandler(sys.stdout)
log.addHandler(stream_handler)


class KafkaMessagesTest(unittest.TestCase):
    def setUp(self):
        try:
            cfg = Config.instance()
            kafka_server = '{}:{}'.format(cfg.OSMPOL_MESSAGE_HOST,
                                          cfg.OSMPOL_MESSAGE_PORT)
            self.producer = KafkaProducer(bootstrap_servers=kafka_server,
                                          key_serializer=str.encode,
                                          value_serializer=str.encode)
            self.consumer = KafkaConsumer(bootstrap_servers=kafka_server,
                                          key_deserializer=bytes.decode,
                                          value_deserializer=bytes.decode,
                                          auto_offset_reset='earliest',
                                          consumer_timeout_ms=5000)
            self.consumer.subscribe(['ns'])
        except KafkaError:
            self.skipTest('Kafka server not present.')

    def tearDown(self):
        self.producer.close()
        self.consumer.close()

    def test_send_instantiated_msg(self):
        with open(
                os.path.join(os.path.dirname(__file__), '../examples/instantiated.json')) as file:
            payload = json.load(file)
            self.producer.send('ns', json.dumps(payload), key="instantiated")
            self.producer.flush()

        for message in self.consumer:
            if message.key == 'instantiated':
                self.assertIsNotNone(message.value)
                return
        self.fail("No message received in consumer")


if __name__ == '__main__':
    unittest.main()
