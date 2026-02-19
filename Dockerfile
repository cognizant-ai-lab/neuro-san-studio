# =============================================================================
# Dockerfile for Neuro SAN Studio — Azure Container Apps deployment
# =============================================================================
# Build:
#   docker build -t neuro-san-studio:latest .
#
# Run locally:
#   docker run --rm -p 4173:4173 -p 8080:8080 -p 30011:30011 \
#     -e OPENAI_API_KEY="sk-..." \
#     neuro-san-studio:latest
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — install Python dependencies into a prefix directory
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /build

# Upgrade pip first (layer cached until pip version changes)
ARG PIP_VERSION=25.0.1
RUN pip install --no-cache-dir --upgrade "pip==${PIP_VERSION}"

# Copy only the requirements file first for layer caching
COPY requirements.txt .

# Install runtime dependencies into an isolated prefix so we can COPY them
# into the final image without dragging in build tools.
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Final — minimal runtime image
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS final

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# ---- Create non-root user ----
ENV USERNAME=neuro-san
ENV APP_HOME=/usr/local/${USERNAME}
ENV APP_SOURCE=${APP_HOME}/app

RUN useradd --create-home --shell /bin/bash --home-dir "${APP_HOME}" --uid 1001 "${USERNAME}" \
    && mkdir -p "${APP_SOURCE}" \
    && chown -R "${USERNAME}:${USERNAME}" "${APP_HOME}"

# ---- Copy installed Python packages from builder ----
COPY --from=builder /install /usr/local

# ---- Copy application code ----
# Order: least-frequently-changed first for layer caching.

# Config files used by the server at runtime
COPY --chown=${USERNAME}:${USERNAME} ./deploy/entrypoint.sh         ${APP_SOURCE}/deploy/entrypoint.sh
COPY --chown=${USERNAME}:${USERNAME} ./deploy/nsflow_start.py       ${APP_SOURCE}/deploy/nsflow_start.py
COPY --chown=${USERNAME}:${USERNAME} ./deploy/config_editor_start.py ${APP_SOURCE}/deploy/config_editor_start.py
COPY --chown=${USERNAME}:${USERNAME} ./deploy/combined_start.py      ${APP_SOURCE}/deploy/combined_start.py
COPY --chown=${USERNAME}:${USERNAME} ./deploy/logging.json          ${APP_SOURCE}/deploy/logging.json
COPY --chown=${USERNAME}:${USERNAME} ./logging.json                  ${APP_SOURCE}/logging.json

# MCP and toolbox configs
COPY --chown=${USERNAME}:${USERNAME} ./mcp         ${APP_SOURCE}/mcp
COPY --chown=${USERNAME}:${USERNAME} ./toolbox      ${APP_SOURCE}/toolbox

# Server wrapper module
COPY --chown=${USERNAME}:${USERNAME} ./servers      ${APP_SOURCE}/servers

# Plugins (log_bridge, phoenix)
COPY --chown=${USERNAME}:${USERNAME} ./plugins      ${APP_SOURCE}/plugins

# Agent registries — seed copy (live registries will be Azure File Share mount)
COPY --chown=${USERNAME}:${USERNAME} ./registries   ${APP_SOURCE}/registries-seed
RUN mkdir -p ${APP_SOURCE}/registries && chown ${USERNAME}:${USERNAME} ${APP_SOURCE}/registries

# Coded tools (custom Python tool implementations)
COPY --chown=${USERNAME}:${USERNAME} ./coded_tools  ${APP_SOURCE}/coded_tools

# Config editor (web UI for HOCON management)
COPY --chown=${USERNAME}:${USERNAME} ./config_editor ${APP_SOURCE}/config_editor

# Main runner script (used by run.py-based launches; not the primary entrypoint)
COPY --chown=${USERNAME}:${USERNAME} ./run.py       ${APP_SOURCE}/run.py

# Make the entrypoint script executable
RUN chmod +x "${APP_SOURCE}/deploy/entrypoint.sh"

# ---- Ports ----
# gRPC port (used by neuro-san inter-agent communication)
EXPOSE 30011
# HTTP port (neuro-san API — internal, nsflow connects to it on localhost)
EXPOSE 8080
# nsflow web UI port (Azure Container Apps ingress targets this)
EXPOSE 4173
# Config editor port (legacy — editor is now served at /editor on port 4173)
EXPOSE 4174

# ---- Switch to non-root user ----
USER ${USERNAME}
WORKDIR ${APP_SOURCE}

# ---- Environment variables ----
# Python / app paths
ENV PYTHONPATH=${APP_SOURCE}
ENV PACKAGE_INSTALL=/usr/local/lib/python3.13/site-packages

# Server identity
ENV AGENT_SERVER_NAME="neuro-san-studio.Agent"
ENV AGENT_SERVER_NAME_FOR_LOGS="Agent Server"

# Manifest and tool paths (relative to APP_SOURCE set above)
ENV AGENT_MANIFEST_FILE="${APP_SOURCE}/registries/manifest.hocon ${APP_SOURCE}/registries/manifest_multiuser_overlay.hocon"
ENV AGENT_TOOL_PATH="${APP_SOURCE}/coded_tools"
ENV AGENT_TOOLBOX_INFO_FILE="${APP_SOURCE}/toolbox/toolbox_info.hocon"
ENV AGENT_LLM_INFO_FILE=""
ENV MCP_SERVERS_INFO_FILE="${APP_SOURCE}/mcp/mcp_info.hocon"

# Logging
ENV AGENT_SERVICE_LOG_JSON="${APP_SOURCE}/deploy/logging.json"
ENV AGENT_SERVICE_LOG_LEVEL="INFO"

# HTTP server configuration
ENV AGENT_HTTP_PORT=8080
ENV AGENT_MAX_CONCURRENT_REQUESTS=50
ENV AGENT_REQUEST_LIMIT=1000000
ENV AGENT_HTTP_CONNECTIONS_BACKLOG=128
ENV AGENT_HTTP_IDLE_CONNECTIONS_TIMEOUT=3600
ENV AGENT_HTTP_SERVER_INSTANCES=1
ENV AGENT_HTTP_RESOURCES_MONITOR_INTERVAL=0

# Agent manifest dynamic reload (30s polling; picks up HOCON changes without restart)
ENV AGENT_MANIFEST_UPDATE_PERIOD_SECONDS=30

# Temporary network reservations (0 = disabled; set >0 for multi-user)
ENV AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS=5

# Metadata forwarding
ENV AGENT_FORWARDED_REQUEST_METADATA="request_id user_id"
ENV AGENT_TRACING_METADATA_REQUEST_KEYS=""
ENV AGENT_TRACING_METADATA_ENV_VARS="POD_NAME POD_NAMESPACE POD_IP NODE_NAME"
ENV AGENT_VERSION_LIBS=""
ENV AGENT_USAGE_LOGGER=""
ENV AGENT_USAGE_LOGGER_METADATA=""

# External server URL (set when behind a load balancer)
ENV AGENT_EXTERNAL_SERVER_URL=""
ENV AGENT_EXTERNAL_RESERVATIONS_STORAGE=""
ENV AGENT_RESERVATIONS_S3_BUCKET=""

# MCP protocol support
ENV AGENT_MCP_ENABLE="true"
ENV AGENT_MCP_ONLY="false"

# Phoenix / observability (disabled by default; enable via Azure env config)
ENV PHOENIX_ENABLED="false"
ENV PHOENIX_AUTOSTART="false"

# ---- Process toggle flags ----
# Set to "false" to disable a process (for single-purpose container apps)
ENV NEURO_SAN_ENABLED="true"
ENV NSFLOW_ENABLED="true"

# ---- nsflow web UI configuration ----
ENV NSFLOW_HOST=0.0.0.0
ENV NSFLOW_PORT=4173
ENV NSFLOW_PLUGIN_CRUSE="false"
ENV VITE_API_PROTOCOL=http
ENV VITE_WS_PROTOCOL=ws
ENV NEURO_SAN_SERVER_HOST=localhost
ENV NEURO_SAN_SERVER_HTTP_PORT=8080
ENV NEURO_SAN_SERVER_CONNECTION=http

# ---- Config editor configuration ----
ENV CONFIG_EDITOR_ENABLED="true"
ENV CONFIG_EDITOR_HOST=0.0.0.0
ENV CONFIG_EDITOR_PORT=4174
ENV CONFIG_EDITOR_REGISTRIES_PATH="${APP_SOURCE}/registries"

# ---- Health check ----
# Check nsflow (4173) — the user-facing service and Azure ingress target.
# Both services start in parallel; uvicorn binds within seconds.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1',4173)); s.close()" || exit 1

# ---- Entrypoint ----
# The entrypoint.sh script starts processes based on *_ENABLED flags:
#   1. neuro-san server: gRPC (30011) + HTTP API (8080)            [NEURO_SAN_ENABLED]
#   2. combined app: nsflow + config editor on port 4173           [NSFLOW_ENABLED]
#      Config editor is served at /editor/ (CONFIG_EDITOR_ENABLED controls mount)
ENV APP_ENTRYPOINT=${APP_SOURCE}/deploy/entrypoint.sh
ENTRYPOINT ["/bin/bash", "-c", "${APP_ENTRYPOINT}"]
