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
"""Global configuration managed by environment variables."""

import logging
import os

from collections import namedtuple

import six

from osm_policy_module.core.singleton import Singleton

log = logging.getLogger(__name__)


class BadConfigError(Exception):
    """Configuration exception."""

    pass


class CfgParam(namedtuple('CfgParam', ['key', 'default', 'data_type'])):
    """Configuration parameter definition."""

    def value(self, data):
        """Convert a string to the parameter type."""
        try:
            return self.data_type(data)
        except (ValueError, TypeError):
            raise BadConfigError(
                'Invalid value "%s" for configuration parameter "%s"' % (
                    data, self.key))


@Singleton
class Config(object):
    """Configuration object."""

    _configuration = [
        CfgParam('OSMPOL_MESSAGE_DRIVER', "kafka", six.text_type),
        CfgParam('OSMPOL_MESSAGE_HOST', "localhost", six.text_type),
        CfgParam('OSMPOL_MESSAGE_PORT', 9092, int),
        CfgParam('OSMPOL_DATABASE_DRIVER', "mongo", six.text_type),
        CfgParam('OSMPOL_DATABASE_HOST', "mongo", six.text_type),
        CfgParam('OSMPOL_DATABASE_PORT', 27017, int),
        CfgParam('OSMPOL_SQL_DATABASE_URI', "sqlite:///mon_sqlite.db", six.text_type),
        CfgParam('OSMPOL_LOG_LEVEL', "INFO", six.text_type),
        CfgParam('OSMPOL_KAFKA_LOG_LEVEL', "WARN", six.text_type),
    ]

    _config_dict = {cfg.key: cfg for cfg in _configuration}
    _config_keys = _config_dict.keys()

    def __init__(self):
        """Set the default values."""
        for cfg in self._configuration:
            setattr(self, cfg.key, cfg.default)
        self.read_environ()

    def read_environ(self):
        """Check the appropriate environment variables and update defaults."""
        for key in self._config_keys:
            try:
                val = self._config_dict[key].data_type(os.environ[key])
                setattr(self, key, val)
            except KeyError as exc:
                log.debug("Environment variable not present: %s", exc)
        return
