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
# Starts neuro-san server and the combined app (nsflow + config editor) based
# on NEURO_SAN_ENABLED and NSFLOW_ENABLED env vars. CONFIG_EDITOR_ENABLED is
# checked inside combined_start.py. When enabled (default), the combined app
# starts immediately so Azure's startup probe on port 4173 passes quickly.

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
# Bootstrap: smart-merge baked-in registries into Azure File Share
# -------------------------------------------------------------------
# On every startup we sync the container image's registries into the
# (possibly Azure File Share-mounted) registries directory.  This
# ensures newly added agent definitions, updated manifests and sub-
# manifests always reach the running container.
#
# Strategy:
#   - All directories EXCEPT generated/ are copied from the seed,
#     overwriting stale files and adding new ones.
#   - generated/ is never overwritten — it holds user-created agent
#     networks.  We only create the directory and seed an empty
#     manifest.hocon if they don't already exist.
# -------------------------------------------------------------------
REGISTRIES_DIR="${APP_SOURCE}/registries"
SEED_DIR="${APP_SOURCE}/registries-seed"

if [ -d "${SEED_DIR}" ]; then
    echo "Syncing registries from container image..."

    # Sync everything except generated/
    for item in "${SEED_DIR}"/*; do
        basename="$(basename "${item}")"
        if [ "${basename}" = "generated" ]; then
            continue  # handled below
        fi
        cp -r "${item}" "${REGISTRIES_DIR}/"
    done

    # Ensure generated/ exists with its manifest, but never overwrite
    mkdir -p "${REGISTRIES_DIR}/generated"
    if [ ! -f "${REGISTRIES_DIR}/generated/manifest.hocon" ]; then
        cp "${SEED_DIR}/generated/manifest.hocon" \
           "${REGISTRIES_DIR}/generated/manifest.hocon"
        echo "Seeded generated/manifest.hocon."
    fi

    echo "Registry sync complete."
fi

# -------------------------------------------------------------------
# Configuration (overridable via Docker ENV)
# -------------------------------------------------------------------
NSFLOW_HOST=${NSFLOW_HOST:-0.0.0.0}
NSFLOW_PORT=${NSFLOW_PORT:-4173}

# -------------------------------------------------------------------
# Signal handling: forward signals to all child processes
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
# 2) Start combined app: nsflow + config editor (background, if enabled)
#    Do NOT wait for neuro-san — nsflow serves its UI right away.
#    Azure startup probe on port 4173 will pass as soon as uvicorn binds.
#    Agent functionality becomes available once neuro-san is ready.
#    The config editor is embedded via iframe and served at /editor/
#    on the same port. CONFIG_EDITOR_ENABLED is checked inside
#    combined_start.py to conditionally mount the editor sub-app.
# -------------------------------------------------------------------
if [ "${NSFLOW_ENABLED:-true}" = "true" ]; then
    echo "Starting combined app (nsflow + editor) on ${NSFLOW_HOST}:${NSFLOW_PORT}..."
    ${PYTHON} -u "${SCRIPT_DIR}/combined_start.py" &
    NSFLOW_PID=$!
    echo "combined app started (PID ${NSFLOW_PID})"
else
    echo "nsflow disabled (NSFLOW_ENABLED=${NSFLOW_ENABLED})"
fi

# -------------------------------------------------------------------
# 3) Monitor enabled processes — exit if any enabled process dies
# -------------------------------------------------------------------
echo "Services starting. Monitoring..."
while true; do
    if [ -n "${NEURO_SAN_PID}" ] && ! kill -0 "${NEURO_SAN_PID}" 2>/dev/null; then
        echo "ERROR: neuro-san server (PID ${NEURO_SAN_PID}) exited unexpectedly"
        cleanup
    fi
    if [ -n "${NSFLOW_PID}" ] && ! kill -0 "${NSFLOW_PID}" 2>/dev/null; then
        echo "ERROR: combined app (PID ${NSFLOW_PID}) exited unexpectedly"
        cleanup
    fi
    sleep 5
done
