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
import argparse
import asyncio
import logging
import sys
import os

from osm_policy_module.core.agent import PolicyModuleAgent
from osm_policy_module.core.config import Config
from osm_policy_module.core.database import DatabaseManager


def main():
    # Cleanup old temp health file
    if os.path.exists('/tmp/osm_pol_agent_health_flag'):
        os.remove('/tmp/osm_pol_agent_health_flag')

    parser = argparse.ArgumentParser(prog='osm-policy-agent')
    parser.add_argument('--config-file', nargs='?', help='POL configuration file')
    args = parser.parse_args()
    cfg = Config(args.config_file)

    root = logging.getLogger()
    root.setLevel(logging.getLevelName(cfg.get('global', 'loglevel')))
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.getLevelName(cfg.get('global', 'loglevel')))
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', '%m/%d/%Y %I:%M:%S %p')
    ch.setFormatter(formatter)
    root.addHandler(ch)

    log = logging.getLogger(__name__)
    log.debug("Config: %s", cfg.conf)
    log.info("Initializing database...")
    db_manager = DatabaseManager(cfg)
    db_manager.create_tables()
    log.info("Database initialized correctly.")
    log.info("Starting policy module agent...")
    loop = asyncio.get_event_loop()
    agent = PolicyModuleAgent(cfg, loop)
    agent.run()


if __name__ == '__main__':
    main()
