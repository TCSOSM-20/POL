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
import datetime
import logging
import os
from typing import Iterable, List

from peewee import CharField, IntegerField, ForeignKeyField, Model, TextField, AutoField, DateTimeField, Proxy, \
    BooleanField
from peewee_migrate import Router
from playhouse.db_url import connect

from osm_policy_module import migrations
from osm_policy_module.core.config import Config

log = logging.getLogger(__name__)

db = Proxy()


class BaseModel(Model):
    id = AutoField(primary_key=True)

    class Meta:
        database = db


class ScalingGroup(BaseModel):
    nsr_id = CharField()
    vnf_member_index = IntegerField()
    name = CharField()
    content = TextField()


class ScalingPolicy(BaseModel):
    name = CharField()
    cooldown_time = IntegerField()
    scale_in_operation = CharField(default='AND')
    scale_out_operation = CharField(default='OR')
    enabled = BooleanField(default=True)
    last_scale = DateTimeField(default=datetime.datetime.now)
    scaling_group = ForeignKeyField(ScalingGroup, related_name='scaling_policies', on_delete='CASCADE')


class ScalingCriteria(BaseModel):
    name = CharField()
    scaling_policy = ForeignKeyField(ScalingPolicy, related_name='scaling_criterias', on_delete='CASCADE')


class ScalingAlarm(BaseModel):
    alarm_uuid = CharField(unique=True)
    action = CharField()
    vnf_member_index = IntegerField()
    vdu_name = CharField()
    scaling_criteria = ForeignKeyField(ScalingCriteria, related_name='scaling_alarms', on_delete='CASCADE')
    last_status = CharField(default='insufficient-data')


class VnfAlarm(BaseModel):
    alarm_id = CharField()
    alarm_uuid = CharField(unique=True)
    nsr_id = CharField()
    vnf_member_index = IntegerField()
    vdu_name = CharField()


class AlarmAction(BaseModel):
    type = CharField()
    url = TextField()
    alarm = ForeignKeyField(VnfAlarm, related_name='actions', on_delete='CASCADE')


class DatabaseManager:
    def __init__(self, config: Config):
        db.initialize(connect(config.get('sql', 'database_uri')))

    def create_tables(self) -> None:
        db.connect()
        with db.atomic():
            router = Router(db, os.path.dirname(migrations.__file__))
            router.run()
        db.close()


class ScalingAlarmRepository:

    @staticmethod
    def list(*expressions) -> Iterable[ScalingAlarm]:
        return ScalingAlarm.select().where(*expressions)

    @staticmethod
    def get(*expressions, join_classes: List = None) -> ScalingAlarm:
        query = ScalingAlarm.select()
        if join_classes:
            for join_class in join_classes:
                query = query.join(join_class)
        return query.where(*expressions).get()

    @staticmethod
    def create(**query) -> ScalingAlarm:
        return ScalingAlarm.create(**query)


class ScalingGroupRepository:

    @staticmethod
    def list(*expressions) -> Iterable[ScalingGroup]:
        return ScalingGroup.select().where(*expressions)

    @staticmethod
    def get(*expressions) -> ScalingGroup:
        return ScalingGroup.select().where(*expressions).get()

    @staticmethod
    def create(**query) -> ScalingGroup:
        return ScalingGroup.create(**query)


class ScalingPolicyRepository:

    @staticmethod
    def list(*expressions, join_classes: List = None) -> Iterable[ScalingPolicy]:
        query = ScalingPolicy.select()
        if join_classes:
            for join_class in join_classes:
                query = query.join(join_class)
        return query.where(*expressions)

    @staticmethod
    def get(*expressions, join_classes: List = None) -> ScalingPolicy:
        query = ScalingPolicy.select()
        if join_classes:
            for join_class in join_classes:
                query = query.join(join_class)
        return query.where(*expressions).get()

    @staticmethod
    def create(**query) -> ScalingPolicy:
        return ScalingPolicy.create(**query)


class ScalingCriteriaRepository:

    @staticmethod
    def list(*expressions, join_classes: List = None) -> Iterable[ScalingCriteria]:
        query = ScalingCriteria.select()
        if join_classes:
            for join_class in join_classes:
                query = query.join(join_class)
        return query.where(*expressions)

    @staticmethod
    def get(*expressions, join_classes: List = None) -> ScalingCriteria:
        query = ScalingCriteria.select()
        if join_classes:
            for join_class in join_classes:
                query = query.join(join_class)
        return query.where(*expressions).get()

    @staticmethod
    def create(**query) -> ScalingCriteria:
        return ScalingCriteria.create(**query)


class VnfAlarmRepository:

    @staticmethod
    def list(*expressions) -> Iterable[VnfAlarm]:
        return VnfAlarm.select().where(*expressions)

    @staticmethod
    def get(*expressions) -> VnfAlarm:
        return VnfAlarm.select().where(*expressions).get()

    @staticmethod
    def create(**query) -> VnfAlarm:
        return VnfAlarm.create(**query)


class AlarmActionRepository:

    @staticmethod
    def list(*expressions) -> Iterable[AlarmAction]:
        return AlarmAction.select().where(*expressions)

    @staticmethod
    def get(*expressions) -> AlarmAction:
        return AlarmAction.select().where(*expressions).get()

    @staticmethod
    def create(**query) -> AlarmAction:
        return AlarmAction.create(**query)
