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
from unittest import TestCase, mock

from osm_policy_module.autoscaling.service import AutoscalingService
from osm_policy_module.common.common_db_client import CommonDbClient
from osm_policy_module.common.lcm_client import LcmClient
from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import ScalingAlarmRepository


@mock.patch.object(LcmClient, "__init__", lambda *args, **kwargs: None)
@mock.patch.object(MonClient, "__init__", lambda *args, **kwargs: None)
@mock.patch.object(CommonDbClient, "__init__", lambda *args, **kwargs: None)
class TestAutoscalingService(TestCase):

    def setUp(self):
        self.config = Config()
        self.loop = asyncio.new_event_loop()

    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch('osm_policy_module.core.database.db')
    def test_update_alarm_status(self, database, get_alarm):
        mock_alarm = mock.Mock()
        mock_alarm.last_status = 'insufficient_data'
        get_alarm.return_value = mock_alarm

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.update_alarm_status('test_uuid', 'alarm'))
        self.assertEqual(mock_alarm.last_status, 'alarm')
        mock_alarm.save.assert_called_with()

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.update_alarm_status('test_uuid', 'ok'))
        self.assertEqual(mock_alarm.last_status, 'ok')
        mock_alarm.save.assert_called_with()

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.update_alarm_status('test_uuid', 'insufficient_data'))
        self.assertEqual(mock_alarm.last_status, 'insufficient_data')
        mock_alarm.save.assert_called_with()

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_not_enabled(self, database, get_alarm, list_alarms):
        mock_alarm = mock.Mock()
        mock_alarm.scaling_criteria.scaling_policy.enabled = False
        get_alarm.return_value = mock_alarm

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        list_alarms.assert_not_called()

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_in_and_equal(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale in with AND operation, both alarms triggered
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_in', last_status='alarm', enabled=True, scale_in_op='AND')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_in', last_status='alarm', enabled=True, scale_in_op='AND')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_called_with('test_nsr_id', 'test_group', '1', 'scale_in')

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_in_and_diff(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale in with AND operation, only one alarm triggered.
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_in', last_status='alarm', enabled=True, scale_in_op='AND')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_in', last_status='ok', enabled=True, scale_in_op='OR')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_not_called()

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_in_or_equal(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale in with OR operation, both alarms triggered
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_in', last_status='alarm', enabled=True, scale_in_op='OR')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_in', last_status='alarm', enabled=True, scale_in_op='OR')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_called_with('test_nsr_id', 'test_group', '1', 'scale_in')

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_in_or_diff(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale in with OR operation, only one alarm triggered
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_in', last_status='alarm', enabled=True, scale_in_op='OR')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_in', last_status='ok', enabled=True, scale_in_op='OR')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_called_with('test_nsr_id', 'test_group', '1', 'scale_in')

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_out_and_equal(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale out with AND operation, both alarms triggered
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_out', last_status='alarm', enabled=True, scale_out_op='AND')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_out', last_status='alarm', enabled=True, scale_out_op='AND')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_called_with('test_nsr_id', 'test_group', '1', 'scale_out')

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_out_and_diff(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale out with AND operation, only one alarm triggered.
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_out', last_status='alarm', enabled=True, scale_out_op='AND')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_out', last_status='ok', enabled=True, scale_out_op='OR')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_not_called()

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_out_or_equal(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale out with OR operation, both alarms triggered
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_out', last_status='alarm', enabled=True, scale_out_op='OR')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_out', last_status='alarm', enabled=True, scale_out_op='OR')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_called_with('test_nsr_id', 'test_group', '1', 'scale_out')

    @mock.patch.object(ScalingAlarmRepository, 'list')
    @mock.patch.object(ScalingAlarmRepository, 'get')
    @mock.patch.object(LcmClient, 'scale')
    @mock.patch('osm_policy_module.core.database.db')
    def test_evaluate_policy_scale_out_or_diff(self, database, scale, get_alarm, list_alarms):
        """
        Tests scale out with OR operation, only one alarm triggered
        """
        future = asyncio.Future(loop=self.loop)
        future.set_result('mock')
        scale.return_value = future

        mock_alarm = self._build_mock_alarm(action='scale_out', last_status='alarm', enabled=True, scale_out_op='OR')
        get_alarm.return_value = mock_alarm

        mock_alarm_2 = self._build_mock_alarm(action='scale_out', last_status='ok', enabled=True, scale_out_op='OR')

        list_alarms.return_value = [mock_alarm, mock_alarm_2]

        service = AutoscalingService(self.config)
        self.loop.run_until_complete(service.evaluate_policy('test_uuid'))
        scale.assert_called_with('test_nsr_id', 'test_group', '1', 'scale_out')

    def _build_mock_alarm(self,
                          action='scale_in',
                          last_status='alarm',
                          last_scale=datetime.datetime.min,
                          cooldown_time=10,
                          enabled=True,
                          scale_in_op='AND',
                          scale_out_op='AND'):
        mock_alarm = mock.Mock()
        mock_alarm.action = action
        mock_alarm.last_status = last_status
        mock_alarm.vnf_member_index = '1'
        mock_alarm.scaling_criteria.scaling_policy.last_scale = last_scale
        mock_alarm.scaling_criteria.scaling_policy.cooldown_time = cooldown_time
        mock_alarm.scaling_criteria.scaling_policy.enabled = enabled
        mock_alarm.scaling_criteria.scaling_policy.scale_in_operation = scale_in_op
        mock_alarm.scaling_criteria.scaling_policy.scale_out_operation = scale_out_op
        mock_alarm.scaling_criteria.scaling_policy.scaling_group.nsr_id = 'test_nsr_id'
        mock_alarm.scaling_criteria.scaling_policy.scaling_group.name = 'test_group'
        return mock_alarm
