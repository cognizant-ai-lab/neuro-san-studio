#!/bin/bash
#
# Script to run a sample OpenFGA server from scratch using docker commands
# This will reset any authorization database every time it is run.

DOCKER_NETWORK="bridge"

# Remove any existing containers that might be left over from previous runs of this script
docker ps -a --filter volume=openfga | grep -v CONTAINER | awk '{print $1}' | xargs docker rm

# Create a fresh volume
docker volume create openfga

# Run the server with SQLite migrations
docker run --rm --network=${DOCKER_NETWORK} \
    -v openfga:/home/nonroot \
    -u nonroot \
    openfga/openfga migrate --datastore-engine sqlite --datastore-uri 'file:/home/nonroot/openfga.db'

# Run the server to stay up
# Note the translation of local port 8082 to the container port 8080 for the OpenFGA internal HTTP server
docker run --name openfga --network=${DOCKER_NETWORK} \
    -p 3000:3000 -p 8082:8080 -p 8081:8081 \
    -v openfga:/home/nonroot \
    -u nonroot  \
    openfga/openfga run --datastore-engine sqlite --datastore-uri 'file:/home/nonroot/openfga.db'
