#!/bin/bash

# Copyright © 2023-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

# Create a local virtual environment for running/developing neuro-san-studio on
# FREE-THREADED CPython 3.14t (no-GIL).
#
#   * The free-threaded interpreter is provisioned with `uv` (there is no
#     official python:3.14t image or, usually, a system 3.14t interpreter).
#   * All dependencies -- including leaf-common and neuro-san -- are installed
#     from requirements.txt as-is (i.e. from PyPI).
#   * orjson (transitive via neuro-san -> langsmith / langgraph-sdk) refuses to
#     build under a free-threaded interpreter unless ORJSON_BUILD_FREETHREADED
#     is set, so we set it.
#
# Pass --local-neuro-san to install neuro-san from the local ../neuro-san source
# tree instead of the PyPI pin in requirements.txt (useful when testing
# unreleased neuro-san changes under 3.14t).
#
# neuro-san-studio itself is NOT installed into the venv; run it from the repo
# source via PYTHONPATH, as studio's Makefile does. Usage is printed at the end.
#
# Usage:
#   build_scripts/make_venv_py314t.sh [VENV_DIR] [--dev] [--local-neuro-san] [--force]
#
#   VENV_DIR            Where to create the venv. Default: <repo>/.venv-py314t
#   --dev              Also install requirements-build.txt (tests, linters).
#                      These may hit additional cp314t source-build issues.
#   --local-neuro-san  Install neuro-san from ../neuro-san source instead of the
#                      PyPI pin in requirements.txt.
#   --force            Recreate VENV_DIR if it already exists.
#
# Environment overrides:
#   PY314T_PYTHON_VERSION    interpreter to provision (default: 3.14t). Named
#                            specifically so it cannot collide with a generic
#                            PYTHON_VERSION that may already be set in your shell.
#   NEURO_SAN_DIR            path to local neuro-san    (default: ../neuro-san)
#   AUTO_INSTALL_UV=1        install uv automatically if it is missing
#   AUTO_INSTALL_RUST=1      install a Rust toolchain (rustup) automatically if missing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PY314T_PYTHON_VERSION="${PY314T_PYTHON_VERSION:-3.14t}"
NEURO_SAN_DIR="${NEURO_SAN_DIR:-${REPO_ROOT}/../neuro-san}"

VENV_DIR=""
WITH_DEV=0
LOCAL_NEURO_SAN=0
FORCE=0

function log()  { echo "[make_venv_py314t] $*"; }
function warn() { echo "[make_venv_py314t] WARNING: $*" >&2; }
function die()  { echo "[make_venv_py314t] ERROR: $*" >&2; exit 1; }

function parse_args() {
    for arg in "$@"; do
        case "${arg}" in
            --dev)             WITH_DEV=1 ;;
            --local-neuro-san) LOCAL_NEURO_SAN=1 ;;
            --force)           FORCE=1 ;;
            -h|--help)
                sed -n '18,54p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
                exit 0
                ;;
            --*) die "unknown option: ${arg}" ;;
            *)
                if [ -z "${VENV_DIR}" ]; then
                    VENV_DIR="${arg}"
                else
                    die "unexpected extra argument: ${arg}"
                fi
                ;;
        esac
    done
    VENV_DIR="${VENV_DIR:-${REPO_ROOT}/.venv-py314t}"
}

function ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        log "uv found: $(uv --version)"
        return
    fi
    if [ "${AUTO_INSTALL_UV:-0}" = "1" ]; then
        log "uv not found; installing (AUTO_INSTALL_UV=1)..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="${HOME}/.local/bin:${PATH}"
        command -v uv >/dev/null 2>&1 || die "uv install did not put uv on PATH"
    else
        die "uv is required but not installed. Install it with:
       curl -LsSf https://astral.sh/uv/install.sh | sh
   (or set AUTO_INSTALL_UV=1 to let this script do it), then re-run."
    fi
}

function ensure_build_toolchain() {
    command -v cc >/dev/null 2>&1 || command -v gcc >/dev/null 2>&1 \
        || warn "no C compiler (cc/gcc) found; native dependencies may fail to build.
   Linux: install build-essential;  macOS: xcode-select --install"

    if command -v cargo >/dev/null 2>&1; then
        log "cargo found: $(cargo --version)"
        return
    fi
    if [ "${AUTO_INSTALL_RUST:-0}" = "1" ]; then
        log "cargo not found; installing rustup toolchain (AUTO_INSTALL_RUST=1)..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
        # shellcheck disable=SC1091
        source "${CARGO_HOME:-${HOME}/.cargo}/env"
        command -v cargo >/dev/null 2>&1 || die "rustup install did not put cargo on PATH"
    else
        die "cargo (Rust) is required to build orjson for free-threaded Python, but was not found.
   Install it with:
       curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
       source \"\$HOME/.cargo/env\"
   (or set AUTO_INSTALL_RUST=1 to let this script do it), then re-run."
    fi
}

function main() {
    parse_args "$@"

    [ -f "${REPO_ROOT}/requirements.txt" ] || die "no requirements.txt at repo root ${REPO_ROOT}"
    if [ "${LOCAL_NEURO_SAN}" = 1 ] && [ ! -f "${NEURO_SAN_DIR}/requirements.txt" ]; then
        die "--local-neuro-san given but no neuro-san source at '${NEURO_SAN_DIR}'. Set NEURO_SAN_DIR."
    fi

    ensure_uv
    ensure_build_toolchain

    log "repo root              : ${REPO_ROOT}"
    log "venv dir               : ${VENV_DIR}"
    log "python                 : ${PY314T_PYTHON_VERSION} (free-threaded)"
    log "neuro-san source       : $([ "${LOCAL_NEURO_SAN}" = 1 ] && echo "${NEURO_SAN_DIR} (local)" || echo "PyPI pin from requirements.txt")"
    log "install build/dev reqs : $([ "${WITH_DEV}" = 1 ] && echo yes || echo no)"

    if [ -e "${VENV_DIR}" ]; then
        if [ "${FORCE}" = 1 ]; then
            case "${VENV_DIR}" in
                ""|"/"|"."|".."|"${REPO_ROOT}") die "refusing to remove unsafe VENV_DIR='${VENV_DIR}'" ;;
            esac
            log "removing existing ${VENV_DIR} (--force)"
            rm -rf -- "${VENV_DIR}"
        else
            die "${VENV_DIR} already exists. Pass --force to recreate, or choose another VENV_DIR."
        fi
    fi

    # 1. Provision the free-threaded interpreter and create the venv.
    log "installing free-threaded CPython ${PY314T_PYTHON_VERSION} via uv..."
    uv python install "${PY314T_PYTHON_VERSION}"

    log "creating venv at ${VENV_DIR}..."
    uv venv --python "${PY314T_PYTHON_VERSION}" --seed "${VENV_DIR}"

    local venv_python="${VENV_DIR}/bin/python"

    # Fail loudly if uv did NOT give us a free-threaded interpreter, so a silent
    # fallback to a regular GIL build (e.g. because the requested version resolved
    # to a non-free-threaded interpreter) can never pass as a successful run.
    if ! "${venv_python}" -c "import sysconfig, sys; sys.exit(0 if sysconfig.get_config_var('Py_GIL_DISABLED') else 1)"; then
        local got
        got="$("${venv_python}" -c 'import sys; print(sys.version.split()[0])')"
        die "venv interpreter is ${got}, NOT a free-threaded build.
   uv resolved '${PY314T_PYTHON_VERSION}' to a regular GIL interpreter. Check that
   PY314T_PYTHON_VERSION (and any UV_PYTHON / .python-version) name a free-threaded
   interpreter such as 3.14t, and that no stray override is in effect."
    fi
    log "confirmed free-threaded interpreter: $("${venv_python}" -c 'import sys; print(sys.version.split()[0])')"

    # 2. Assemble the requirements to install. By default everything -- including
    #    leaf-common and neuro-san -- comes from requirements.txt (i.e. PyPI).
    #    With --local-neuro-san, the neuro-san pin is stripped and neuro-san is
    #    installed from local source instead.
    local -a install_args=()
    local req_file="${REPO_ROOT}/requirements.txt"
    local req_tmp=""
    if [ "${LOCAL_NEURO_SAN}" = 1 ]; then
        req_tmp="$(mktemp)"
        # shellcheck disable=SC2064
        trap "rm -f '${req_tmp}'" EXIT
        grep -viE '^[[:space:]]*neuro-san([[:space:]]|[<>=!~;[]|$)' \
            "${REPO_ROOT}/requirements.txt" > "${req_tmp}"
        req_file="${req_tmp}"
        install_args+=("${NEURO_SAN_DIR}")
    fi
    install_args+=(-r "${req_file}")
    if [ "${WITH_DEV}" = 1 ]; then
        if [ -f "${REPO_ROOT}/requirements-build.txt" ]; then
            install_args+=(-r "${REPO_ROOT}/requirements-build.txt")
        else
            warn "requirements-build.txt not found; skipping --dev extras"
        fi
    fi

    log "installing dependencies (this compiles orjson and possibly others for cp314t)..."
    ORJSON_BUILD_FREETHREADED=1 \
        uv pip install --python "${venv_python}" "${install_args[@]}"

    # 3. Sanity check.
    log "verifying environment..."
    PYTHONPATH="${REPO_ROOT}" "${venv_python}" - <<'PY'
import sys
print("  python              :", sys.version.split()[0], "(" + sys.executable + ")")
gil = getattr(sys, "_is_gil_enabled", None)
print("  free-threaded build :", bool(__import__("sysconfig").get_config_var("Py_GIL_DISABLED")))
print("  GIL enabled now     :", gil() if gil else "n/a")
import leaf_common, neuro_san
print("  leaf_common         : OK")
print("  neuro_san           : OK")
import neuro_san_studio
print("  neuro_san_studio    : OK (from repo source)")
PY

    print_usage "${venv_python}"
}

function print_usage() {
    local venv_python="$1"
    cat <<EOF

[make_venv_py314t] Done. Virtual environment ready at:
    ${VENV_DIR}

To use it to run neuro-san-studio from source:

    source "${VENV_DIR}/bin/activate"
    export PYTHONPATH="${REPO_ROOT}"
    export AGENT_MANIFEST_FILE="${REPO_ROOT}/registries/manifest.hocon"
    export AGENT_TOOL_PATH="${REPO_ROOT}/coded_tools"
    export OPENAI_API_KEY="<your key>"        # demos default to OpenAI

    # Free-threaded builds default to GIL OFF, but importing a not-yet-safe
    # extension (e.g. orjson) would auto RE-ENABLE it. To match the container,
    # which forces it off, export:
    export PYTHON_GIL=0

    # Start the neuro-san server (serves studio's registries):
    python -m neuro_san.service.main_loop.server_main_loop
    # ...then drive it with the CLI client, e.g.:
    #   python -m neuro_san.client.agent_cli --agent copy_cat --http
    # (nsflow is installed for the web UI as well.)

Quick GIL check in this venv:
    ${venv_python} -c "import sys, orjson; print('GIL enabled:', sys._is_gil_enabled())"

EOF
}

main "$@"
