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

import requests

from osm_policy_module.common.common_db_client import CommonDbClient
from osm_policy_module.common.lcm_client import LcmClient
from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core import database
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import VnfAlarm, VnfAlarmRepository, AlarmActionRepository
from osm_policy_module.core.exceptions import VdurNotFound

log = logging.getLogger(__name__)


class AlarmingService:

    def __init__(self, config: Config, loop=None):
        self.conf = config
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.db_client = CommonDbClient(config)
        self.mon_client = MonClient(config, loop=self.loop)
        self.lcm_client = LcmClient(config, loop=self.loop)

    async def configure_vnf_alarms(self, nsr_id: str):
        log.info("Configuring vnf alarms for network service %s", nsr_id)
        alarms_created = []
        database.db.connect(reuse_if_open=True)
        with database.db.atomic() as tx:
            try:
                vnfrs = self.db_client.get_vnfrs(nsr_id)
                for vnfr in vnfrs:
                    log.debug("Processing vnfr: %s", vnfr)
                    vnfd = self.db_client.get_vnfd(vnfr['vnfd-id'])
                    for vdur in vnfr['vdur']:
                        vdu = next(
                            filter(
                                lambda vdu: vdu['id'] == vdur['vdu-id-ref'],
                                vnfd['vdu']
                            )
                        )
                        if 'alarm' in vdu:
                            alarm_descriptors = vdu['alarm']
                            for alarm_descriptor in alarm_descriptors:
                                try:
                                    VnfAlarmRepository.get(
                                        VnfAlarm.alarm_id == alarm_descriptor['alarm-id'],
                                        VnfAlarm.vnf_member_index == vnfr['member-vnf-index-ref'],
                                        VnfAlarm.vdu_name == vdur['name'],
                                        VnfAlarm.nsr_id == nsr_id
                                    )
                                    log.debug("vdu %s already has an alarm configured with same id %s", vdur['name'],
                                              alarm_descriptor['alarm-id'])
                                    continue
                                except VnfAlarm.DoesNotExist:
                                    pass
                                vnf_monitoring_param = next(
                                    filter(
                                        lambda param: param['id'] == alarm_descriptor['vnf-monitoring-param-ref'],
                                        vnfd['monitoring-param'])
                                )
                                alarm_uuid = await self.mon_client.create_alarm(
                                    metric_name=alarm_descriptor['vnf-monitoring-param-ref'],
                                    ns_id=nsr_id,
                                    vdu_name=vdur['name'],
                                    vnf_member_index=vnfr['member-vnf-index-ref'],
                                    threshold=alarm_descriptor['value'],
                                    operation=alarm_descriptor['operation'],
                                    statistic=vnf_monitoring_param['aggregation-type']
                                )
                                alarm = VnfAlarmRepository.create(
                                    alarm_id=alarm_descriptor['alarm-id'],
                                    alarm_uuid=alarm_uuid,
                                    nsr_id=nsr_id,
                                    vnf_member_index=int(vnfr['member-vnf-index-ref']),
                                    vdu_name=vdur['name']
                                )
                                for action_type in ['ok', 'insufficient-data', 'alarm']:
                                    if 'actions' in alarm_descriptor and action_type in alarm_descriptor['actions']:
                                        for url in alarm_descriptor['actions'][action_type]:
                                            AlarmActionRepository.create(
                                                type=action_type,
                                                url=url['url'],
                                                alarm=alarm
                                            )
                                alarms_created.append(alarm)

            except Exception as e:
                log.exception("Error configuring VNF alarms:")
                tx.rollback()
                if len(alarms_created) > 0:
                    log.debug("Cleaning alarm resources in MON")
                    for alarm in alarms_created:
                        await self.mon_client.delete_alarm(alarm.nsr_id,
                                                           alarm.vnf_member_index,
                                                           alarm.vdu_name,
                                                           alarm.alarm_uuid)
                raise e
        database.db.close()

    async def delete_orphaned_alarms(self, nsr_id):
        log.info("Deleting orphaned vnf alarms for network service %s", nsr_id)
        database.db.connect()
        with database.db.atomic() as tx:
            try:
                for alarm in VnfAlarmRepository.list(VnfAlarm.nsr_id == nsr_id):
                    try:
                        self.db_client.get_vdur(nsr_id, alarm.vnf_member_index, alarm.vdu_name)
                    except VdurNotFound:
                        log.debug("Deleting orphaned alarm %s", alarm.alarm_uuid)
                        try:
                            await self.mon_client.delete_alarm(
                                alarm.nsr_id,
                                alarm.vnf_member_index,
                                alarm.vdu_name,
                                alarm.alarm_uuid)
                        except ValueError:
                            log.exception("Error deleting alarm in MON %s", alarm.alarm_uuid)
                        alarm.delete_instance()

            except Exception as e:
                log.exception("Error deleting orphaned alarms:")
                tx.rollback()
                raise e
        database.db.close()

    async def delete_vnf_alarms(self, nsr_id):
        log.info("Deleting vnf alarms for network service %s", nsr_id)
        database.db.connect()
        with database.db.atomic() as tx:
            try:
                for alarm in VnfAlarmRepository.list(VnfAlarm.nsr_id == nsr_id):
                    log.debug("Deleting vnf alarm %s", alarm.alarm_uuid)
                    try:
                        await self.mon_client.delete_alarm(
                            alarm.nsr_id,
                            alarm.vnf_member_index,
                            alarm.vdu_name,
                            alarm.alarm_uuid)
                    except ValueError:
                        log.exception("Error deleting alarm in MON %s", alarm.alarm_uuid)
                    alarm.delete_instance()

            except Exception as e:
                log.exception("Error deleting orphaned alarms:")
                tx.rollback()
                raise e
        database.db.close()

    async def handle_alarm(self, alarm_uuid: str, status: str, payload: dict):
        database.db.connect()
        try:
            with database.db.atomic():
                alarm = VnfAlarmRepository.get(VnfAlarm.alarm_uuid == alarm_uuid)
                log.debug("Handling vnf alarm %s with status %s", alarm.alarm_id, status)
                for action in alarm.actions:
                    if action.type == status:
                        log.info("Executing request to url %s for vnf alarm %s with status %s", action.url,
                                 alarm.alarm_id, status)
                        requests.post(url=action.url, json=json.dumps(payload))
        except VnfAlarm.DoesNotExist:
            log.debug("There is no alarming action configured for alarm %s.", alarm_uuid)
        finally:
            database.db.close()
