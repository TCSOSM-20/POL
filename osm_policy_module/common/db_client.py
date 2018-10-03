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
from osm_common import dbmongo

from osm_policy_module.core.config import Config


class DbClient:
    def __init__(self):
        cfg = Config.instance()
        self.common_db = dbmongo.DbMongo()
        self.common_db.db_connect({'host': cfg.OSMPOL_DATABASE_HOST,
                                   'port': int(cfg.OSMPOL_DATABASE_PORT),
                                   'name': 'osm'})

    def get_vnfr(self, nsr_id: str, member_index: int):
        vnfr = self.common_db.get_one(table="vnfrs",
                                      filter={"nsr-id-ref": nsr_id, "member-vnf-index-ref": str(member_index)})
        return vnfr

    def get_vnfrs(self, nsr_id: str):
        return [self.get_vnfr(nsr_id, member['member-vnf-index']) for member in
                self.get_nsr(nsr_id)['nsd']['constituent-vnfd']]

    def get_vnfd(self, vnfd_id: str):
        vnfr = self.common_db.get_one(table="vnfds",
                                      filter={"_id": vnfd_id})
        return vnfr

    def get_nsr(self, nsr_id: str):
        nsr = self.common_db.get_one(table="nsrs",
                                     filter={"id": nsr_id})
        return nsr

    def get_nslcmop(self, nslcmop_id):
        nslcmop = self.common_db.get_one(table="nslcmops",
                                         filter={"_id": nslcmop_id})
        return nslcmop
