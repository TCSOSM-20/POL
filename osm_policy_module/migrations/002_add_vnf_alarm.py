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
"""Peewee migrations -- 002_add_vnf_alarm.py.

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
    class VnfAlarm(pw.Model):
        id = pw.AutoField()
        alarm_id = pw.CharField(max_length=255)
        alarm_uuid = pw.CharField(max_length=255, unique=True)
        nsr_id = pw.CharField(max_length=255)
        vnf_member_index = pw.IntegerField()
        vdu_name = pw.CharField(max_length=255)

        class Meta:
            table_name = "vnfalarm"

    @migrator.create_model
    class AlarmAction(pw.Model):
        id = pw.AutoField()
        type = pw.CharField(max_length=255)
        url = pw.TextField()
        alarm = pw.ForeignKeyField(backref='actions', column_name='alarm_id', field='id',
                                   model=migrator.orm['vnfalarm'], on_delete='CASCADE')

        class Meta:
            table_name = "alarmaction"


def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""

    migrator.remove_model('vnfalarm')

    migrator.remove_model('alarmaction')
