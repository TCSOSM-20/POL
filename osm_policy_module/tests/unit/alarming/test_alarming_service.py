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
from unittest import TestCase, mock

from osm_policy_module.alarming.service import AlarmingService
from osm_policy_module.common.common_db_client import CommonDbClient
from osm_policy_module.common.lcm_client import LcmClient
from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import VnfAlarmRepository


@mock.patch.object(LcmClient, "__init__", lambda *args, **kwargs: None)
@mock.patch.object(MonClient, "__init__", lambda *args, **kwargs: None)
@mock.patch.object(CommonDbClient, "__init__", lambda *args, **kwargs: None)
class TestAlarmingService(TestCase):

    def setUp(self):
        self.config = Config()
        self.loop = asyncio.new_event_loop()

    @mock.patch.object(VnfAlarmRepository, 'get')
    @mock.patch('requests.post')
    @mock.patch('osm_policy_module.core.database.db')
    def test_handle_alarm(self, database, requests_post, get_alarm):
        mock_alarm = self._build_mock_alarm('test_id')
        get_alarm.return_value = mock_alarm

        service = AlarmingService(self.config)
        self.loop.run_until_complete(service.handle_alarm('test_id', 'alarm', {}))
        requests_post.assert_called_once_with(json='{}', url='http://alarm-url/')

        requests_post.reset_mock()
        self.loop.run_until_complete(service.handle_alarm('test_id', 'ok', {}))
        requests_post.assert_called_once_with(json='{}', url='http://ok-url/')

        requests_post.reset_mock()
        self.loop.run_until_complete(service.handle_alarm('test_id', 'insufficient-data', {}))
        requests_post.assert_called_once_with(json='{}', url='http://insufficient-data-url/')

    @mock.patch.object(VnfAlarmRepository, 'get')
    @mock.patch('requests.post')
    @mock.patch('osm_policy_module.core.database.db')
    def test_handle_alarm_unknown_status(self, database, requests_post, get_alarm):
        mock_alarm = self._build_mock_alarm('test_id')
        get_alarm.return_value = mock_alarm

        service = AlarmingService(self.config)
        self.loop.run_until_complete(service.handle_alarm('test_id', 'unknown', {}))
        requests_post.assert_not_called()

    def _build_mock_alarm(self,
                          alarm_id='test_id',
                          alarm_url='http://alarm-url/',
                          insufficient_data_url='http://insufficient-data-url/',
                          ok_url='http://ok-url/'):
        mock_alarm = mock.Mock()
        mock_alarm.alarm_id = alarm_id
        insufficient_data_action = mock.Mock()
        insufficient_data_action.type = 'insufficient-data'
        insufficient_data_action.url = insufficient_data_url
        alarm_action = mock.Mock()
        alarm_action.type = 'alarm'
        alarm_action.url = alarm_url
        ok_action = mock.Mock()
        ok_action.type = 'ok'
        ok_action.url = ok_url
        mock_alarm.actions = [insufficient_data_action, alarm_action, ok_action]
        return mock_alarm
