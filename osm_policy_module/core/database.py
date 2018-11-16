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

from peewee import CharField, IntegerField, ForeignKeyField, Model, TextField, AutoField, DateTimeField
from playhouse.db_url import connect

from osm_policy_module.core.config import Config

log = logging.getLogger(__name__)
cfg = Config.instance()

db = connect(cfg.OSMPOL_SQL_DATABASE_URI)


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
    last_scale = DateTimeField(default=datetime.datetime.now)
    scaling_group = ForeignKeyField(ScalingGroup, related_name='scaling_policies')


class ScalingCriteria(BaseModel):
    name = CharField()
    scaling_policy = ForeignKeyField(ScalingPolicy, related_name='scaling_criterias')


class ScalingAlarm(BaseModel):
    alarm_id = CharField()
    action = CharField()
    vnf_member_index = IntegerField()
    vdu_name = CharField()
    scaling_criteria = ForeignKeyField(ScalingCriteria, related_name='scaling_alarms')


class DatabaseManager:
    def create_tables(self):
        try:
            db.connect()
            db.create_tables([ScalingGroup, ScalingPolicy, ScalingCriteria, ScalingAlarm])
            db.close()
        except Exception:
            log.exception("Error creating tables: ")

    def get_alarm(self, alarm_id: str):
        return ScalingAlarm.select().where(ScalingAlarm.alarm_id == alarm_id).get()
