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

# Script that runs the docker file locally with proper mounts
# Usage: run.sh <CONTAINER_VERSION>
#

# If either of these change, also change the env var in build.sh
export SERVICE_TAG=${SERVICE_TAG:-neuro-san-studio}
export SERVICE_VERSION=${SERVICE_VERSION:-0.0.1}

function check_directory() {
    working_dir=$(pwd)
    if [ "neuro-san-studio" == "$(basename "${working_dir}")" ]
    then
        # We are in the neuro-san repo.
        # Change directories so that the rest of the script will work OK.
        cd . || exit 1
    fi
}

function run() {

    check_directory

    # RUN_JSON_INPUT_DIR will go away when an actual GRPC service exists
    # for receiving the input. For now it's a mounted directory.
    CONTAINER_VERSION=${SERVICE_VERSION}
    echo "Using CONTAINER_VERSION ${CONTAINER_VERSION}"
    echo "Using args '$*'"

    #
    # Host networking only works on Linux. Get the OS we are running on
    #
    OS=$(uname)
    echo "OS: ${OS}"

    # Using a default network of 'host' is actually easiest thing when
    # locally testing against a vault server container set up with https,
    # but allow this to be changeable by env var.
    network=${NETWORK:="host"}
    echo "Network is ${network}"

    SERVICE_NAME="NeuroSanAgents"
    # Assume the first port EXPOSEd in the Dockerfile is the input port
    DOCKERFILE=$(find . -name Dockerfile | sort | head -1)
    SERVICE_PORT=$(grep ^EXPOSE < "${DOCKERFILE}" | head -1 | awk '{ print $2 }')
    SERVICE_HTTP_PORT=$(grep ^EXPOSE < "${DOCKERFILE}" | tail -1 | awk '{ print $2 }')
    echo "SERVICE_PORT: ${SERVICE_PORT}"
    echo "SERVICE_HTTP_PORT: ${SERVICE_HTTP_PORT}"

    # Run the docker container in interactive mode
    #   Mount the 1st command line arg as the place where input files come from
    #   Slurp in the rest as environment variables, all of which are optional.

    docker_cmd="docker run --rm -it \
        --name=$SERVICE_NAME \
        --network=$network \
        -e OPENAI_API_KEY \
        -e ANTHROPIC_API_KEY \
        -e TOOL_REGISTRY_FILE=$1 \
        -p $SERVICE_PORT:$SERVICE_PORT \
        -p $SERVICE_HTTP_PORT:$SERVICE_HTTP_PORT \
            neuro-san/${SERVICE_TAG}:$CONTAINER_VERSION"

    if [ "${OS}" == "Darwin" ];then
        # Host networking does not work for non-Linux operating systems
        # Remove it from the docker command
        docker_cmd=${docker_cmd/--network=$network/}
    fi

    echo "${docker_cmd}"
    $docker_cmd
}

function main() {
    run "$@"
}

# Pass all command line args to function
main "$@"
