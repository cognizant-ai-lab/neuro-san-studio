#!/bin/bash

# Riffed from:
#
#   https://github.com/openfga/cli?tab=readme-ov-file#building-from-source
#
# This will need to be run with sudo.

BUILD_LOCAL=/tmp/fga_local_build
FGA_VERSION=0.7.8
FGA_TAG="v${FGA_VERSION}"
OPEN_FGA_CLI="${BUILD_LOCAL}/cli"
FGA_GO_VERSION=1.22.5
GO_DEST="${BUILD_LOCAL}"

# Create the destination directory for the source
mkdir -p "${OPEN_FGA_CLI}"

# Go there or die trying
cd "${OPEN_FGA_CLI}" || exit

# Clone the fga source. It's in golang
git clone --branch "${FGA_TAG}" https://github.com/openfga/cli "${OPEN_FGA_CLI}"

# Get the version of go that corresponds to this build.
# It might not be what we are using for development within the team
wget --progress=dot:giga "https://go.dev/dl/go${FGA_GO_VERSION}.linux-amd64.tar.gz"

# Remove anything we might have had before
rm -rf "${GO_DEST}/go"

# Unpack the golang distribution tarball
tar -C "${GO_DEST}" -xzf "go${FGA_GO_VERSION}.linux-amd64.tar.gz"

# Make the fga tool
PATH="${PATH}:${GO_DEST}/go/bin" make build

# Install the fga tool in /usr/bin
cp "${OPEN_FGA_CLI}/dist/fga" /usr/bin/fga

# Clean up after ourselves
rm -rf "${GO_DEST}/go"
rm -rf "${OPEN_FGA_CLI}"
rm -rf "${BUILD_LOCAL}"

# Run what we installed to be sure it's there
fga --version
