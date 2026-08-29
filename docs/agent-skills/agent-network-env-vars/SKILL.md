---
name: agent-network-env-vars
description: Look up a neuro-san server environment variable — manifest/tool/LLM/toolbox file paths, HTTP port,
  MCP toggles, hot-reload interval, authorization. Use when asked what an AGENT_* or MCP_* env var does, or how
  to point the server at a custom manifest/tool/LLM/toolbox file.
---

# neuro-san server environment variables

Verified against the installed `neuro-san` package source (`server_main_loop.py`, `activation_factory.py`,
`default_llm_factory.py`, `toolbox_factory.py`, `authorizer_factory.py`, `mcp_servers_info_restorer.py`,
`agent_authorization_policy.py`) — defaults below are code-level, not just docs.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_MANIFEST_FILE` | `neuro_san/registries/manifest.hocon` (this repo's `make`/`ns` targets set `registries/manifest.hocon`) | Path to the manifest that lists which networks to serve. |
| `AGENT_TOOL_PATH` | `<repo>/coded_tools` (this repo uses `coded_tools/`) | Root dir coded tools are resolved from — see `agent-network-tool-integration` skill. |
| `AGENT_LLM_INFO_FILE` | unset (falls back to the built-in `default_llm_info.hocon`) | Custom/extra LLM model definitions — see `agent-network-llm-config` skill. |
| `AGENT_TOOLBOX_INFO_FILE` | unset (falls back to the built-in `toolbox_info.hocon`) | Custom/extra toolbox tool definitions — see `agent-network-tool-integration` skill. |
| `AGENT_HTTP_PORT` (`AGENT_PORT` as a legacy fallback) | `8080` | HTTP server port for `ns run`. |
| `AGENT_SERVER_NAME` | `neuro-san.Agent` | Service name reported in health checks. |
| `AGENT_SERVER_NAME_FOR_LOGS` | `Agent Server` | Service name as it appears in logs. |
| `AGENT_MAX_CONCURRENT_REQUESTS` | `0` (unlimited) | Max requests served at the same time. |
| `AGENT_REQUEST_LIMIT` | `1000000` | Requests served before the server shuts down in an orderly fashion. |
| `AGENT_FORWARDED_REQUEST_METADATA` | `"request_id user_id"` | Space-delimited request metadata keys forwarded to logs/downstream requests. |
| `AGENT_OPENAPI_SPEC` | auto-derived path | File path to the OpenAPI service spec document. |
| `AGENT_MANIFEST_UPDATE_PERIOD_SECONDS` | `0` (disabled) | Seconds between manifest/network hot-reloads; `0` means no polling. |
| `AGENT_HTTP_CONNECTIONS_BACKLOG` | `128` | TCP connection backlog size for the HTTP server. |
| `AGENT_HTTP_IDLE_CONNECTIONS_TIMEOUT` | `3600` | Seconds before an idle-but-alive HTTP connection is closed. |
| `AGENT_HTTP_SERVER_INSTANCES` | `1` | Number of HTTP server instances (one process each) to fork. |
| `AGENT_HTTP_RESOURCES_MONITOR_INTERVAL` | `0` (disabled) | Seconds between resource-usage log lines; `0` disables logging. |
| `AGENT_STREAM_KEEP_ALIVE_WITH_PROGRESS_INTERVAL_SECONDS` | `0` (disabled) | Heartbeat interval, in seconds, for streaming responses. |
| `AGENT_MAX_TEMP_NETWORKS` | `0` (unlimited) | Cap on temporary/reservation-mode networks (see `agent-network-designer` skill's `AGENT_NETWORK_DESIGNER_USE_RESERVATIONS`). |
| `AGENT_MCP_ENABLE` | `true` | Exposes MCP protocol alongside REST. |
| `AGENT_MCP_ONLY` | `false` | Set `true` to disable REST and serve only MCP. |
| `MCP_SERVERS_INFO_FILE` | unset | HOCON file of per-MCP-URL auth headers and tool filters — see `agent-network-tool-integration` skill. |
| `AGENT_AUTHORIZER` | unset (no authorization) | Fully-qualified class name of an `Authorizer` implementation (e.g. OpenFGA) — see `agent-network-middleware` skill. |
| `AGENT_AUTHORIZER_ACTOR_KEY` | `User` | Key naming the actor type in authorization checks. |
| `AGENT_AUTHORIZER_ACTOR_ID_METADATA_KEY` | `user_id` | `sly_data`/metadata key the authorizer reads the actor's ID from. |
| `AGENT_AUTHORIZER_RESOURCE_KEY` | `AgentNetwork` | Resource-type name used in authorization checks. |
| `AGENT_AUTHORIZER_ALLOW_RELATION` | `read` | Relation name checked to allow access. |
| `LANGFUSE_ENABLED` | `false` | Enables the Langfuse observability plugin — see `agent-network-middleware` skill. |
| `AGENT_SERVICE_LOG_JSON` | unset | Path to a logging HOCON for verbose coded-tool logging — see `agent-network-cli` skill. |

This repo's own defaults for `AGENT_TOOL_PATH`/`AGENT_MANIFEST_FILE` (`coded_tools/`, `registries/manifest.hocon`)
come from [Makefile](../../../Makefile) targets and `ns` itself, not the neuro-san package default —
[CONTRIBUTING.md](../../../CONTRIBUTING.md)'s test setup points them at `tests/coded_tools/` /
`tests/registries/manifest.hocon` instead.

Full reference: [manifest_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/manifest_hocon_reference.md).
