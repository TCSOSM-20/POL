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
from setuptools import setup

_name = 'osm_policy_module'
_version_command = ('git describe --match v* --tags --long --dirty', 'pep440-git-full')
_author = "Benjamín Díaz"
_author_email = 'bdiaz@whitestack.com'
_description = 'OSM Policy Module'
_maintainer = 'Benjamín Díaz'
_maintainer_email = 'bdiaz@whitestack.com'
_license = 'Apache 2.0'
_url = 'https://osm.etsi.org/gitweb/?p=osm/MON.git;a=tree'

setup(
    name=_name,
    version_command=_version_command,
    description=_description,
    long_description=open('README.rst', encoding='utf-8').read(),
    author=_author,
    author_email=_author_email,
    maintainer=_maintainer,
    maintainer_email=_maintainer_email,
    url=_url,
    license=_license,
    packages=[_name],
    package_dir={_name: _name},
    include_package_data=True,
    install_requires=[
        "aiokafka==0.4.*",
        "peewee==3.8.*",
        "jsonschema==2.6.*",
        "pyyaml==3.*",
        "pymysql",
        "peewee-migrate==1.1.*",
        "requests==2.*",
        "osm-common",
    ],
    entry_points={
        "console_scripts": [
            "osm-policy-agent = osm_policy_module.cmd.policy_module_agent:main",
        ]
    },
    dependency_links=[
        'git+https://osm.etsi.org/gerrit/osm/common.git#egg=osm-common'
    ],
    setup_requires=['setuptools-version-command']
)
