---
name: agent-network-tool-integration
description: Wire a toolbox tool, coded tool, MCP server, or external/other-framework agent into a
  neuro-san-studio network. Use when an agent needs to call an API, run deterministic Python logic, consume MCP
  tools, or delegate to another network.
---

# Toolbox, coded tools, MCP, and external agents

## Toolbox: pre-built tools

Before writing a coded tool, check the **toolbox** — ready-made tools (web search, RAG, code execution,
Gmail/Jira, …). Reference by name; pass settings via `args` (merged over the tool's defaults):

```hocon
{ "name": "policy_web_search", "toolbox": "ddgs_search", "args": { "num_results": 3 } }
```

Available tools: [toolbox_info.hocon](../../../neuro_san_studio/toolbox/toolbox_info.hocon)
Defining/Customizing tools: [toolbox_info_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/toolbox_info_hocon_reference.md).

## Coded tools, sly_data, external APIs

When no toolbox tool fits, implement a `CodedTool` under `coded_tools/<agent_name>/`. No manifest entry — you wire
it as an agent node in the network HOCON (an up-chain agent lists it in `tools`), giving the node a `function`
(`description` + `parameters`) and `"class": "<module>.<ClassName>"` — the `.py` file name, then the class inside
it (snake_case → PascalCase). So `order_lookup.py` with `class OrderLookup` → `"class": "order_lookup.OrderLookup"`.
**Prefer `async_invoke`** — the synchronous `invoke()` blocks the event loop.

```python
from typing import Any, Dict

from neuro_san.interfaces.coded_tool import CodedTool


class OrderLookup(CodedTool):
    """Looks up order status by order ID."""

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        order_id = args.get("order_id")
        return f"Order {order_id} is shipped"
```

`args` comes from `function.parameters`; `sly_data` is the private dict below. No-args constructor, JSON-friendly
return, wrap blocking I/O in `asyncio.to_thread(...)`. Docs:
[user_guide.md → Coded tools](../../../docs/user_guide.md#coded-tools).

**sly_data** — network-wide private channel for secrets/inter-agent state: client passes it in, any coded tool
reads/writes it, never reaches the LLM stream. Use a distinct key per purpose (any tool that reads sly_data reads
all of it). Doesn't cross into external/other-network agents without an explicit `allow` policy; schemas are
Front-Man-only. Also carries MCP auth headers (below). **Never log or print sly_data** — that defeats the entire
point of keeping secrets out of the chat stream. `allow` schema, agent HOCON reference:
[allow](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#allow).

**Finding a new API** — reuse the toolbox first and `registries/tools/` vendor adapters (below) first. Else search
[public-apis](https://github.com/public-apis/public-apis), [APIs.guru](https://apis.guru/),
[RapidAPI Hub](https://rapidapi.com/hub), [Apify Store](https://apify.com/store), or the vendor's own docs. Before
wiring one in, confirm base URL, **auth**, **rate limits**, pricing, and **terms**; prefer official/free tiers;
keep keys out of HOCON (env/`.env`). If the choice is ambiguous or the API has cost/usage limits, ask which
provider to use. If the user must act to get access (account, key, billing, terms), name the env var and link the
pricing page.

## MCP and external agents

An agent can consume/expose **MCP** tools, delegate to **other networks**, or bridge to **other frameworks**.

1. **MCP** — reference a server by URL (starts `https://mcp` or ends `/mcp`); its tools become callable. Auth
   headers travel via `sly_data.http_headers` (keyed by MCP URL) or server-side in
   [mcp_info.hocon](../../../neuro_san_studio/mcp/mcp_info.hocon)
   (`MCP_SERVERS_INFO_FILE`). Expose your own network as MCP with `"mcp": true` in its manifest entry (see
   `agent-network-hocon-reference` skill). Docs:
   [mcp_service.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/mcp_service.md).
2. **Other neuro-san networks** — list one as a tool to hand off a query (compose "agent webs"). sly_data only
   crosses under an explicit `allow` policy:

   ```hocon
   "tools": ["/expedia"]                            # network on this server (expedia.hocon)
   "tools": ["http://192.168.1.1:8080/expedia"]     # network on another neuro-san server
   ```

3. **Other frameworks** (A2A, CrewAI, LangGraph) — bridge with a coded tool acting as a client, e.g. the
   [A2A research report](../../../docs/examples/tools/a2a_research_report.md).
4. **SaaS adapters** in `registries/tools/` — copy one as a starting point: Salesforce
   [Agentforce](../../../docs/examples/tools/agentforce.md)
   (`agentforce.hocon`), Google
   [Agentspace](../../../docs/examples/tools/agentspace_adapter.md)
   (`agentspace_adapter.hocon`),
   [ServiceNow](../../../docs/examples/tools/now_agents.md),
   and others.
