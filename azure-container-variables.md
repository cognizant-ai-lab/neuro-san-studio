# Neuro SAN Studio — Azure Container Environment Variables

## nsflow Web UI

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `NSFLOW_HOST` | `0.0.0.0` | No | Bind address for nsflow. Must be `0.0.0.0` in container for Azure ingress to reach it. |
| `NSFLOW_PORT` | `4173` | No | nsflow web UI port. Azure ingress targets this port. |
| `NSFLOW_PLUGIN_CRUSE` | `false` | No | Enable the CRUSE plugin in nsflow UI. |
| `VITE_API_PROTOCOL` | `http` | No | Protocol for nsflow frontend API calls. Set to `https` if using TLS termination. |
| `VITE_WS_PROTOCOL` | `ws` | No | WebSocket protocol for nsflow streaming. Set to `wss` if using TLS termination. |
| `NEURO_SAN_SERVER_HOST` | `localhost` | No | Host where nsflow finds the neuro-san API server (internal to container). |
| `NEURO_SAN_SERVER_HTTP_PORT` | `8080` | No | Port where nsflow connects to the neuro-san API server. |
| `NEURO_SAN_SERVER_CONNECTION` | `http` | No | Connection protocol to neuro-san server. |
| `SERVER_STARTUP_TIMEOUT` | `60` | No | Max seconds the entrypoint waits for neuro-san server before starting nsflow. |

## Neuro-SAN Server — Core

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AGENT_SERVER_NAME` | `neuro-san-studio.Agent` | No | Server identity name. |
| `AGENT_SERVER_NAME_FOR_LOGS` | `Agent Server` | No | Display name in log output. |
| `AGENT_MANIFEST_FILE` | `<APP>/registries/manifest.hocon ...` | No | Space-separated path(s) to agent manifest HOCON files. |
| `AGENT_TOOL_PATH` | `<APP>/coded_tools` | No | Path to custom Python coded tools directory. |
| `AGENT_TOOLBOX_INFO_FILE` | `""` | No | Path to toolbox info HOCON file. |
| `AGENT_LLM_INFO_FILE` | `""` | No | Path to LLM configuration info file. |
| `MCP_SERVERS_INFO_FILE` | `""` | No | Path to MCP servers configuration file. |

## Neuro-SAN Server — HTTP

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AGENT_HTTP_PORT` | `8080` | No | HTTP API port (internal, nsflow connects to this). |
| `AGENT_MAX_CONCURRENT_REQUESTS` | `50` | No | Maximum concurrent HTTP requests the server will handle. |
| `AGENT_REQUEST_LIMIT` | `1000000` | No | Maximum request size limit. |
| `AGENT_HTTP_CONNECTIONS_BACKLOG` | `128` | No | TCP connection backlog size. |
| `AGENT_HTTP_IDLE_CONNECTIONS_TIMEOUT` | `3600` | No | Idle connection timeout in seconds. |
| `AGENT_HTTP_SERVER_INSTANCES` | `1` | No | Number of HTTP server worker instances. |
| `AGENT_HTTP_RESOURCES_MONITOR_INTERVAL` | `0` | No | Resource monitoring interval in seconds (0 = disabled). |

## Neuro-SAN Server — Logging

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AGENT_SERVICE_LOG_JSON` | `<APP>/deploy/logging.json` | No | Path to logging configuration JSON file. |
| `AGENT_SERVICE_LOG_LEVEL` | `INFO` | No | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

## Neuro-SAN Server — Agent Management

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AGENT_MANIFEST_UPDATE_PERIOD_SECONDS` | `0` | No | Interval to reload agent manifest (0 = disabled). |
| `AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS` | `5` | No | Interval for temporary network reservation cleanup. |
| `AGENT_FORWARDED_REQUEST_METADATA` | `request_id user_id` | No | Space-separated metadata keys forwarded between agents. |
| `AGENT_TRACING_METADATA_REQUEST_KEYS` | `""` | No | Additional request metadata keys for tracing. |
| `AGENT_TRACING_METADATA_ENV_VARS` | `POD_NAME POD_NAMESPACE POD_IP NODE_NAME` | No | Environment variables to include in trace metadata. |
| `AGENT_VERSION_LIBS` | `""` | No | Library version tracking configuration. |
| `AGENT_USAGE_LOGGER` | `""` | No | Usage logger class path. |
| `AGENT_USAGE_LOGGER_METADATA` | `""` | No | Metadata for usage logger. |

## Neuro-SAN Server — External / Multi-User

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AGENT_EXTERNAL_SERVER_URL` | `""` | No | Public URL when behind a load balancer. |
| `AGENT_EXTERNAL_RESERVATIONS_STORAGE` | `""` | No | External storage for agent reservations. |
| `AGENT_RESERVATIONS_S3_BUCKET` | `""` | No | S3 bucket name for reservations storage. |

## MCP Protocol

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AGENT_MCP_ENABLE` | `true` | No | Enable MCP (Model Context Protocol) support. |
| `AGENT_MCP_ONLY` | `false` | No | Run in MCP-only mode (disable native protocol). |

## Observability (Phoenix)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `PHOENIX_ENABLED` | `false` | No | Enable Phoenix OpenTelemetry observability. |
| `PHOENIX_AUTOSTART` | `false` | No | Auto-start the Phoenix server inside the container. |

## API Keys (inject at runtime)

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `OPENAI_API_KEY` | *(none)* | **Yes** | OpenAI API key for LLM calls. Never hardcode — inject via Azure env config. |

---

## Azure CLI Commands

### Container App — View current configuration

```bash
# Show container app details
az containerapp show \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG

# Show current ingress configuration
az containerapp ingress show \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG
```

### Container App — Update ingress target port

```bash
# Set ingress to target nsflow on port 4173
az containerapp ingress update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --target-port 4173

# Revert to neuro-san API on port 8080 (if needed)
az containerapp ingress update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --target-port 8080
```

### Container App — Set environment variables

```bash
# Set a single environment variable
az containerapp update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --set-env-vars "OPENAI_API_KEY=secretref:openai-api-key"

# Set multiple environment variables at once
az containerapp update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --set-env-vars \
    "AGENT_SERVICE_LOG_LEVEL=DEBUG" \
    "PHOENIX_ENABLED=true" \
    "NSFLOW_PLUGIN_CRUSE=true"

# Remove an environment variable
az containerapp update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --remove-env-vars "PHOENIX_ENABLED"
```

### Container App — Manage secrets (for API keys)

```bash
# Add a secret
az containerapp secret set \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --secrets "openai-api-key=sk-your-key-here"

# List secrets
az containerapp secret list \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG

# Reference a secret as an environment variable
az containerapp update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --set-env-vars "OPENAI_API_KEY=secretref:openai-api-key"
```

### Container App — View logs

```bash
# Stream live logs
az containerapp logs show \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --follow

# View recent logs (last 100 lines)
az containerapp logs show \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --tail 100
```

### Container App — Restart and scale

```bash
# Restart the container (force new revision)
az containerapp revision restart \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --revision $(az containerapp revision list \
    --name csai-neuro-san-studio \
    --resource-group CSAI-RG \
    --query "[0].name" -o tsv)

# Scale replicas (min 0, max 3)
az containerapp update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --min-replicas 1 \
  --max-replicas 3
```

### ACR — Build and push image manually

```bash
# Build image using ACR Tasks (no local Docker needed)
az acr build \
  --registry csaiadocicd \
  --image csai-neuro-san-studio:latest \
  --file Dockerfile \
  .

# Deploy the latest image
az containerapp update \
  --name csai-neuro-san-studio \
  --resource-group CSAI-RG \
  --image csaiadocicd.azurecr.io/csai-neuro-san-studio:latest
```
