#!/bin/bash -e
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

# Script used to build the container
# Usage:
#   build.sh [--no-cache]
#
# The script must be run from the top-level directory of where your
# registries and code lives so as to properly import them into the Dockerfile.
#

# If either of these change, also change the env var in run.sh
export SERVICE_TAG=${SERVICE_TAG:-neuro-san-studio}
export SERVICE_VERSION=${SERVICE_VERSION:-0.0.1}

function check_directory() {
    working_dir=$(pwd)
    if [ "neuro-san-studio" == "$(basename "${working_dir}")" ]
    then
        # We are in the neuro-san-studio repo.
        # Change directories so that the rest of the script will work OK.
        cd . || exit 1
    fi
}


function build_main() {
    # Outline function which delegates most work to other functions

    check_directory

    # Parse for a specific arg when debugging
    CACHE_OR_NO_CACHE="--rm"
    if [ "$1" == "--no-cache" ]
    then
        CACHE_OR_NO_CACHE="--no-cache --progress=plain"
    fi

    if [ -z "${TARGET_PLATFORM}" ]
    then
        TARGET_PLATFORM="linux/amd64"
    fi
    echo "Target Platform for Docker image generation: ${TARGET_PLATFORM}"

    DOCKERFILE=$(find . -name Dockerfile | sort | head -1)

    # Build the docker image
    # DOCKER_BUILDKIT needed for secrets
    # shellcheck disable=SC2086
    DOCKER_BUILDKIT=1 docker build \
        -t neuro-san/${SERVICE_TAG}:${SERVICE_VERSION} \
        --platform ${TARGET_PLATFORM} \
        --build-arg="NEURO_SAN_VERSION=${USER}-$(date +'%Y-%m-%d-%H-%M')" \
        -f "${DOCKERFILE}" \
        ${CACHE_OR_NO_CACHE} \
        .
}


# Call the build_main() outline function
build_main "$@"
