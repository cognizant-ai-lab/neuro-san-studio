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

# Use ./deploy/build.sh to build this container. After a successful build,
# you can use ./deploy/run.sh to run the built container locally.
#
# To find server-oriented environment variables to help you configure things
# how you want, search for "ENV AGENT_" in this file.

# Stage 1: Builder Stage - Use our python base image for installations
# Set python image as base image
FROM python:3.13-slim AS builder

# Set the shell and options per hadolint recommendations
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Reset to the root directory
WORKDIR /

# App-specific constants
ENV USERNAME=neuro-san
ENV APP_HOME=/usr/local/${USERNAME}
ENV APP_SOURCE=${APP_HOME}/myapp
ENV PIP3_VERSION=25.0.1

# Explicitly get the desired pip version
RUN pip3 install --upgrade pip==${PIP3_VERSION} --no-cache-dir ; mkdir -p ${APP_SOURCE}

# Having a requirements.txt file for your coded_tool dependencies is optional
COPY ./requirements.txt ${APP_SOURCE}/requirements.txt
# Move the work dir to the app source to find the requirements.
WORKDIR ${APP_SOURCE}
RUN if [ -f ${APP_SOURCE}/requirements.txt ]; \
    then \
        pip install --prefix=/install --no-cache-dir -r ${APP_SOURCE}/requirements.txt ; \
    fi

# Reset to the root directory
WORKDIR /

# Stage 2: Final Stage - Use a slim Python image
FROM python:3.13-slim AS final

# Set the shell and options in each FROM section per hadolint recommendations
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set up user for app running in container
ENV USERNAME=neuro-san
ENV APP_HOME=/usr/local/${USERNAME}
ENV APP_SOURCE=${APP_HOME}/myapp

RUN \
    useradd -ms /bin/bash -d ${APP_HOME} -u 1001 ${USERNAME} \
    && echo ${USERNAME}:pw | chpasswd \
    && mkdir -p ${APP_HOME}/.ssh \
    && chown -R ${USERNAME}: ${APP_HOME} \
    && chown -R ${USERNAME}: /usr/local/ \
    && chown -R ${USERNAME}: /var/log

# Set up a place for the mount of secrets to happen
RUN mkdir -p ${APP_HOME}/certs/aws \
    && ln -s ${APP_HOME}/certs/aws ${APP_HOME}/.aws

# This is the port the service will accept http requests on.
# This should be consistent with the main port for the service as described
# in any kubernetes <service>.yaml file
# This port number is also mentioned as AGENT_HTTP_PORT below
# and ServiceAgentSession.DEFAULT_HTTP_PORT
EXPOSE 8080

# Copy installed dependencies from the builder stage
COPY --from=builder /install /usr/local

# Copy application code and necessary files
# Note: The registries directory where agent definitions live is mandatory
#       The coded_tools directory where agent code lives is optional
#       [s] allows for registries/coded_tools from within client repo or neuro-san repo
COPY ./registries ${APP_SOURCE}/registries
COPY ./coded_tool[s] ${APP_SOURCE}/coded_tools
COPY ./deploy/entrypoint.sh ${APP_SOURCE}/deploy/entrypoint.sh
COPY ./deploy/logging.hocon ${APP_SOURCE}/deploy/logging.hocon

# Set up the entry point for when the container is run
USER ${USERNAME}
WORKDIR ${APP_SOURCE}

# RUN echo "$(pip show neuro-san | grep Location | awk '{print $2}')"
# This value below comes from the above RUN command. Cannot set ENV vars in Dockerfiles based on shell output.
ENV PACKAGE_INSTALL=/usr/local/lib/python3.13/site-packages
ENV APP_ENTRYPOINT=${APP_SOURCE}/deploy/entrypoint.sh

#
# API Keys for LLM Access
#
# Which env vars you need may vary depending on which LLM(s) you choose for your own setup.
# See https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#llm_config
# for details on different LLM providers' needs for out-of-the-box support.
#
# Note that you really really don't want to leak secrets by checking the actual values into source control.
# These are best injected into the container via environment variables at runtime ala:
#   docker run -e OPENAI_API_KEY=...
#

# OpenAI/ChatGPT access
ENV OPENAI_API_KEY=""

# Amazon Bedrock access
ENV AWS_ACCESS_KEY_ID=""
ENV AWS_SECRET_ACCESS_KEY=""

# Anthropic/Claude access
ENV ANTHROPIC_API_KEY=""

# MicroSoft Azure/OpenAI access
# OPENAI_API_KEY is a fallback for AZURE_OPENAI_API_KEY
# ENV AZURE_OPENAI_API_KEY=""
ENV AZURE_OPENAI_ENDPOINT=""

# Google/Gemini access
ENV GOOGLE_API_KEY=""

# NVidia LLM access
ENV NVIDIA_API_KEY=""

#
# Server configuration
#

# Point to the root folder of the app
ENV PYTHONPATH=${APP_SOURCE}

# Where to find the tool registry manifest file which lists all the agent hocon
# files to serve up from this server instance.  To specify multiple manifest files,
# simply use a space-separated list of manifest files.  Manifest dictionaries will
# effectively be merged, where content coming from manifests later in the list
# have precedence.
# This particular Dockerfile is put together to support a server that hosts multiple users
# and so we use the multiple manifest file aspect of the neuro-san server to turn off some networks
# that are not appropriate for such a deployment. See manifest_multiuser_overlay.hocon for more info.
ENV AGENT_MANIFEST_FILE="${APP_SOURCE}/registries/manifest.hocon ${APP_SOURCE}/registries/manifest_multiuser_overlay.hocon"

# An llm_info hocon file with user-provided llm descriptions that are to be used
# in addition to the neuro-san defaults.
ENV AGENT_LLM_INFO_FILE=""

# A toolbox_info hocon file with user-provided base tool and coded tool
# descriptions that are to be used in addition to the neuro-san defaults.
ENV AGENT_TOOLBOX_INFO_FILE=""

# Where to find the classes for CodedTool class implementations
# that are used by specific agent networks.
ENV AGENT_TOOL_PATH=${APP_SOURCE}/coded_tools

# Where to find the configuration file for Python logging.
# See https://docs.python.org/3/library/logging.config.html#dictionary-schema-details
# as to how this file can be configured for your own needs.  Examples there are provided in YAML,
# but these can be easily translated to JSON or HOCON (which we prefer).
# Another good resource: https://docs.python.org/3/howto/logging-cookbook.html
ENV AGENT_SERVICE_LOG_JSON=${APP_SOURCE}/deploy/logging.hocon

# Threshold for logging.
# See https://docs.python.org/3/library/logging.html#logging.Handler.setLevel
# and https://docs.python.org/3/library/logging.html#logging-levels for details.
ENV AGENT_SERVICE_LOG_LEVEL="DEBUG"

# The name of the service for health reporting purposes
ENV AGENT_SERVER_NAME="neuro-san-studio.Agent"

# Name of the service as seen in logs
ENV AGENT_SERVER_NAME_FOR_LOGS="Agent Server"

# A space-delimited list of http metadata request keys to forward to logs/other requests
# You can see how these are used in the AGENT_SERVICE_LOG_JSON file (see above) and
# customize this and the AGENT_SERVER_LOG_JSON file to your needs.
# Note that any metadata key needs to be all lowercase.
ENV AGENT_FORWARDED_REQUEST_METADATA="request_id user_id"

# Port number for http service endpoint
# If you are changing this, you should also change the EXPOSE port above
# and when running your container locally be sure to have a -p <port>:<port> entry
# for it on your docker run command line.
ENV AGENT_HTTP_PORT=8080

# Maximm number of requests that can be served at the same time
ENV AGENT_MAX_CONCURRENT_REQUESTS=50

# Number of requests served before the server shuts down in an orderly fashion.
# This is useful for testing response handling in clusters with duplicated pods.
# A value of -1 indicates unlimited requests are handled.
ENV AGENT_REQUEST_LIMIT=-1

# If this value is specified and >0,
# it will enable dynamic run-time updates of the server agents configuration according
# to current state of manifest file and separate agents registry files.
# Both manifest file and agent registry files could be modified (edited),
# agent registry files could be added or deleted from registry directory
# with corresponding changes in manifest file.
# Update will be done every AGENT_MANIFEST_UPDATE_PERIOD_SECONDS seconds;
# if value is not specified or <= 0, no such dynamic updates will be executed.
ENV AGENT_MANIFEST_UPDATE_PERIOD_SECONDS=0

# By default, the HTTP service reports the neuro-san library pip version in its health-check response.
# It is possible to add other libraries to those results by listing them within this env var
# below and separating them with spaces, like this: "langchain openai".
# Sometimes it is useful to report a library version explicitly when they are not actually
# pip-installed (for instance when building a container from your own source, it's the
# tag of your repo that you care about.)  In that case you can add an entry with its version
# after a colon, like this: "my_repo:1.2.3".
# You can combine these too, like this: "langchain openai my_repo:1.2.3"
ENV AGENT_VERSION_LIBS=""

# A reference to a Python class that can be used to log per-user request information.
# This class must have a no-args constructor and implement the
# neuro_san.interfaces.usage_logger.UsageLogger interface.
# When not set, this defaults to a null implementation.
ENV AGENT_USAGE_LOGGER=""

# A space-delimited list of http metadata request keys to forward to the AGENT_USAGE_LOGGER
# described above. When not set, this defaults to the value provided by
# AGENT_FORWARDED_REQUEST_METADATA
ENV AGENT_USAGE_LOGGER_METADATA=""

# A space-delimited list of http metadata request keys to forward to tracing/Observability
# infrastructure. When not set, this defaults to the value provided by
# AGENT_USAGE_LOGGER_METADATA or AGENT_FORWARDED_REQUEST_METADATA.
ENV AGENT_TRACING_METADATA_REQUEST_KEYS=""

# A space-delimited list of environment variables to be forwarded to observability tracing metadata.
# The defaults given here are standard Kubernetes environment variables for any given deployment pod.
# Only environment variables that are set to something other than the empty string will be forwarded.
ENV AGENT_TRACING_METADATA_ENV_VARS="POD_NAME POD_NAMESPACE POD_IP NODE_NAME"

# Size of backlog for TCP connections to http server.
# Sets the maximum number of pending TCP connections waiting to be accepted by the server.
# Impact:
# Higher values allow the kernel to queue more incoming connections during traffic spikes,
# reducing the chance of refused connections.
ENV AGENT_HTTP_CONNECTIONS_BACKLOG=128

# Sets the maximum idle time (in seconds) before Tornado closes a keep-alive connection.
# Impact:
# Shorter timeouts free up resources faster under high load.
# Longer timeouts reduce reconnections for clients that make periodic requests.
ENV AGENT_HTTP_IDLE_CONNECTIONS_TIMEOUT=3600

# Forks multiple worker processes, each with its own Tornado event loop, all sharing the same listening socket.
# Impact:
# Allows utilization of multiple CPU cores.
# Improves concurrency without blocking a single IOLoop.
# Typical Usage:
# start(0) → Automatically spawns one process per CPU core.
# start(N) → Manually specifies number of worker processes.
ENV AGENT_HTTP_SERVER_INSTANCES=1

# If set to a value>0, will start periodic logging of currently used
# run-time server resources:
# open file descriptors;
# open connections for server port.
# Logging period is specified in seconds.
ENV AGENT_HTTP_RESOURCES_MONITOR_INTERVAL=0

# If this value is specified and >0,
# it will enable dynamic temporary network updates of the server agents
# allowing CodedTools to reserve temporary networks via the Reservationist
# interface, if the agent network hocon file specifically allows it for the tool.
# Update will be done every AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS seconds;
# if value is not specified or <= 0, no such dynamic updates will be executed.
# This particular sample deployment turns this on to 5 seconds to be able to show off the feature
# in a multi-user environment, however most Neuro SAN deployments will want this set to 0
# to disable the feature for safety.
ENV AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS=5

# Optional URL describing how the server is to be referenced by the outside world.
# This is useful when a server is behind a load-balancer as part of a larger cluster.
ENV AGENT_EXTERNAL_SERVER_URL=""

# A reference to a Python class that can be used to store temporary agent references
# External to the server, so other replicated pods can pick them up.
# This class must have a no-args constructor and implement the
# neuro_san.internals.interfaces.ReservationsStorage interface.
# When not set, this defaults to a null implementation.
# A simple default implementation is provided by the class
# "neuro_san.service.watcher.temp_networks.s3_reservations_storage.S3ReservationsStorage"
ENV AGENT_EXTERNAL_RESERVATIONS_STORAGE=""

# When the AGENT_EXTERNAL_RESERVATIONS_STORAGE (immediately above) is set to the
# S3ReservationsStorage class mentioned there, this env var must be set to the S3 Bucket
# to use for cross-pod reservations storage.
ENV AGENT_RESERVATIONS_S3_BUCKET=""

# A hocon file with MCP servers information to be used by LangChainMcpAdapter
# for connecting to external MCP servers with authentication and tool filtering.
ENV MCP_SERVERS_INFO_FILE=""

# When set, this parameter enables MCP service protocol for running neuro-san server.
# Service endpoint is http://host:port/mcp
# (neuro-san own http API is also enabled in this case)
ENV AGENT_MCP_ENABLE="true"

# When set, this parameter will only enable MCP service protocol for running neuro-san server,
# while disabling neuro-san own http API.
ENV AGENT_MCP_ONLY="false"

#
# Authorization
#

# What class neuro-san server should use for authorization
# When not set (the default) the server uses an implementation for the Authorizer
# that effectively lets all requests for all users through.
# We offer the following implementations:
#   neuro_san.internals.authorization.null.always_yes_authorizer.AlwaysYesAuthorizer (default)
#   neuro_san.internals.authorization.null.always_no_authorizer.AlwaysNoAuthorizer
#   neuro_san.internals.authorization.openfga.open_fga_authorizer.OpenFgaAuthorizer
# Feel free to make your own as long as it derives from this interface:
#   neuro_san.internals.authorization.interfaces.authorizer.Authorizer
ENV AGENT_AUTHORIZER=""

# The request metadata field to use as the actor id for authorization
ENV AGENT_AUTHORIZER_ACTOR_ID_METADATA_KEY=user_id

# See authorization logging.
# In production you would not want to set this at all.
# For debugging you might want to set this to "true".
ENV AGENT_DEBUG_AUTH=""

# The Actor type sent to the Authorizer
# This typically corresponds to a specific type set up in the authorization policy
ENV AGENT_AUTHORIZER_ACTOR_KEY=User

# The Resource type sent to the Authorizer
# This typically corresponds to a specific type set up in the authorization policy
ENV AGENT_AUTHORIZER_RESOURCE_KEY=AgentNetwork

# The Relation type sent to the Authorizer used to judge whether the Actor has permission to access the Resource.
# This typically corresponds to a specific relation set up in the authorization policy
# Typically "read" from CRUD-based permissions.
ENV AGENT_AUTHORIZER_ALLOW_RELATION=read

# Below: Env vars specific to OpenFgaAuthorizer

# Where the OpenFGA HTTP server is running for the OpenFgaAuthorizer
# Typical development example might be "http://localhost:8082"
ENV FGA_API_URL=

# The file containing the authorization policy for the OpenFgaAuthorizer
# This is a path to a json file that has been compiled from a .fga policy file using the fga CLI tool.
ENV FGA_POLICY_FILE=

# The name of the authorization store to use
# Typically "default"
ENV FGA_STORE_NAME=

ENTRYPOINT "${APP_ENTRYPOINT}"
