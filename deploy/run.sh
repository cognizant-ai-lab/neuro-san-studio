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

    # Check for an environment file to pass to the docker run command.
    # This is optional, but if it is set and exists, we will use it.
    # Environment file should be a simple text file with lines of the form:
    #   VAR_NAME=VAR_VALUE
    # This allows us to pass in any collection of run-specific values
env_file_cmd=""
if [[ -n "${SERVICE_ENV_FILE:-}" && -f "$SERVICE_ENV_FILE" ]]; then
    if [[ "$SERVICE_ENV_FILE" =~ [[:space:]] ]]; then
        echo "ERROR: SERVICE_ENV_FILE path contains whitespace; please use a path without spaces: '$SERVICE_ENV_FILE'" >&2
        exit 1
    fi
    echo "Using service environment file: $SERVICE_ENV_FILE"
    env_file_cmd="--env-file $SERVICE_ENV_FILE"
elif [[ -z "${SERVICE_ENV_FILE:-}" ]]; then
    echo "SERVICE_ENV_FILE is not set."
else
    echo "WARNING: '$SERVICE_ENV_FILE' does not exist."
fi

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

    # RUN_JSON_INPUT_DIR will go away when an actual service exists
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
    # Get the HTTP port EXPOSED in the Dockerfile
    DOCKERFILE=$(find . -name Dockerfile | sort | head -1)
    SERVICE_HTTP_PORT=$(grep ^EXPOSE < "${DOCKERFILE}" | head -1 | awk '{ print $2 }')
    echo "SERVICE_HTTP_PORT: ${SERVICE_HTTP_PORT}"

    # Note that we have to set the equivalent of the ulimit -n via the docker run
    # command line.  We don't want the ceiling of fds to interfere with how many
    # requests we can serve in the container.
    FILE_DESCRIPTOR_MAX=100000

    # Run the docker container in interactive mode
    #   Mount the 1st command line arg as the place where input files come from
    #   Slurp in the rest as environment variables, all of which are optional.

    docker_cmd="docker run --rm -it \
        --ulimit nofile=${FILE_DESCRIPTOR_MAX}:${FILE_DESCRIPTOR_MAX} \
        --name=$SERVICE_NAME \
        --network=$network \
        -e OPENAI_API_KEY \
        -e OPENAI_API_BASE \
        -e ANTHROPIC_API_KEY \
        -e LANGFUSE_ENABLED \
        -e LANGFUSE_SECRET_KEY \
        -e LANGFUSE_PUBLIC_KEY \
        -e LANGFUSE_HOST \
        -e AGENT_RESERVATIONS_S3_BUCKET \
        -e AGENT_EXTERNAL_RESERVATIONS_STORAGE \
        -e AGENT_SESSION_REQUIRE_HTTPS=false \
        -e AGENT_NETWORK_DESIGNER_USER_RESERVATIONS \
        -e AWS_SECRET_ACCESS_KEY \
        -e AWS_ACCESS_KEY_ID \
        -e LEAF_LOG_SENSITIVE=true \
        -e TOOL_REGISTRY_FILE=$1 \
        ${env_file_cmd} \
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
