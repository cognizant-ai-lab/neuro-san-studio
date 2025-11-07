# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san SDK Software in commercial settings.
#
# END COPYRIGHT

# Use ./deploy/build.sh to build this container. After a successful build,
# you can use ./deploy/run.sh to run the built container locally.
#
# To find server-oriented environment variables to help you configure things
# how you want, search for "ENV AGENT_" in this file.

# Stage 1: Set python image as base image
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
RUN pip3 install --upgrade pip==${PIP3_VERSION} --no-cache-dir

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

# This is the port the service will accept grpc requests on.
# This should be consistent with the main port for the service as described
# in the <service>.yaml file for any kubernetes deployment.
# This default port number is also mentioned as AGENT_PORT below
# and ServiceAgentSession.DEFAULT_PORT
# In order to be self-discovered by supporting build/run scripts this must
# be the first port exposed in the Dockerfile.
EXPOSE 30011

# This is the port the service will accept http requests on.
# This should be consistent with the main port for the service as described
# in the <service>.yaml file for any kubernetes deployment.
# This default port number is also mentioned as AGENT_HTTP_PORT below
# and ServiceAgentSession.DEFAULT_HTTP_PORT
EXPOSE 8080

# Copy installed dependencies from the builder stage
COPY --from=builder /install /usr/local

# Copy application code and necessary files
# Note: The registries directory where agent definitions live is mandatory
#       The coded_tools directory where agent code lives is optional
COPY ./registries ${APP_SOURCE}/registries
COPY ./coded_tool[s] ${APP_SOURCE}/coded_tools
COPY ./deploy/entrypoint.sh ${APP_SOURCE}/deploy/entrypoint.sh
COPY ./deploy/logging.json ${APP_SOURCE}/deploy/logging.json

# Set up the entry point for when the container is run
USER ${USERNAME}
WORKDIR ${APP_SOURCE}

# RUN echo "$(pip show neuro-san | grep Location | awk '{print $2}')"
# This value below comes from the above RUN command. Cannot set ENV vars in Dockerfiles based on shell output.
ENV PACKAGE_INSTALL=/usr/local/lib/python3.13/site-packages
ENV APP_ENTRYPOINT=${APP_SOURCE}/deploy/entrypoint.sh

#
# Server configuration
#

# Point to the root folder of the app
ENV PYTHONPATH=${APP_SOURCE}

# Where to find the tool registry manifest file which lists all the agent hocon
# files to serve up from this server instance.
ENV AGENT_MANIFEST_FILE=${APP_SOURCE}/registries/manifest_deploy.hocon

# An llm_info hocon file with user-provided llm descriptions that are to be used
# in addition to the neuro-san defaults.
ENV AGENT_LLM_INFO_FILE=""

# Where to find the classes for CodedTool class implementations
# that are used by specific agent networks.
ENV AGENT_TOOL_PATH=${APP_SOURCE}/coded_tools

# Where to find the configuration file for Python logging.
# See https://docs.python.org/3/library/logging.config.html#dictionary-schema-details
# as to how this file can be configured for your own needs.  Examples there are provided in YAML,
# but these can be easily translated to JSON (which we prefer).
ENV AGENT_SERVICE_LOG_JSON=${APP_SOURCE}/deploy/logging.json

# Threshold for logging.
# See https://docs.python.org/3/library/logging.html#logging.Handler.setLevel
# and https://docs.python.org/3/library/logging.html#logging-levels for details.
ENV AGENT_SERVICE_LOG_LEVEL="DEBUG"

# The name of the service for grpc health reporting purposes
ENV AGENT_SERVER_NAME="neuro-san.Agent"

# Name of the service as seen in logs
ENV AGENT_SERVER_NAME_FOR_LOGS="Agent Server"

# A space-delimited list of http metadata request keys to forward to logs/other requests
# You can see how these are used in the AGENT_SERVICE_LOG_JSON file (see above) and
# customize this and the AGENT_SERVER_LOG_JSON file to your needs.
# Note that any metadata key needs to be all lowercase.
ENV AGENT_FORWARDED_REQUEST_METADATA="request_id user_id"

# Port number for the grpc service endpoint
# If you are changing this, you should also change the first EXPOSE port above
# and when running your container locally be sure to have a -p <port>:<port> entry
# for it on your docker run command line.
ENV AGENT_PORT=30011

# Port number for http service endpoint
# If you are changing this, you should also change the second EXPOSE port above
# and when running your container locally be sure to have a -p <port>:<port> entry
# for it on your docker run command line.
ENV AGENT_HTTP_PORT=8080

# Maximm number of requests that can be served at the same time
ENV AGENT_MAX_CONCURRENT_REQUESTS=10

# Number of requests served before the server shuts down in an orderly fashion.
# This is useful for testing response handling in clusters with duplicated pods.
ENV AGENT_REQUEST_LIMIT=1000000

# ENTRYPOINT ls ${APP_SOURCE}
ENTRYPOINT "${APP_ENTRYPOINT}"
