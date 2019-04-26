..
 Copyright 2018 Whitestack, LLC
 *************************************************************

 This file is part of OSM policy management module
 All Rights Reserved to Whitestack, LLC

 Licensed under the Apache License, Version 2.0 (the "License"); you may
 not use this file except in compliance with the License. You may obtain
 a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.
 For those usages not covered by the Apache License, Version 2.0 please
 contact: bdiaz@whitestack.com or glavado@whitestack.com

OSM POL Module
****************

POL is a policy management module for OSM.
It configures and handles autoscaling policies and vnf defined alarms.

Components
**********

POL module has the following components:

* POL Alarming Service: Handles VNF alarms.
* POL Autoscaling Service: Handles autoscaling policy configuration, alarms creation and executing scaling actions through LCM.
* POL Agent: Listens message bus and calls action in corresponding service.

Configuration
*************

Configuration is handled by the file [pol.yaml] (osm_pol/core/pol.yaml). You can pass a personalized configuration file
through the `--config-file` flag.

Example:

    osm-policy-agent --config-file your-config.yaml

Configuration variables can also be overridden through environment variables by following the convention:
OSMPOL_<SECTION>_<VARIABLE>=<VALUE>

Example:

    OSMPOL_GLOBAL_LOGLEVEL=DEBUG

Development
***********

The following is a reference for making changes to the code and testing them in a running OSM deployment.

::

    git clone https://osm.etsi.org/gerrit/osm/POL.git
    cd POL
    # Make your changes here
    # Build the image
    docker build -t opensourcemano/pol:develop -f docker/Dockerfile .
    # Deploy that image in a running OSM deployment
    docker service update --force --image opensourcemano/pol:develop osm_pol
    # Change a specific env variable
    docker service update --force --env-add VARIABLE_NAME=new_value osm_pol
    # View logs
    docker logs $(docker ps -qf name=osm_pol.1)


Developers
**********

* Benjamín Díaz <bdiaz@whitestack.com>, Whitestack, Argentina

Maintainers
***********

* Benjamín Díaz, Whitestack, Argentina

Contributions
*************

For information on how to contribute to OSM POL module, please get in touch with
the developer or the maintainer.

Any new code must follow the development guidelines detailed in the Dev Guidelines
in the OSM Wiki and pass all tests.

Dev Guidelines can be found at:

    [https://osm.etsi.org/wikipub/index.php/Workflow_with_OSM_tools]
