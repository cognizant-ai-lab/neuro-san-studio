#!/bin/bash
set -e
#
# Script to run a sample OpenFGA server from scratch using docker commands
# This will reset any authorization database every time it is run.


#
# Env vars to control the behavior of this script
#

# This Docker network allows containers to talk to each other and ports on the main host,
# but not any incoming traffic.  See https://docs.docker.com/engine/network/ for more info
DOCKER_NETWORK="bridge"

# Name of the docker volume where the database is stored across container instances
VOLUME=neuro_san_openfga

# The user for the mount
CONTAINER_USER=nonroot

# The mount for the volume
MOUNT=/home/${CONTAINER_USER}

# Type of datastore to use
DATASTORE=sqlite

# URI on the volume where the database is stored
DATASTORE_URI="file:${MOUNT}/openfga.db"

# Port for incoming traffic to the OpenFGA container-internal HTTP server outside of the container
INCOMING_HTTP_PORT=8082

# Name of the OpenFGA container
CONTAINER_NAME=neuro_san_openfga

#
# Beginning essentials
#

# Make sure docker is installed
docker --version

# From  https://openfga.dev/docs/getting-started/setup-openfga/docker#step-by-step
# Pull the OpenFGA image if needed
docker pull openfga/openfga

#
# Clean up
#

# Remove any existing containers that might be left over from previous runs of this script
CONTAINERS=$(docker ps -a --filter volume=${VOLUME} | grep -v CONTAINER | awk '{print $1}')
if [ -n "${CONTAINERS}" ]
then
    echo "${CONTAINERS}" | xargs docker rm -f
fi

# Remove any existing volumes that might be left over from previous runs of this script.
docker volume rm -f ${VOLUME}


#
# From https://openfga.dev/docs/getting-started/setup-openfga/docker#using-sqlite
#

# Create a fresh volume
docker volume create ${VOLUME}

# Run the server with SQLite migrations
docker run --rm --network="${DOCKER_NETWORK}" \
    -v ${VOLUME}:${MOUNT} \
    -u ${CONTAINER_USER} \
    openfga/openfga migrate --datastore-engine ${DATASTORE} --datastore-uri "${DATASTORE_URI}"

# Run the server to stay up
# Note the translation of local port INCOMING_HTTP_PORT to the container port 8080
# for the OpenFGA internal HTTP server
docker run --name ${CONTAINER_NAME} --network="${DOCKER_NETWORK}" \
    -p 3000:3000 -p ${INCOMING_HTTP_PORT}:8080 -p 8081:8081 \
    -v ${VOLUME}:${MOUNT} \
    -u ${CONTAINER_USER}  \
    openfga/openfga run --datastore-engine ${DATASTORE} --datastore-uri "${DATASTORE_URI}"
