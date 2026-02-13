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

# Startup script for both the Neuro SAN server and NSFlow client on macOS/Linux.
# Usage: ./start_all.sh [additional run.py arguments]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "${SCRIPT_DIR}/venv" ]; then
    echo "Virtual environment not found. Please run 'make install' first."
    exit 1
fi

source "${SCRIPT_DIR}/venv/bin/activate"
export PYTHONPATH="${SCRIPT_DIR}"

python -m run "$@"
