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

FROM ubuntu:16.04

LABEL authors="Benjamín Díaz"

RUN apt-get --yes update \
 && apt-get --yes install python3 python3-pip libmysqlclient-dev git \
 && pip3 install pip==9.0.3

COPY requirements.txt /policy_module/requirements.txt

RUN pip3 install -r /policy_module/requirements.txt

COPY . /policy_module

RUN pip3 install /policy_module

ENV OSMPOL_MESSAGE_DRIVER kafka
ENV OSMPOL_MESSAGE_HOST kafka
ENV OSMPOL_MESSAGE_PORT 9092

ENV OSMPOL_DATABASE_DRIVER mongo
ENV OSMPOL_DATABASE_URI mongodb://mongo:27017

ENV OSMPOL_SQL_DATABASE_URI sqlite:///policy_module.db

ENV OSMPOL_LOG_LEVEL INFO
ENV OSMPOL_KAFKA_LOG_LEVEL WARN

CMD osm-policy-agent
