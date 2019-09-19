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
import json
import logging
from typing import List

from osm_policy_module.common.common_db_client import CommonDbClient
from osm_policy_module.common.lcm_client import LcmClient
from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core import database
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import ScalingGroup, ScalingAlarm, ScalingPolicy, ScalingCriteria, \
    ScalingAlarmRepository, ScalingGroupRepository, ScalingPolicyRepository, ScalingCriteriaRepository
from osm_policy_module.core.exceptions import VdurNotFound
from osm_policy_module.utils.vnfd import VnfdUtils

log = logging.getLogger(__name__)


class AutoscalingService:

    def __init__(self, config: Config, loop=None):
        self.conf = config
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.db_client = CommonDbClient(config)
        self.mon_client = MonClient(config, loop=self.loop)
        self.lcm_client = LcmClient(config, loop=self.loop)

    async def configure_scaling_groups(self, nsr_id: str):
        """
        Configures scaling groups for a network service. Creates records in DB. Creates alarms in MON.
        :param nsr_id: Network service record id
        :return:
        """
        log.info("Configuring scaling groups for network service with nsr_id: %s",
                 nsr_id)
        alarms_created = []
        database.db.connect()
        try:
            with database.db.atomic() as tx:
                try:
                    vnfrs = self.db_client.get_vnfrs(nsr_id)
                    for vnfr in vnfrs:
                        log.debug("Processing vnfr: %s", vnfr)
                        vnfd = self.db_client.get_vnfd(vnfr['vnfd-id'])
                        if 'scaling-group-descriptor' not in vnfd:
                            log.debug("No scaling group present in vnfd")
                            continue
                        scaling_groups = vnfd['scaling-group-descriptor']
                        vnf_monitoring_params = vnfd['monitoring-param']
                        for scaling_group in scaling_groups:
                            scaling_group_record = self._get_or_create_scaling_group(nsr_id,
                                                                                     vnfr['member-vnf-index-ref'],
                                                                                     scaling_group)
                            for scaling_policy in scaling_group['scaling-policy']:
                                if scaling_policy['scaling-type'] != 'automatic':
                                    continue
                                scaling_policy_record = self._get_or_create_scaling_policy(nsr_id,
                                                                                           scaling_policy,
                                                                                           scaling_group_record)

                                for scaling_criteria in scaling_policy['scaling-criteria']:
                                    scaling_criteria_record = self._get_or_create_scaling_criteria(
                                        nsr_id,
                                        scaling_criteria,
                                        scaling_policy_record
                                    )
                                    vnf_monitoring_param = next(
                                        filter(
                                            lambda param: param['id'] == scaling_criteria[
                                                'vnf-monitoring-param-ref'
                                            ],
                                            vnf_monitoring_params)
                                    )
                                    vdurs = self._get_monitored_vdurs(vnf_monitoring_param, vnfr['vdur'], vnfd)
                                    for vdur in vdurs:
                                        log.debug("Creating alarm for vdur %s ", vdur)
                                        try:
                                            ScalingAlarmRepository.get(ScalingAlarm.vdu_name == vdur['name'],
                                                                       ScalingCriteria.name == scaling_criteria['name'],
                                                                       ScalingPolicy.name == scaling_policy['name'],
                                                                       ScalingGroup.nsr_id == nsr_id,
                                                                       join_classes=[ScalingCriteria,
                                                                                     ScalingPolicy,
                                                                                     ScalingGroup])
                                            log.debug("vdu %s already has an alarm configured", vdur['name'])
                                            continue
                                        except ScalingAlarm.DoesNotExist:
                                            pass
                                        metric_name = self._get_metric_name(vnf_monitoring_param, vdur, vnfd)
                                        alarm_uuid = await self.mon_client.create_alarm(
                                            metric_name=metric_name,
                                            ns_id=nsr_id,
                                            vdu_name=vdur['name'],
                                            vnf_member_index=vnfr['member-vnf-index-ref'],
                                            threshold=scaling_criteria['scale-in-threshold'],
                                            operation=scaling_criteria['scale-in-relational-operation'],
                                            statistic=vnf_monitoring_param['aggregation-type']
                                        )
                                        alarm = ScalingAlarmRepository.create(
                                            alarm_uuid=alarm_uuid,
                                            action='scale_in',
                                            vnf_member_index=vnfr['member-vnf-index-ref'],
                                            vdu_name=vdur['name'],
                                            scaling_criteria=scaling_criteria_record
                                        )
                                        alarms_created.append(alarm)
                                        alarm_uuid = await self.mon_client.create_alarm(
                                            metric_name=metric_name,
                                            ns_id=nsr_id,
                                            vdu_name=vdur['name'],
                                            vnf_member_index=vnfr['member-vnf-index-ref'],
                                            threshold=scaling_criteria['scale-out-threshold'],
                                            operation=scaling_criteria['scale-out-relational-operation'],
                                            statistic=vnf_monitoring_param['aggregation-type']
                                        )
                                        alarm = ScalingAlarmRepository.create(
                                            alarm_uuid=alarm_uuid,
                                            action='scale_out',
                                            vnf_member_index=vnfr['member-vnf-index-ref'],
                                            vdu_name=vdur['name'],
                                            scaling_criteria=scaling_criteria_record
                                        )
                                        alarms_created.append(alarm)

                except Exception as e:
                    log.exception("Error configuring scaling groups:")
                    tx.rollback()
                    if len(alarms_created) > 0:
                        log.info("Cleaning alarm resources in MON")
                        for alarm in alarms_created:
                            await self.mon_client.delete_alarm(
                                alarm.scaling_criteria.scaling_policy.scaling_group.nsr_id,
                                alarm.vnf_member_index,
                                alarm.vdu_name,
                                alarm.alarm_uuid)
                    raise e
        finally:
            database.db.close()

    async def delete_scaling_groups(self, nsr_id: str):
        log.debug("Deleting scaling groups for network service %s", nsr_id)
        database.db.connect()
        try:
            with database.db.atomic() as tx:
                try:
                    for scaling_group in ScalingGroupRepository.list(ScalingGroup.nsr_id == nsr_id):
                        for scaling_policy in scaling_group.scaling_policies:
                            for scaling_criteria in scaling_policy.scaling_criterias:
                                for alarm in scaling_criteria.scaling_alarms:
                                    try:
                                        await self.mon_client.delete_alarm(
                                            alarm.scaling_criteria.scaling_policy.scaling_group.nsr_id,
                                            alarm.vnf_member_index,
                                            alarm.vdu_name,
                                            alarm.alarm_uuid)
                                    except ValueError:
                                        log.exception("Error deleting alarm in MON %s", alarm.alarm_uuid)
                                    alarm.delete_instance()
                                scaling_criteria.delete_instance()
                            scaling_policy.delete_instance()
                        scaling_group.delete_instance()

                except Exception as e:
                    log.exception("Error deleting scaling groups and alarms:")
                    tx.rollback()
                    raise e
        finally:
            database.db.close()

    async def delete_orphaned_alarms(self, nsr_id):
        log.info("Deleting orphaned scaling alarms for network service %s", nsr_id)
        database.db.connect()
        try:
            with database.db.atomic() as tx:
                try:
                    for scaling_group in ScalingGroupRepository.list(ScalingGroup.nsr_id == nsr_id):
                        for scaling_policy in scaling_group.scaling_policies:
                            for scaling_criteria in scaling_policy.scaling_criterias:
                                for alarm in scaling_criteria.scaling_alarms:
                                    try:
                                        self.db_client.get_vdur(nsr_id, alarm.vnf_member_index, alarm.vdu_name)
                                    except VdurNotFound:
                                        log.debug("Deleting orphaned scaling alarm %s", alarm.alarm_uuid)
                                        try:
                                            await self.mon_client.delete_alarm(
                                                alarm.scaling_criteria.scaling_policy.scaling_group.nsr_id,
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
        finally:
            database.db.close()

    async def handle_alarm(self, alarm_uuid: str, status: str):
        await self.update_alarm_status(alarm_uuid, status)
        await self.evaluate_policy(alarm_uuid)

    async def update_alarm_status(self, alarm_uuid: str, status: str):
        database.db.connect()
        try:
            with database.db.atomic():
                alarm = ScalingAlarmRepository.get(ScalingAlarm.alarm_uuid == alarm_uuid)
                alarm.last_status = status
                alarm.save()
        except ScalingAlarm.DoesNotExist:
            log.debug("There is no autoscaling action configured for alarm %s.", alarm_uuid)
        finally:
            database.db.close()

    async def evaluate_policy(self, alarm_uuid):
        database.db.connect()
        try:
            with database.db.atomic():
                alarm = ScalingAlarmRepository.get(ScalingAlarm.alarm_uuid == alarm_uuid)
                vnf_member_index = alarm.vnf_member_index
                action = alarm.action
                scaling_policy = alarm.scaling_criteria.scaling_policy
                if not scaling_policy.enabled:
                    return
                if action == 'scale_in':
                    operation = scaling_policy.scale_in_operation
                elif action == 'scale_out':
                    operation = scaling_policy.scale_out_operation
                else:
                    raise Exception('Unknown alarm action {}'.format(alarm.action))
                alarms = ScalingAlarmRepository.list(ScalingAlarm.scaling_criteria == alarm.scaling_criteria,
                                                     ScalingAlarm.action == alarm.action,
                                                     ScalingAlarm.vnf_member_index == vnf_member_index,
                                                     ScalingAlarm.vdu_name == alarm.vdu_name)
                statuses = []
                for alarm in alarms:
                    statuses.append(alarm.last_status)
                if (operation == 'AND' and set(statuses) == {'alarm'}) or (operation == 'OR' and 'alarm' in statuses):
                    delta = datetime.datetime.now() - scaling_policy.last_scale
                    if delta.total_seconds() > scaling_policy.cooldown_time:
                        log.info("Sending %s action message for ns: %s",
                                 alarm.action,
                                 scaling_policy.scaling_group.nsr_id)
                        await self.lcm_client.scale(scaling_policy.scaling_group.nsr_id,
                                                    scaling_policy.scaling_group.name,
                                                    vnf_member_index,
                                                    action)
                        scaling_policy.last_scale = datetime.datetime.now()
                        scaling_policy.save()

        except ScalingAlarm.DoesNotExist:
            log.debug("There is no autoscaling action configured for alarm %s.", alarm_uuid)
        finally:
            database.db.close()

    def _get_or_create_scaling_group(self, nsr_id: str, vnf_member_index: str, scaling_group: dict):
        try:
            scaling_group_record = ScalingGroupRepository.get(
                ScalingGroup.nsr_id == nsr_id,
                ScalingGroup.vnf_member_index == vnf_member_index,
                ScalingGroup.name == scaling_group['name']
            )
            log.debug("Found existing scaling group record in DB...")
        except ScalingGroup.DoesNotExist:
            log.debug("Creating scaling group record in DB...")
            scaling_group_record = ScalingGroupRepository.create(
                nsr_id=nsr_id,
                vnf_member_index=vnf_member_index,
                name=scaling_group['name'],
                content=json.dumps(scaling_group)
            )
            log.debug(
                "Created scaling group record in DB : nsr_id=%s, vnf_member_index=%s, name=%s",
                scaling_group_record.nsr_id,
                scaling_group_record.vnf_member_index,
                scaling_group_record.name)
        return scaling_group_record

    def _get_or_create_scaling_policy(self, nsr_id: str, scaling_policy: dict, scaling_group_record: ScalingGroup):
        try:
            scaling_policy_record = ScalingPolicyRepository.get(
                ScalingPolicy.name == scaling_policy['name'],
                ScalingGroup.id == scaling_group_record.id,
                join_classes=[ScalingGroup]
            )
            log.debug("Found existing scaling policy record in DB...")
        except ScalingPolicy.DoesNotExist:
            log.debug("Creating scaling policy record in DB...")
            scaling_policy_record = ScalingPolicyRepository.create(
                nsr_id=nsr_id,
                name=scaling_policy['name'],
                cooldown_time=scaling_policy['cooldown-time'],
                scaling_group=scaling_group_record,
            )
            if 'scale-in-operation-type' in scaling_policy:
                scaling_policy_record.scale_in_operation = scaling_policy[
                    'scale-in-operation-type']
            if 'scale-out-operation-type' in scaling_policy:
                scaling_policy_record.scale_out_operation = scaling_policy[
                    'scale-out-operation-type']
            if 'enabled' in scaling_policy:
                scaling_policy_record.enabled = scaling_policy['enabled']
            scaling_policy_record.save()
            log.debug("Created scaling policy record in DB : name=%s, scaling_group.name=%s",
                      scaling_policy_record.name,
                      scaling_policy_record.scaling_group.name)
        return scaling_policy_record

    def _get_or_create_scaling_criteria(self, nsr_id: str, scaling_criteria: dict,
                                        scaling_policy_record: ScalingPolicy):
        try:
            scaling_criteria_record = ScalingCriteriaRepository.get(
                ScalingPolicy.id == scaling_policy_record.id,
                ScalingCriteria.name == scaling_criteria['name'],
                join_classes=[ScalingPolicy]
            )
            log.debug("Found existing scaling criteria record in DB...")
        except ScalingCriteria.DoesNotExist:
            log.debug("Creating scaling criteria record in DB...")
            scaling_criteria_record = ScalingCriteriaRepository.create(
                nsr_id=nsr_id,
                name=scaling_criteria['name'],
                scaling_policy=scaling_policy_record
            )
            log.debug(
                "Created scaling criteria record in DB : name=%s, scaling_policy.name=%s",
                scaling_criteria_record.name,
                scaling_criteria_record.scaling_policy.name)
        return scaling_criteria_record

    def _get_monitored_vdurs(self, vnf_monitoring_param: dict, vdurs: List[dict], vnfd: dict):
        monitored_vdurs = []
        if 'vdu-monitoring-param' in vnf_monitoring_param:
            monitored_vdurs = list(
                filter(
                    lambda vdur: vdur['vdu-id-ref'] == vnf_monitoring_param
                    ['vdu-monitoring-param']
                    ['vdu-ref'],
                    vdurs
                )
            )
        elif 'vdu-metric' in vnf_monitoring_param:
            monitored_vdurs = list(
                filter(
                    lambda vdur: vdur['vdu-id-ref'] == vnf_monitoring_param
                    ['vdu-metric']
                    ['vdu-ref'],
                    vdurs
                )
            )
        elif 'vnf-metric' in vnf_monitoring_param:
            vdu = VnfdUtils.get_mgmt_vdu(vnfd)
            monitored_vdurs = list(
                filter(
                    lambda vdur: vdur['vdu-id-ref'] == vdu['id'],
                    vdurs
                )
            )
        else:
            log.warning(
                "Scaling criteria is referring to a vnf-monitoring-param that does not "
                "contain a reference to a vdu or vnf metric.")
        return monitored_vdurs

    def _get_metric_name(self, vnf_monitoring_param: dict, vdur: dict, vnfd: dict):
        vdu = next(
            filter(lambda vdu: vdu['id'] == vdur['vdu-id-ref'], vnfd['vdu'])
        )
        if 'vdu-monitoring-param' in vnf_monitoring_param:
            vdu_monitoring_param = next(filter(
                lambda param: param['id'] == vnf_monitoring_param['vdu-monitoring-param'][
                    'vdu-monitoring-param-ref'], vdu['monitoring-param']))
            nfvi_metric = vdu_monitoring_param['nfvi-metric']
            return nfvi_metric
        if 'vdu-metric' in vnf_monitoring_param:
            vnf_metric_name = vnf_monitoring_param['vdu-metric']['vdu-metric-name-ref']
            return vnf_metric_name
        if 'vnf-metric' in vnf_monitoring_param:
            vnf_metric_name = vnf_monitoring_param['vnf-metric']['vnf-metric-name-ref']
            return vnf_metric_name
        raise ValueError('No metric name found for vnf_monitoring_param %s' % vnf_monitoring_param['id'])
