---
name: agent-network-hocon-reference
description: Write or edit a neuro-san-studio agent network HOCON file — agent types, AAOSA delegation, fields,
  and manifest registration. Use when hand-refining a generated network or authoring/editing any .hocon network
  file directly.
---

# Agent network HOCON

A network is one `.hocon` file (JSON + comments, multi-line strings, `${}` substitutions).
Docs: [agent HOCON reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md),
[user_guide.md → Hocon files](../../../docs/user_guide.md#hocon-files).

## Delegation between agents (AAOSA)

Routing is driven by **AAOSA** (Adaptive Agent Oriented Software Architecture): each agent decides whether to
answer itself or delegate to the down-chain agents in its `tools`, based on each down-chain agent's name and its
`function.description`. `aaosa_instructions` and `aaosa_call` (from `registries/aaosa.hocon`, a substitution-only
file) implement it — the Designer emits this for all agents:

```hocon
include "registries/aaosa.hocon",
"function": ${aaosa_call}{ "description": "Controls the TV." },
"instructions": ${instructions_prefix} """Your name is TV. ...""" ${aaosa_instructions},
```

Docs: [user_guide.md → AAOSA](../../../docs/user_guide.md#aaosa).

## Agent types

| Type | Marked by | Role |
|------|-----------|------|
| **Front Man** | first in `tools`, **no** `parameters` | entry point, talks to the user |
| **Branch agent** | has `function.parameters` | LLM sub-agent, called by name |
| **Coded tool** | has `class` | Python logic; no LLM behavior — see `agent-network-tool-integration` skill |
| **Toolbox tool** | has `toolbox` | runs directly — see `agent-network-tool-integration` skill |
| **External agent** | name is `/path` or `http(s)://host:port/agent` | another network as a tool — see `agent-network-tool-integration` skill |
| **MCP server** | URL starting `https://mcp` or ending `/mcp` | tools over MCP — see `agent-network-tool-integration` skill |

## Fields

- **Per-agent:** `name`, `function.description`, `instructions`, `function.parameters`, `tools`,
  `class`/`toolbox`, `args`, `llm_config` (see `agent-network-llm-config` skill), `allow`, `middleware` (see
  `agent-network-middleware` skill).
- **Front-Man only:** `function.sly_data_schema` / `sly_data_output_schema`, `max_message_history`,
  `structure_formats`.
- **Network-level:** `metadata` (`description`/`tags`/`sample_queries`), `llm_config`, **`max_steps`** (recursion
  budget — not `max_iterations`), **`max_execution_seconds`** (wall-clock). Rarer keys + full defaults in the docs
  above.

**House rule:** every network you generate or edit must set `max_steps` and `max_execution_seconds` — never
unbounded. (Not yet universal across older curated networks — don't treat a missing value elsewhere as precedent
to skip this.)

## Registering the network (manifest)

`registries/manifest.hocon` includes per-group manifests, including `registries/generated/manifest.hocon` — that
directory/file is git-ignored and **absent on a fresh clone**; create both if they don't exist yet (an empty `{}`
is a valid starting manifest). Add yours as `"my_network.hocon": true` (serve + list), or the detailed form
`{ "serve": true, "public": false, "mcp": true }` — `serve` loads/runs it, `public` lists it in `/list` (set
`false` to keep it reachable but unlisted, e.g. a support network), `mcp` exposes it as an MCP tool (see
`agent-network-tool-integration` skill).
Docs: [manifest_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/manifest_hocon_reference.md).

A manifest key registered from a subfolder's manifest (e.g. `"my_network.hocon": true` inside
`registries/generated/manifest.hocon`) registers the runtime agent name **with that folder prefix** —
`generated/my_network`. Run/chat with the prefixed name (`ns chat generated/my_network`) always.

## Pitfalls

- The Front Man must be an LLM agent, not a coded/toolbox tool.
- Network-level `tools` (agent *definitions*) ≠ an agent's `tools` (down-chain agents it can *call*).
- A `toolbox` agent can't have `tools` — it runs code, can't call sub-agents.
- Don't assume the default model supports tool-calling; check `capabilities` in the LLM info config.
