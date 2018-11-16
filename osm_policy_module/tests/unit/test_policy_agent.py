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
import unittest
from unittest import mock
from unittest.mock import Mock

from osm_policy_module.core.agent import PolicyModuleAgent
from osm_policy_module.core.database import DatabaseManager


class PolicyAgentTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)

    @mock.patch('osm_policy_module.core.agent.CommonDbClient')
    @mock.patch('osm_policy_module.core.agent.MonClient')
    @mock.patch('osm_policy_module.core.agent.LcmClient')
    @mock.patch.object(PolicyModuleAgent, '_configure_scaling_groups')
    def test_handle_instantiated_or_scaled(self, configure_scaling_groups, lcm_client, mon_client, db_client):
        async def mock_configure_scaling_groups(nsr_id):
            pass

        agent = PolicyModuleAgent(self.loop)
        assert lcm_client.called
        assert mon_client.called
        assert db_client.called
        content = {
            'nslcmop_id': 'test_id',
        }
        nslcmop_completed = {
            'operationState': 'COMPLETED',
            'nsInstanceId': 'test_nsr_id'
        }
        nslcmop_failed = {
            'operationState': 'FAILED',
            'nsInstanceId': 'test_nsr_id'
        }
        configure_scaling_groups.side_effect = mock_configure_scaling_groups

        db_client.return_value.get_nslcmop.return_value = nslcmop_completed
        self.loop.run_until_complete(agent._handle_instantiated_or_scaled(content))
        configure_scaling_groups.assert_called_with('test_nsr_id')
        configure_scaling_groups.reset_mock()

        db_client.return_value.get_nslcmop.return_value = nslcmop_failed
        self.loop.run_until_complete(agent._handle_instantiated_or_scaled(content))
        configure_scaling_groups.assert_not_called()

    @mock.patch('osm_policy_module.core.agent.CommonDbClient')
    @mock.patch('osm_policy_module.core.agent.MonClient')
    @mock.patch('osm_policy_module.core.agent.LcmClient')
    @mock.patch.object(DatabaseManager, 'get_alarm')
    def test_handle_alarm_notification(self, get_alarm, lcm_client, mon_client, db_client):
        async def mock_scale(nsr_id, scaling_group_name, vnf_member_index, action):
            pass

        agent = PolicyModuleAgent(self.loop)
        assert lcm_client.called
        assert mon_client.called
        assert db_client.called
        content = {
            'notify_details': {
                'alarm_uuid': 'test_alarm_uuid',
                'metric_name': 'test_metric_name',
                'operation': 'test_operation',
                'threshold_value': 'test_threshold_value',
                'vdu_name': 'test_vdu_name',
                'vnf_member_index': 'test_vnf_member_index',
                'ns_id': 'test_nsr_id'
            }
        }
        mock_alarm = Mock()
        mock_alarm.vnf_member_index = 1
        mock_alarm.action = 'scale_out'
        mock_scaling_criteria = Mock()
        mock_scaling_policy = Mock()
        mock_scaling_group = Mock()
        mock_scaling_group.nsr_id = 'test_nsr_id'
        mock_scaling_group.name = 'test_name'
        mock_scaling_policy.cooldown_time = 60
        mock_scaling_policy.scaling_group = mock_scaling_group
        mock_scaling_criteria.scaling_policy = mock_scaling_policy
        mock_alarm.scaling_criteria = mock_scaling_criteria
        get_alarm.return_value = mock_alarm
        lcm_client.return_value.scale.side_effect = mock_scale

        mock_scaling_policy.last_scale = datetime.datetime.now() - datetime.timedelta(minutes=90)

        self.loop.run_until_complete(agent._handle_alarm_notification(content))
        lcm_client.return_value.scale.assert_called_with('test_nsr_id', 'test_name', 1, 'scale_out')
        lcm_client.return_value.scale.reset_mock()

        mock_scaling_policy.last_scale = datetime.datetime.now()
        self.loop.run_until_complete(agent._handle_alarm_notification(content))
        lcm_client.return_value.scale.assert_not_called()


if __name__ == '__main__':
    unittest.main()
