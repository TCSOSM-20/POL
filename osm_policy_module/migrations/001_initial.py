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
"""Peewee migrations -- 001_initial.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['model_name']            # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.python(func, *args, **kwargs)        # Run python code
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.drop_index(model, *col_names)
    > migrator.add_not_null(model, *field_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)

"""

import peewee as pw

SQL = pw.SQL


def migrate(migrator, database, fake=False, **kwargs):
    """Write your migrations here."""

    @migrator.create_model
    class BaseModel(pw.Model):
        id = pw.AutoField()

        class Meta:
            table_name = "basemodel"

    @migrator.create_model
    class ScalingGroup(pw.Model):
        id = pw.AutoField()
        nsr_id = pw.CharField(max_length=255)
        vnf_member_index = pw.IntegerField()
        name = pw.CharField(max_length=255)
        content = pw.TextField()

        class Meta:
            table_name = "scalinggroup"

    @migrator.create_model
    class ScalingPolicy(pw.Model):
        id = pw.AutoField()
        name = pw.CharField(max_length=255)
        cooldown_time = pw.IntegerField()
        last_scale = pw.DateTimeField()
        scaling_group = pw.ForeignKeyField(backref='scaling_policies', column_name='scaling_group_id', field='id',
                                           model=migrator.orm['scalinggroup'], on_delete='CASCADE')

        class Meta:
            table_name = "scalingpolicy"

    @migrator.create_model
    class ScalingCriteria(pw.Model):
        id = pw.AutoField()
        name = pw.CharField(max_length=255)
        scaling_policy = pw.ForeignKeyField(backref='scaling_criterias', column_name='scaling_policy_id', field='id',
                                            model=migrator.orm['scalingpolicy'], on_delete='CASCADE')

        class Meta:
            table_name = "scalingcriteria"

    @migrator.create_model
    class ScalingAlarm(pw.Model):
        id = pw.AutoField()
        alarm_uuid = pw.CharField(max_length=255, unique=True)
        action = pw.CharField(max_length=255)
        vnf_member_index = pw.IntegerField()
        vdu_name = pw.CharField(max_length=255)
        scaling_criteria = pw.ForeignKeyField(backref='scaling_alarms', column_name='scaling_criteria_id', field='id',
                                              model=migrator.orm['scalingcriteria'], on_delete='CASCADE')

        class Meta:
            table_name = "scalingalarm"


def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""

    migrator.remove_model('scalingalarm')

    migrator.remove_model('scalingcriteria')

    migrator.remove_model('scalingpolicy')

    migrator.remove_model('scalinggroup')

    migrator.remove_model('basemodel')
