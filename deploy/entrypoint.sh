#!/bin/bash
# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

# Entry point script which manages the transition from
# Docker bash to Python

cat /etc/os-release

PYTHON=python3
echo "Using python ${PYTHON}"

PIP=pip3
echo "Using pip ${PIP}"

# The Log Bridge plugin aggregates logs from server and client subprocesses, and pretty-prints them.
# But we only deploy the neuro-san server here, and it has its own logging configuration.
# So we forcibly disable the log bridge plugin to avoid conflicts.
export LOGBRIDGE_ENABLED=false

echo "Preparing app..."
if [ -z "${PYTHONPATH}" ]
then
    PYTHONPATH=$(pwd)
fi
export PYTHONPATH

echo "Toolchain:"
${PYTHON} --version
${PIP} --version
${PIP} freeze

PACKAGE_INSTALL=${PACKAGE_INSTALL:-.}
echo "PACKAGE_INSTALL is ${PACKAGE_INSTALL}"

echo "DIAGNOSTIC: Dumping sys.path and PYTHONPATH before server start..."
${PYTHON} -c "import sys, os; print('DIAGNOSTIC sys.path:', sys.path); print('DIAGNOSTIC PYTHONPATH:', os.environ.get('PYTHONPATH'))"

echo "Starting service with args '$1'..."
${PYTHON} "${APP_SOURCE}"/neuro_san_studio/runner/neuro_san_server_wrapper.py "$@"

echo "Done."
