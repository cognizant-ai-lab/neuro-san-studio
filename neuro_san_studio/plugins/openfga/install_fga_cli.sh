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
