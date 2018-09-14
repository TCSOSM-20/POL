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
import logging
import sys
import unittest
import uuid
from unittest.mock import patch, Mock

from kafka import KafkaProducer
from osm_common.dbmongo import DbMongo
from osm_policy_module.core import database
from peewee import SqliteDatabase

from osm_policy_module.common.mon_client import MonClient
from osm_policy_module.core.agent import PolicyModuleAgent
from osm_policy_module.core.database import ScalingRecord, ScalingAlarm, BaseModel

log = logging.getLogger()
log.level = logging.INFO
stream_handler = logging.StreamHandler(sys.stdout)
log.addHandler(stream_handler)

nsr_record_mock = {
    "_id": "87776f33-b67c-417a-8119-cb08e4098951",
    "crete-time": 1535392482.0044956,
    "operational-status": "running",
    "ssh-authorized-key": None,
    "name-ref": "cirros_ns",
    "nsd": {
        "name": "cirros_vdu_scaling_ns",
        "_id": "d7c8bd3c-eb39-4514-8847-19f01345524f",
        "vld": [
            {
                "id": "cirros_nsd_vld1",
                "name": "cirros_nsd_vld1",
                "type": "ELAN",
                "mgmt-network": "true",
                "vnfd-connection-point-ref": [
                    {
                        "vnfd-id-ref": "cirros_vdu_scaling_vnf",
                        "member-vnf-index-ref": 1,
                        "vnfd-connection-point-ref": "eth0"
                    },
                    {
                        "vnfd-id-ref": "cirros_vdu_scaling_vnf",
                        "member-vnf-index-ref": 2,
                        "vnfd-connection-point-ref": "eth0"
                    }
                ]
            }
        ],
        "vendor": "OSM",
        "constituent-vnfd": [
            {
                "member-vnf-index": "1",
                "vnfd-id-ref": "cirros_vdu_scaling_vnf"
            },
            {
                "member-vnf-index": "2",
                "vnfd-id-ref": "cirros_vdu_scaling_vnf"
            }
        ],
        "version": "1.0",
        "id": "cirros_vdu_scaling_ns",
        "description": "Simple NS example with a cirros_vdu_scaling_vnf",
        "logo": "osm.png",
        "_admin": {
            "created": 1535392246.499733,
            "userDefinedData": {

            },
            "usageSate": "NOT_IN_USE",
            "storage": {
                "zipfile": "package.tar.gz",
                "fs": "local",
                "path": "/app/storage/",
                "folder": "d7c8bd3c-eb39-4514-8847-19f01345524f",
                "pkg-dir": "cirros_nsd",
                "descriptor": "cirros_nsd/cirros_vdu_scaling_nsd.yaml"
            },
            "onboardingState": "ONBOARDED",
            "modified": 1535392246.499733,
            "projects_read": [
                "admin"
            ],
            "operationalState": "ENABLED",
            "projects_write": [
                "admin"
            ]
        },
        "short-name": "cirros_vdu_scaling_ns"
    },
    "id": "87776f33-b67c-417a-8119-cb08e4098951",
    "config-status": "configured",
    "operational-events": [],
    "_admin": {
        "created": 1535392482.0084584,
        "projects_read": [
            "admin"
        ],
        "nsState": "INSTANTIATED",
        "modified": 1535392482.0084584,
        "projects_write": [
            "admin"
        ],
        "deployed": {
            "RO": {
                "vnfd_id": {
                    "cirros_vdu_scaling_vnf": "7445e347-fe2f-431a-abc2-8b9be3d093c6"
                },
                "nsd_id": "92c56cf0-f8fa-488c-9afb-9f3d78ae6bbb",
                "nsr_id": "637e12cd-c201-4c44-8ebd-70fb57a4dcee",
                "nsr_status": "BUILD"
            }
        }
    },
    "nsd-ref": "cirros_vdu_scaling_ns",
    "name": "cirros_ns",
    "resource-orchestrator": "osmopenmano",
    "instantiate_params": {
        "nsDescription": "default description",
        "nsdId": "d7c8bd3c-eb39-4514-8847-19f01345524f",
        "nsr_id": "87776f33-b67c-417a-8119-cb08e4098951",
        "nsName": "cirros_ns",
        "vimAccountId": "be48ae31-1d46-4892-a4b4-d69abd55714b"
    },
    "description": "default description",
    "constituent-vnfr-ref": [
        "0d9d06ad-3fc2-418c-9934-465e815fafe2",
        "3336eb44-77df-4c4f-9881-d2828d259864"
    ],
    "admin-status": "ENABLED",
    "detailed-status": "done",
    "datacenter": "be48ae31-1d46-4892-a4b4-d69abd55714b",
    "orchestration-progress": {

    },
    "short-name": "cirros_ns",
    "ns-instance-config-ref": "87776f33-b67c-417a-8119-cb08e4098951",
    "nsd-name-ref": "cirros_vdu_scaling_ns",
    "admin": {
        "deployed": {
            "RO": {
                "nsr_status": "ACTIVE"
            }
        }
    }
}

vnfr_record_mocks = [
    {
        "_id": "0d9d06ad-3fc2-418c-9934-465e815fafe2",
        "ip-address": "192.168.160.2",
        "created-time": 1535392482.0044956,
        "vim-account-id": "be48ae31-1d46-4892-a4b4-d69abd55714b",
        "vdur": [
            {
                "interfaces": [
                    {
                        "mac-address": "fa:16:3e:71:fd:b8",
                        "name": "eth0",
                        "ip-address": "192.168.160.2"
                    }
                ],
                "status": "ACTIVE",
                "vim-id": "63a65636-9fc8-4022-b070-980823e6266a",
                "name": "cirros_ns-1-cirros_vnfd-VM-1",
                "status-detailed": None,
                "ip-address": "192.168.160.2",
                "vdu-id-ref": "cirros_vnfd-VM"
            }
        ],
        "id": "0d9d06ad-3fc2-418c-9934-465e815fafe2",
        "vnfd-ref": "cirros_vdu_scaling_vnf",
        "vnfd-id": "63f44c41-45ee-456b-b10d-5f08fb1796e0",
        "_admin": {
            "created": 1535392482.0067868,
            "projects_read": [
                "admin"
            ],
            "modified": 1535392482.0067868,
            "projects_write": [
                "admin"
            ]
        },
        "nsr-id-ref": "87776f33-b67c-417a-8119-cb08e4098951",
        "member-vnf-index-ref": "1",
        "connection-point": [
            {
                "name": "eth0",
                "id": None,
                "connection-point-id": None
            }
        ]
    },
    {
        "_id": "3336eb44-77df-4c4f-9881-d2828d259864",
        "ip-address": "192.168.160.10",
        "created-time": 1535392482.0044956,
        "vim-account-id": "be48ae31-1d46-4892-a4b4-d69abd55714b",
        "vdur": [
            {
                "interfaces": [
                    {
                        "mac-address": "fa:16:3e:1e:76:e8",
                        "name": "eth0",
                        "ip-address": "192.168.160.10"
                    }
                ],
                "status": "ACTIVE",
                "vim-id": "a154b8d3-2b10-421a-a51d-4b391d9bd366",
                "name": "cirros_ns-2-cirros_vnfd-VM-1",
                "status-detailed": None,
                "ip-address": "192.168.160.10",
                "vdu-id-ref": "cirros_vnfd-VM"
            }
        ],
        "id": "3336eb44-77df-4c4f-9881-d2828d259864",
        "vnfd-ref": "cirros_vdu_scaling_vnf",
        "vnfd-id": "63f44c41-45ee-456b-b10d-5f08fb1796e0",
        "_admin": {
            "created": 1535392482.0076294,
            "projects_read": [
                "admin"
            ],
            "modified": 1535392482.0076294,
            "projects_write": [
                "admin"
            ]
        },
        "nsr-id-ref": "87776f33-b67c-417a-8119-cb08e4098951",
        "member-vnf-index-ref": "2",
        "connection-point": [
            {
                "name": "eth0",
                "id": None,
                "connection-point-id": None
            }
        ]}]

nsd_record_mock = {'name': 'cirros_vdu_scaling_ns',
                   'version': '1.0',
                   'short-name': 'cirros_vdu_scaling_ns',
                   'logo': 'osm.png',
                   'id': 'cirros_vdu_scaling_ns',
                   'description': 'Simple NS example with a cirros_vdu_scaling_vnf',
                   'vendor': 'OSM',
                   'vld': [
                       {'name': 'cirros_nsd_vld1',
                        'type': 'ELAN',
                        'id': 'cirros_nsd_vld1',
                        'mgmt-network': 'true',
                        'vnfd-connection-point-ref': [
                            {'vnfd-id-ref': 'cirros_vdu_scaling_vnf',
                             'vnfd-connection-point-ref': 'eth0',
                             'member-vnf-index-ref': 1},
                            {'vnfd-id-ref': 'cirros_vdu_scaling_vnf',
                             'vnfd-connection-point-ref': 'eth0',
                             'member-vnf-index-ref': 2}]}],
                   'constituent-vnfd': [{'vnfd-id-ref': 'cirros_vdu_scaling_vnf',
                                         'member-vnf-index': '1'},
                                        {'vnfd-id-ref': 'cirros_vdu_scaling_vnf',
                                         'member-vnf-index': '2'}]}

vnfd_record_mock = {
    "_id": "63f44c41-45ee-456b-b10d-5f08fb1796e0",
    "name": "cirros_vdu_scaling_vnf",
    "vendor": "OSM",
    "vdu": [
        {
            "name": "cirros_vnfd-VM",
            "monitoring-param": [
                {
                    "id": "cirros_vnfd-VM_memory_util",
                    "nfvi-metric": "average_memory_utilization"
                }
            ],
            "vm-flavor": {
                "vcpu-count": 1,
                "memory-mb": 256,
                "storage-gb": 2
            },
            "description": "cirros_vnfd-VM",
            "count": 1,
            "id": "cirros_vnfd-VM",
            "interface": [
                {
                    "name": "eth0",
                    "external-connection-point-ref": "eth0",
                    "type": "EXTERNAL",
                    "virtual-interface": {
                        "bandwidth": "0",
                        "type": "VIRTIO",
                        "vpci": "0000:00:0a.0"
                    }
                }
            ],
            "image": "cirros034"
        }
    ],
    "monitoring-param": [
        {
            "id": "cirros_vnf_memory_util",
            "name": "cirros_vnf_memory_util",
            "aggregation-type": "AVERAGE",
            "vdu-monitoring-param-ref": "cirros_vnfd-VM_memory_util",
            "vdu-ref": "cirros_vnfd-VM"
        }
    ],
    "description": "Simple VNF example with a cirros and a scaling group descriptor",
    "id": "cirros_vdu_scaling_vnf",
    "logo": "cirros-64.png",
    "version": "1.0",
    "connection-point": [
        {
            "name": "eth0",
            "type": "VPORT"
        }
    ],
    "mgmt-interface": {
        "cp": "eth0"
    },
    "scaling-group-descriptor": [
        {
            "name": "scale_cirros_vnfd-VM",
            "min-instance-count": 1,
            "vdu": [
                {
                    "count": 1,
                    "vdu-id-ref": "cirros_vnfd-VM"
                }
            ],
            "max-instance-count": 10,
            "scaling-policy": [
                {
                    "name": "auto_memory_util_above_threshold",
                    "scaling-type": "automatic",
                    "cooldown-time": 60,
                    "threshold-time": 10,
                    "scaling-criteria": [
                        {
                            "name": "group1_memory_util_above_threshold",
                            "vnf-monitoring-param-ref": "cirros_vnf_memory_util",
                            "scale-out-threshold": 80,
                            "scale-out-relational-operation": "GT",
                            "scale-in-relational-operation": "LT",
                            "scale-in-threshold": 20
                        }
                    ]
                }
            ]
        }
    ],
    "short-name": "cirros_vdu_scaling_vnf",
    "_admin": {
        "created": 1535392242.6281035,
        "modified": 1535392242.6281035,
        "storage": {
            "zipfile": "package.tar.gz",
            "pkg-dir": "cirros_vnf",
            "path": "/app/storage/",
            "folder": "63f44c41-45ee-456b-b10d-5f08fb1796e0",
            "fs": "local",
            "descriptor": "cirros_vnf/cirros_vdu_scaling_vnfd.yaml"
        },
        "usageSate": "NOT_IN_USE",
        "onboardingState": "ONBOARDED",
        "userDefinedData": {

        },
        "projects_read": [
            "admin"
        ],
        "operationalState": "ENABLED",
        "projects_write": [
            "admin"
        ]
    }
}

test_db = SqliteDatabase(':memory:')

MODELS = [ScalingRecord, ScalingAlarm]


class PolicyModuleAgentTest(unittest.TestCase):
    def setUp(self):
        super()
        database.db = test_db
        test_db.bind(MODELS)
        test_db.connect()
        test_db.drop_tables(MODELS)
        test_db.create_tables(MODELS)

    def tearDown(self):
        super()

    @patch.object(DbMongo, 'db_connect', Mock())
    @patch.object(KafkaProducer, '__init__')
    @patch.object(MonClient, 'create_alarm')
    @patch.object(PolicyModuleAgent, '_get_vnfd')
    @patch.object(PolicyModuleAgent, '_get_nsr')
    @patch.object(PolicyModuleAgent, '_get_vnfr')
    def test_configure_scaling_groups(self, get_vnfr, get_nsr, get_vnfd, create_alarm, kafka_producer_init):
        def _test_configure_scaling_groups_get_vnfr(*args, **kwargs):
            if '1' in args[1]:
                return vnfr_record_mocks[0]
            if '2' in args[1]:
                return vnfr_record_mocks[1]

        def _test_configure_scaling_groups_create_alarm(*args, **kwargs):
            return uuid.uuid4()

        kafka_producer_init.return_value = None
        get_vnfr.side_effect = _test_configure_scaling_groups_get_vnfr
        get_nsr.return_value = nsr_record_mock
        get_vnfd.return_value = vnfd_record_mock
        create_alarm.side_effect = _test_configure_scaling_groups_create_alarm
        agent = PolicyModuleAgent()
        agent._configure_scaling_groups("test_nsr_id")
        create_alarm.assert_any_call(metric_name='average_memory_utilization',
                                     ns_id='test_nsr_id',
                                     operation='GT',
                                     statistic='AVERAGE',
                                     threshold=80,
                                     vdu_name='cirros_vnfd-VM',
                                     vnf_member_index='1')
        scaling_record = ScalingRecord.get()
        self.assertEqual(scaling_record.name, 'scale_cirros_vnfd-VM')
        self.assertEqual(scaling_record.nsr_id, 'test_nsr_id')
        self.assertIsNotNone(scaling_record)


if __name__ == '__main__':
    unittest.main()
