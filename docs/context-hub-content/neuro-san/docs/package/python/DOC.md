---
name: package
description: "Neuro-SAN Python package guide for building data-driven multi-agent networks with HOCON configuration, coded tools, and multi-provider LLM support"
metadata:
  languages: "python"
  versions: "0.6.52"
  revision: 2
  updated-on: "2026-05-18"
  source: maintainer
  tags: "neuro-san,agents,multi-agent,llm,langchain,langgraph,hocon,orchestration,python,mcp,langfuse"
---

# Neuro-SAN Python Package Guide

## What It Is

`neuro-san` (Neuro AI System of Agent Networks) is a data-driven multi-agent orchestration framework. Agent networks are defined entirely in HOCON configuration files — no Python code required for pure LLM agent networks. Custom logic is added through CodedTool Python classes when deterministic behavior is needed.

Use it when you need:

- Multiple LLM-backed agents collaborating on complex problems
- Data-driven agent configuration that non-programmers can author
- Mixed agent types (LLM agents, coded tools, external services, MCP servers)
- Multi-provider LLM support (OpenAI, Anthropic, Google, AWS Bedrock, NVIDIA, Azure, Ollama)
- A server that exposes agent networks via HTTP REST API and/or MCP protocol
- Observability/tracing feeds (LangSmith, Arize Phoenix, HoneyHive, Langfuse)
- Per-user authorization for agent networks (OpenFGA)

## Installation

```bash
pip install neuro-san==0.6.52
```

Python 3.10+ is required (the quick-start scripts assume 3.12+).

From source:

```bash
git clone https://github.com/cognizant-ai-lab/neuro-san.git
cd neuro-san
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=$(pwd)
```

## LLM Setup and Authentication

Set the API key for your chosen LLM provider:

```bash
# OpenAI (default provider)
export OPENAI_API_KEY="your-key"

# Anthropic
export ANTHROPIC_API_KEY="your-key"

# Google Gemini
export GOOGLE_API_KEY="your-key"

# AWS Bedrock
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Azure OpenAI
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="your-endpoint"

# NVIDIA
export NVIDIA_API_KEY="your-key"

# Ollama — no key required
```

The default model is `gpt-4o`. Override per-network or per-agent via `llm_config` in HOCON files.

End-users can also supply their own API keys at request time as `sly_data` (see [Client-Provided API Keys](#client-provided-api-keys)).

## Quick Start

### Using Quick Start Scripts

Terminal 1 — start server:

```bash
./quick-start/start-server.sh
```

Terminal 2 — run client:

```bash
./quick-start/start-client.sh hello_world
```

### Using Python Modules

Terminal 1 — start server:

```bash
python -m neuro_san.service.main_loop.server_main_loop
```

Terminal 2 — CLI client:

```bash
python -m neuro_san.client.agent_cli --http --agent hello_world
```

### Library Mode (No Server)

```bash
python -m neuro_san.client.agent_cli --agent hello_world
```

## Core Concept: Agent Networks in HOCON

Agent networks are defined in `.hocon` files. HOCON is JSON with comments and syntactic sugar. Each file defines a network of agents that can call each other.

Minimal two-agent network:

```hocon
{
    "llm_config": {
        "model_name": "gpt-4o"
    },
    "tools": [
        {
            "name": "announcer",
            "function": {
                "description": "I can help make terse announcements."
            },
            "instructions": "You write the shortest possible announcements.",
            "tools": ["synonymizer"]
        },
        {
            "name": "synonymizer",
            "function": {
                "description": "Returns sequences of synonyms.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input_string": {
                            "type": "string",
                            "description": "Words to find synonyms for"
                        }
                    },
                    "required": ["input_string"]
                }
            },
            "instructions": "You are a thesaurus. Find synonyms for each word."
        }
    ]
}
```

Key rules:

- The **first** agent in `tools` is the **Front Man** — the entry point that talks to clients.
- The Front Man has no `parameters` in its `function` definition.
- Other agents (Branch Agents) are called by name via the `tools` list.
- Agents form a graph (trees, DAGs, or cycles are all valid).

## Agent Types

| Type | Defined By | Purpose |
|------|-----------|---------|
| **Front Man** | First in `tools`, no `parameters` | Entry point, talks to client |
| **Branch Agent** | Has `parameters` in `function` | LLM-powered sub-agent |
| **Coded Tool** | Has `class` key | Python implementation for deterministic logic |
| **Toolbox Tool** | Has `toolbox` key | Pre-built LangChain or coded tool (cannot have a `tools` field) |
| **External Agent** | Tool name starts with `/` or URL | Agent on same or remote server |
| **MCP Server** | URL starts with `https://mcp` or ends with `/mcp` | MCP protocol tools |

## Using the Python API

### Library Mode (DirectAgentSession)

```python
from neuro_san.session.direct_agent_session import DirectAgentSession

session = DirectAgentSession(agent_name="hello_world")

# Get agent capabilities
func = session.function({})
print(func["function"]["description"])

# Chat with streaming responses
responses = session.streaming_chat({
    "user_message": {"text": "Greet a new planet"},
    "chat_context": {},
    "sly_data": {}
})

for response in responses:
    msg = response.get("response", {})
    text = msg.get("text", "")
    if text:
        print(text)
```

### HTTP Client Mode

```python
from neuro_san.session.http_service_agent_session import HttpServiceAgentSession

session = HttpServiceAgentSession(
    agent_name="hello_world",
    host="localhost",
    port=8080
)

responses = session.streaming_chat({
    "user_message": {"text": "Greet a new planet"},
    "chat_context": {},
    "sly_data": {}
})

for response in responses:
    msg = response.get("response", {})
    text = msg.get("text", "")
    if text:
        print(text)
```

### Async Versions

```python
from neuro_san.session.async_direct_agent_session import AsyncDirectAgentSession
from neuro_san.session.async_http_service_agent_session import AsyncHttpServiceAgentSession

# Same API but with async/await
session = AsyncDirectAgentSession(agent_name="hello_world")
async for response in session.streaming_chat(request_dict):
    print(response)
```

## REST API

When running the server, these endpoints are available:

```
GET  /api/v1/{agent_name}/function         # Get agent description and capabilities
POST /api/v1/{agent_name}/streaming_chat    # Chat with an agent
GET  /api/v1/list                           # List all available agents
GET  /health                                # Server health check
GET  /api/v1/docs                           # OpenAPI specification
```

Chat request body:

```json
{
    "user_message": {"text": "Your question here"},
    "chat_context": {},
    "sly_data": {"private_key": "private_value"}
}
```

cURL example:

```bash
curl -X POST http://localhost:8080/api/v1/hello_world/streaming_chat \
  -H "Content-Type: application/json" \
  -d '{"user_message": {"text": "Greet a new planet"}}'
```

## Writing a Coded Tool

When you need deterministic logic (API calls, database operations, calculations), implement a `CodedTool`:

```python
from typing import Any, Dict
from neuro_san.interfaces.coded_tool import CodedTool

class Calculator(CodedTool):

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        operation = args.get("operation", "add")
        a = args.get("a", 0)
        b = args.get("b", 0)

        if operation == "add":
            return str(a + b)
        elif operation == "multiply":
            return str(a * b)
        else:
            return f"Unknown operation: {operation}"
```

Reference it in your HOCON file:

```hocon
{
    "name": "calculator",
    "function": {
        "description": "Performs arithmetic operations.",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "description": "add or multiply"},
                "a": {"type": "float", "description": "First number"},
                "b": {"type": "float", "description": "Second number"}
            },
            "required": ["operation", "a", "b"]
        }
    },
    "class": "calculator.Calculator"
}
```

Place the Python file under `AGENT_TOOL_PATH` (default: `coded_tools/<agent_name>/`).

## Sly Data (Private Data Channel)

Sly data is a dictionary of private information kept out of LLM chat streams. Use it for credentials, API keys, personal data, or inter-agent communication that should not be visible to LLMs.

```python
# Client passes sly_data
responses = session.streaming_chat({
    "user_message": {"text": "Look up my account"},
    "sly_data": {"user_token": "abc123", "api_key": "secret"}
})
```

Inside a CodedTool, sly_data is accessible:

```python
async def async_invoke(self, args, sly_data):
    token = sly_data.get("user_token")
    # Use token for authenticated API call
    # Can also add new keys for downstream agents:
    sly_data["lookup_result_id"] = "xyz789"
    return "Account found"
```

Control sly_data flow to/from external agents via `allow` policies in HOCON. By default, **no sly_data crosses network boundaries** — you must explicitly enable each key.

```hocon
"allow": {
    "connectivity": true,
    "to_downstream": {
        "sly_data": {"user_token": true, "api_key": false}
    },
    "from_downstream": {
        "sly_data": {"result_id": true},
        "messages": true
    },
    "to_upstream": {
        "sly_data": ["result_id"]
    }
}
```

A Front Man can advertise the schema of sly_data it expects (input) and produces (output) via `function.sly_data_schema` and `function.sly_data_output_schema`. Generic clients use these to prompt users for required private inputs.

### Client-Provided API Keys

End-users can supply their own LLM API keys at request time by putting an `llm_config` dictionary inside `sly_data`:

```python
responses = session.streaming_chat({
    "user_message": {"text": "Hello"},
    "sly_data": {
        "llm_config": {
            "openai_api_key": "sk-...",
            "anthropic_api_key": "..."
        }
    }
})
```

Key names are the lowercase form of the environment variable names (e.g. `OPENAI_API_KEY` → `openai_api_key`). The network's HOCON should advertise this requirement in its `sly_data_schema`. See the [`music_nerd_pro_sly_api_key.hocon`](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/registries/music_nerd_pro_sly_api_key.hocon) example.

### MCP Authentication via Sly Data

Per-server MCP authentication headers can also be passed in `sly_data`:

```python
"sly_data": {
    "http_headers": {
        "https://example.com/mcp": {"Authorization": "Bearer <token>"},
        "https://other.com/mcp":   {"client_id": "...", "client_secret": "..."}
    }
}
```

Or define them server-side via the `MCP_SERVERS_INFO_FILE` environment variable pointing at a HOCON file of per-URL `http_headers` and tool filters.

## LLM Configuration

### Default LLM for All Agents

```hocon
{
    "llm_config": {
        "model_name": "gpt-4o",
        "temperature": 0.7
    },
    "tools": [...]
}
```

### Per-Agent LLM Override

```hocon
{
    "name": "budget_agent",
    "llm_config": {
        "model_name": "gpt-4o-mini",
        "temperature": 0.3
    },
    "function": {...},
    "instructions": "..."
}
```

### Using Anthropic Models

```hocon
"llm_config": {
    "model_name": "claude-sonnet"
}
```

Aliases `claude-haiku`, `claude-sonnet`, `claude-opus` auto-resolve to latest versions.

### Fallback LLMs

```hocon
"llm_config": {
    "model_name": "gpt-4o",
    "fallbacks": [
        {"model_name": "claude-sonnet"},
        {"model_name": "gpt-4o-mini"}
    ]
}
```

### Custom LLM Provider

```hocon
"llm_config": {
    "class": "langchain_nvidia_ai_endpoints.chat_models.ChatNVIDIA",
    "model_name": "meta/llama-3.1-405b-instruct"
}
```

## External Agents and Composability

Agent networks can call agents in other networks, enabling composition:

```hocon
"tools": [
    "local_agent",                        // Agent in same network
    "/date_time",                         // External agent on same server
    "http://other-server:8080/math_guy",  // Agent on remote server
    "https://example.com/mcp"             // MCP server tools
]
```

Expose agents as MCP tools with `AGENT_MCP_ENABLE=true` and `"mcp": true` in manifest.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `GOOGLE_API_KEY` | — | Google Gemini API key |
| `NVIDIA_API_KEY` | — | NVIDIA API key |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | — | Amazon Bedrock credentials |
| `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT` | — | Azure OpenAI credentials |
| `AGENT_MANIFEST_FILE` | `neuro_san/registries/manifest.hocon` | Path to agent manifest |
| `AGENT_TOOL_PATH` | `<repo>/coded_tools` | Path to coded tool implementations |
| `AGENT_LLM_INFO_FILE` | — | Custom LLM definitions file |
| `AGENT_TOOLBOX_INFO_FILE` | — | Custom toolbox definitions file |
| `AGENT_HTTP_PORT` | `8080` | HTTP server port |
| `AGENT_MCP_ENABLE` | `true` | Expose MCP protocol alongside REST |
| `AGENT_MCP_ONLY` | `false` | Disable REST and serve only MCP |
| `AGENT_MANIFEST_UPDATE_PERIOD_SECONDS` | `0` | Manifest/network hot-reload interval (0 = disabled) |
| `AGENT_AUTHORIZER` | — | Per-user authorization plugin (e.g. OpenFGA) |
| `MCP_SERVERS_INFO_FILE` | — | HOCON file with per-MCP-URL auth headers and tool filters |
| `LANGFUSE_ENABLED` | `false` | Enable Langfuse tracing |

## Common Pitfalls

- Do not assume the default model works for tool-calling. Some models lack tool-use capability. Check `default_llm_info.hocon` for the `capabilities` section.
- Do not put secrets in HOCON files. Use environment variables for API keys and credentials.
- Do not forget that the first agent in `tools` is always the Front Man. It cannot be a CodedTool or Toolbox tool.
- Do not confuse agent-level `tools` (list of callable agents) with the top-level `tools` (list of agent definitions).
- Do not use synchronous `invoke()` in production CodedTools. Use `async_invoke()` to avoid blocking the event loop.
- Do not forget `parameters` on branch agents. Without them, the calling LLM cannot pass arguments.
- Do not pass sly_data keys to external agents without explicit `allow` configuration. By default, no sly_data crosses network boundaries.
- Do not use `max_iterations` in new configurations. It is deprecated — use `max_steps` (LangGraph recursion limit, default `10000`).
- Do not put a `tools` field on an agent that uses `toolbox`. Toolbox agents execute code directly and cannot call sub-agents.

## Version-Sensitive Notes for 0.6.52

- `0.6.52` is the current release, tagged on 2026-05-15.
- Requires Python >=3.10. Quick-start scripts assume Python 3.12+.
- Built on LangChain + LangGraph for LLM orchestration, but abstracts both away from agent authors.
- The default LLM model is `gpt-4o` when no `llm_config` is specified.
- Anthropic model aliases (`claude-haiku`, `claude-sonnet`, `claude-opus`) auto-resolve to latest versions to avoid deprecation issues.
- **`max_iterations` is deprecated**; use `max_steps` instead. `max_steps` corresponds to the LangGraph recursion-limit (super-step budget) and defaults to **10,000** — much higher than the old `max_iterations` default of 20.
- Toolbox agents (those with a `toolbox` key) **cannot** declare a `tools` field — they execute directly rather than calling an LLM.
- Front Man agents can declare both `sly_data_schema` (expected inputs) and `sly_data_output_schema` (produced outputs).
- MCP protocol is enabled by default (`AGENT_MCP_ENABLE=true`). Authentication headers may come from `sly_data["http_headers"]` or the `MCP_SERVERS_INFO_FILE` HOCON file.
- Langfuse tracing is available when `LANGFUSE_ENABLED=true`; `user_id` and `session_id` are propagated as Langfuse attributes.
- Periodic events: networks can register cron-style schedules to trigger themselves without a client request.
- LangChain-style **AgentMiddleware** classes can be attached to any LLM agent via the `middleware` HOCON key for cross-cutting concerns (logging, PII redaction, summarization, etc.).

## Official Source URLs

- GitHub: https://github.com/cognizant-ai-lab/neuro-san
- PyPI: https://pypi.org/project/neuro-san/
- Agent HOCON Reference: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md
- LLM Info Reference: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/llm_info_hocon_reference.md
- Manifest Reference: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/manifest_hocon_reference.md
- Toolbox Reference: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/toolbox_info_hocon_reference.md
- Test Case Reference: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md
- MCP Service Docs: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/mcp_service.md
- Client Docs: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/clients.md
- HOCON Validator CLI: https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/hocon_validator_cli.md
- neuro-san-studio (examples & tutorials): https://github.com/cognizant-ai-lab/neuro-san-studio
