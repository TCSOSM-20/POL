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
import unittest
from unittest import mock

from osm_policy_module.alarming.service import AlarmingService
from osm_policy_module.autoscaling.service import AutoscalingService
from osm_policy_module.core.agent import PolicyModuleAgent
from osm_policy_module.core.config import Config


class PolicyAgentTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()

    @mock.patch('osm_policy_module.alarming.service.CommonDbClient')
    @mock.patch('osm_policy_module.alarming.service.MonClient')
    @mock.patch('osm_policy_module.alarming.service.LcmClient')
    @mock.patch('osm_policy_module.autoscaling.service.CommonDbClient')
    @mock.patch('osm_policy_module.autoscaling.service.MonClient')
    @mock.patch('osm_policy_module.autoscaling.service.LcmClient')
    @mock.patch.object(AutoscalingService, 'configure_scaling_groups')
    @mock.patch.object(AlarmingService, 'configure_vnf_alarms')
    @mock.patch.object(AutoscalingService, 'delete_orphaned_alarms')
    def test_handle_instantiated(self,
                                 delete_orphaned_alarms,
                                 configure_vnf_alarms,
                                 configure_scaling_groups,
                                 autoscaling_lcm_client,
                                 autoscaling_mon_client,
                                 autoscaling_db_client,
                                 alarming_lcm_client,
                                 alarming_mon_client,
                                 alarming_db_client):
        async def mock_configure_scaling_groups(nsr_id):
            pass

        async def mock_configure_vnf_alarms(nsr_id):
            pass

        async def mock_delete_orphaned_alarms(nsr_id):
            pass

        config = Config()
        agent = PolicyModuleAgent(config, self.loop)
        assert autoscaling_lcm_client.called
        assert autoscaling_mon_client.called
        assert autoscaling_db_client.called
        assert alarming_lcm_client.called
        assert alarming_mon_client.called
        assert alarming_db_client.called
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
        configure_vnf_alarms.side_effect = mock_configure_vnf_alarms
        delete_orphaned_alarms.side_effect = mock_delete_orphaned_alarms

        autoscaling_db_client.return_value.get_nslcmop.return_value = nslcmop_completed
        self.loop.run_until_complete(agent._handle_instantiated(content))
        configure_scaling_groups.assert_called_with('test_nsr_id')
        configure_scaling_groups.reset_mock()

        autoscaling_db_client.return_value.get_nslcmop.return_value = nslcmop_failed
        self.loop.run_until_complete(agent._handle_instantiated(content))
        configure_scaling_groups.assert_not_called()

    @mock.patch('osm_policy_module.autoscaling.service.CommonDbClient')
    @mock.patch('osm_policy_module.autoscaling.service.MonClient')
    @mock.patch('osm_policy_module.autoscaling.service.LcmClient')
    @mock.patch('osm_policy_module.alarming.service.CommonDbClient')
    @mock.patch('osm_policy_module.alarming.service.MonClient')
    @mock.patch('osm_policy_module.alarming.service.LcmClient')
    @mock.patch.object(AutoscalingService, 'handle_alarm')
    @mock.patch.object(AlarmingService, 'handle_alarm')
    def test_handle_alarm_notification(self,
                                       alarming_handle_alarm,
                                       autoscaling_handle_alarm,
                                       autoscaling_lcm_client,
                                       autoscaling_mon_client,
                                       autoscaling_db_client,
                                       alarming_lcm_client,
                                       alarming_mon_client,
                                       alarming_db_client):
        async def mock_handle_alarm(alarm_uuid, status, payload=None):
            pass

        config = Config()
        agent = PolicyModuleAgent(config, self.loop)
        assert autoscaling_lcm_client.called
        assert autoscaling_mon_client.called
        assert autoscaling_db_client.called
        assert alarming_lcm_client.called
        assert alarming_mon_client.called
        assert alarming_db_client.called
        content = {
            'notify_details': {
                'alarm_uuid': 'test_alarm_uuid',
                'metric_name': 'test_metric_name',
                'operation': 'test_operation',
                'threshold_value': 'test_threshold_value',
                'vdu_name': 'test_vdu_name',
                'vnf_member_index': 'test_vnf_member_index',
                'ns_id': 'test_nsr_id',
                'status': 'alarm'
            }
        }
        autoscaling_handle_alarm.side_effect = mock_handle_alarm
        alarming_handle_alarm.side_effect = mock_handle_alarm

        self.loop.run_until_complete(agent._handle_alarm_notification(content))
        autoscaling_handle_alarm.assert_called_with('test_alarm_uuid', 'alarm')
        alarming_handle_alarm.assert_called_with('test_alarm_uuid', 'alarm', content)


if __name__ == '__main__':
    unittest.main()
