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

# Entry point script which manages the transition from Docker bash to Python.
# Starts both the neuro-san server and the nsflow web UI in parallel.
# nsflow starts immediately so Azure's startup probe on port 4173 passes quickly.
# nsflow will serve its UI right away; agent calls work once neuro-san is ready.

set -eo pipefail

# -------------------------------------------------------------------
# Diagnostics
# -------------------------------------------------------------------
cat /etc/os-release

PYTHON=python3
echo "Using python ${PYTHON}"

PIP=pip3
echo "Using pip ${PIP}"

echo "Preparing app..."
if [ -z "${PYTHONPATH:-}" ]; then
    PYTHONPATH=$(pwd)
fi
export PYTHONPATH

echo "Toolchain:"
${PYTHON} --version
${PIP} --version
${PIP} freeze

PACKAGE_INSTALL=${PACKAGE_INSTALL:-.}
echo "PACKAGE_INSTALL is ${PACKAGE_INSTALL}"

# -------------------------------------------------------------------
# Configuration (overridable via Docker ENV)
# -------------------------------------------------------------------
NSFLOW_HOST=${NSFLOW_HOST:-0.0.0.0}
NSFLOW_PORT=${NSFLOW_PORT:-4173}

# -------------------------------------------------------------------
# Signal handling: forward signals to both child processes
# -------------------------------------------------------------------
NEURO_SAN_PID=""
NSFLOW_PID=""

cleanup() {
    echo "Received shutdown signal. Stopping all processes..."
    [ -n "${NEURO_SAN_PID}" ] && kill -TERM "${NEURO_SAN_PID}" 2>/dev/null || true
    [ -n "${NSFLOW_PID}" ] && kill -TERM "${NSFLOW_PID}" 2>/dev/null || true
    sleep 3
    [ -n "${NEURO_SAN_PID}" ] && kill -KILL "${NEURO_SAN_PID}" 2>/dev/null || true
    [ -n "${NSFLOW_PID}" ] && kill -KILL "${NSFLOW_PID}" 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# -------------------------------------------------------------------
# 1) Start neuro-san server (background)
# -------------------------------------------------------------------
echo "Starting neuro-san server..."
${PYTHON} "${PACKAGE_INSTALL}"/neuro_san/service/main_loop/server_main_loop.py "$@" &
NEURO_SAN_PID=$!
echo "neuro-san server started (PID ${NEURO_SAN_PID})"

# -------------------------------------------------------------------
# 2) Start nsflow web UI immediately (background)
#    Do NOT wait for neuro-san — nsflow serves its UI right away.
#    Azure startup probe on port 4173 will pass as soon as uvicorn binds.
#    Agent functionality becomes available once neuro-san is ready.
# -------------------------------------------------------------------
echo "Starting nsflow on ${NSFLOW_HOST}:${NSFLOW_PORT}..."
${PYTHON} -u -m uvicorn nsflow.backend.main:app \
    --host "${NSFLOW_HOST}" \
    --port "${NSFLOW_PORT}" &
NSFLOW_PID=$!
echo "nsflow started (PID ${NSFLOW_PID})"

# -------------------------------------------------------------------
# 3) Monitor both processes — exit if either dies
# -------------------------------------------------------------------
echo "Both services starting. Monitoring..."
while true; do
    if ! kill -0 "${NEURO_SAN_PID}" 2>/dev/null; then
        echo "ERROR: neuro-san server (PID ${NEURO_SAN_PID}) exited unexpectedly"
        kill -TERM "${NSFLOW_PID}" 2>/dev/null || true
        wait "${NSFLOW_PID}" 2>/dev/null || true
        exit 1
    fi
    if ! kill -0 "${NSFLOW_PID}" 2>/dev/null; then
        echo "ERROR: nsflow (PID ${NSFLOW_PID}) exited unexpectedly"
        kill -TERM "${NEURO_SAN_PID}" 2>/dev/null || true
        wait "${NEURO_SAN_PID}" 2>/dev/null || true
        exit 1
    fi
    sleep 5
done
