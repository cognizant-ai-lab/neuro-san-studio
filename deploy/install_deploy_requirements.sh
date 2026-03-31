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

# Installs optional deploy-specific Python requirements from a Docker
# build secret.  Following the unileaf pattern, the CI workflow creates
# a credentialed copy of the requirements file (with tokens embedded in
# git+https:// URLs) and mounts it as the "with_creds_requirements"
# Docker secret.
#
# When building locally (without the secret), this script is a no-op.

set -eu

SECRET_PATH="/run/secrets/with_creds_requirements"

if [ ! -f "${SECRET_PATH}" ]; then
    echo "No deploy requirements secret found — skipping."
    exit 0
fi

echo "Installing deploy requirements from secret ..."
python -m pip install --prefix=/install --no-cache-dir \
    -r "${SECRET_PATH}"
