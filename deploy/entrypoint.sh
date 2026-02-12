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
# Selectively starts neuro-san server, nsflow web UI, and/or config editor
# based on NEURO_SAN_ENABLED, NSFLOW_ENABLED, CONFIG_EDITOR_ENABLED env vars.
# When all three are enabled (default), nsflow starts immediately so Azure's
# startup probe on port 4173 passes quickly.

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
# Bootstrap: seed Azure File Share from baked-in registries if empty
# -------------------------------------------------------------------
REGISTRIES_DIR="${APP_SOURCE}/registries"
SEED_DIR="${APP_SOURCE}/registries-seed"

if [ -d "${SEED_DIR}" ]; then
    if [ -z "$(ls -A "${REGISTRIES_DIR}" 2>/dev/null)" ]; then
        echo "Seeding registries from container image..."
        cp -r "${SEED_DIR}/"* "${REGISTRIES_DIR}/"
        echo "Seeding complete."
    else
        echo "Registries directory already populated."
    fi
fi

# -------------------------------------------------------------------
# Configuration (overridable via Docker ENV)
# -------------------------------------------------------------------
NSFLOW_HOST=${NSFLOW_HOST:-0.0.0.0}
NSFLOW_PORT=${NSFLOW_PORT:-4173}
CONFIG_EDITOR_HOST=${CONFIG_EDITOR_HOST:-0.0.0.0}
CONFIG_EDITOR_PORT=${CONFIG_EDITOR_PORT:-4174}

# -------------------------------------------------------------------
# Signal handling: forward signals to all child processes
# -------------------------------------------------------------------
NEURO_SAN_PID=""
NSFLOW_PID=""
CONFIG_EDITOR_PID=""

cleanup() {
    echo "Received shutdown signal. Stopping all processes..."
    [ -n "${NEURO_SAN_PID}" ] && kill -TERM "${NEURO_SAN_PID}" 2>/dev/null || true
    [ -n "${NSFLOW_PID}" ] && kill -TERM "${NSFLOW_PID}" 2>/dev/null || true
    [ -n "${CONFIG_EDITOR_PID}" ] && kill -TERM "${CONFIG_EDITOR_PID}" 2>/dev/null || true
    sleep 3
    [ -n "${NEURO_SAN_PID}" ] && kill -KILL "${NEURO_SAN_PID}" 2>/dev/null || true
    [ -n "${NSFLOW_PID}" ] && kill -KILL "${NSFLOW_PID}" 2>/dev/null || true
    [ -n "${CONFIG_EDITOR_PID}" ] && kill -KILL "${CONFIG_EDITOR_PID}" 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------------------------------------------------------
# 1) Start neuro-san server (background, if enabled)
# -------------------------------------------------------------------
if [ "${NEURO_SAN_ENABLED:-true}" = "true" ]; then
    echo "Starting neuro-san server..."
    ${PYTHON} "${PACKAGE_INSTALL}"/neuro_san/service/main_loop/server_main_loop.py "$@" &
    NEURO_SAN_PID=$!
    echo "neuro-san server started (PID ${NEURO_SAN_PID})"
else
    echo "neuro-san server disabled (NEURO_SAN_ENABLED=${NEURO_SAN_ENABLED})"
fi

# -------------------------------------------------------------------
# 2) Start nsflow web UI (background, if enabled)
#    Do NOT wait for neuro-san — nsflow serves its UI right away.
#    Azure startup probe on port 4173 will pass as soon as uvicorn binds.
#    Agent functionality becomes available once neuro-san is ready.
# -------------------------------------------------------------------
if [ "${NSFLOW_ENABLED:-true}" = "true" ]; then
    echo "Starting nsflow on ${NSFLOW_HOST}:${NSFLOW_PORT}..."
    ${PYTHON} -u "${SCRIPT_DIR}/nsflow_start.py" &
    NSFLOW_PID=$!
    echo "nsflow started (PID ${NSFLOW_PID})"
else
    echo "nsflow disabled (NSFLOW_ENABLED=${NSFLOW_ENABLED})"
fi

# -------------------------------------------------------------------
# 3) Start config editor (background, if enabled)
# -------------------------------------------------------------------
if [ "${CONFIG_EDITOR_ENABLED:-true}" = "true" ]; then
    echo "Starting config editor on ${CONFIG_EDITOR_HOST}:${CONFIG_EDITOR_PORT}..."
    ${PYTHON} -u "${SCRIPT_DIR}/config_editor_start.py" &
    CONFIG_EDITOR_PID=$!
    echo "config editor started (PID ${CONFIG_EDITOR_PID})"
else
    echo "Config editor disabled (CONFIG_EDITOR_ENABLED=${CONFIG_EDITOR_ENABLED})"
fi

# -------------------------------------------------------------------
# 4) Monitor enabled processes — exit if any enabled process dies
# -------------------------------------------------------------------
echo "Services starting. Monitoring..."
while true; do
    if [ -n "${NEURO_SAN_PID}" ] && ! kill -0 "${NEURO_SAN_PID}" 2>/dev/null; then
        echo "ERROR: neuro-san server (PID ${NEURO_SAN_PID}) exited unexpectedly"
        cleanup
    fi
    if [ -n "${NSFLOW_PID}" ] && ! kill -0 "${NSFLOW_PID}" 2>/dev/null; then
        echo "ERROR: nsflow (PID ${NSFLOW_PID}) exited unexpectedly"
        cleanup
    fi
    if [ -n "${CONFIG_EDITOR_PID}" ] && ! kill -0 "${CONFIG_EDITOR_PID}" 2>/dev/null; then
        echo "ERROR: config editor (PID ${CONFIG_EDITOR_PID}) exited unexpectedly"
        cleanup
    fi
    sleep 5
done
