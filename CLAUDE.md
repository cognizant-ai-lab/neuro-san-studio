# CLAUDE.md

Guidance for Claude working with **neuro-san-studio** — a playground for the
[neuro-san](https://github.com/cognizant-ai-lab/neuro-san) framework. You build **multi-agent networks**
declaratively in **HOCON** config files; add Python (a "coded tool") only when an agent needs deterministic logic
(API calls, DB queries, math).

Sections link the real docs — open them for detail instead of trusting this summary.
**Start here:** [tutorial.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/tutorial.md)
(build your first network) ·
[examples.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples.md)
(one example per feature — fastest way to find how to build something).

---

## 0. First-time setup

**Inside this repo** (not installed yet; needs Python 3.12/3.13 + `make`, macOS/Linux — Windows steps in
[CONTRIBUTING.md](CONTRIBUTING.md)):

```bash
make venv && make install       # venv/ + requirements.txt + requirements-build.txt
source venv/bin/activate
export PYTHONPATH=$(pwd)
```

**Fresh project instead** (just the framework, no clone):

```bash
pip install neuro-san-studio
ns init             # scaffolds config/, mcp/, registries/ + shared aaosa*.hocon in the cwd
```

Either way: ask which LLM provider(s) the user wants, have them set the key in `.env`
(`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`, §6), then verify with
`ns check-llm-keys && ns check-config`. Full CLI:
[cli.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/cli.md).

## 1. Repository layout

| Path | Purpose |
|------|---------|
| `registries/` | HOCON networks + `manifest.hocon`, plus shared includes (`aaosa.hocon`, `llm_config.hocon`). Curated examples in `basic/`, `tools/`, `industry/`, `experimental/`; your networks go in `generated/`. |
| `coded_tools/<agent_name>/` | Python `CodedTool` implementations (resolved via `AGENT_TOOL_PATH`, default `coded_tools/`). |
| `neuro_san_studio/` | The framework: `ns` CLI, server runner, importer/exporter, toolbox, MCP, plugins. |
| `middleware/` | Reusable `AgentMiddleware` implementations: Designer, skills, persistent memory, checklist. |
| `config/` | LLM config (`llm_config.hocon`) + plugin config (`plugins.hocon`); created by `ns init`. |
| `apps/` | Example apps built on networks (Flask UIs, Slack app) — §12. |
| `servers/` | Standalone **example** a2a / mcp servers (e.g. a demo MCP server to test against) — not needed to use MCP. |
| `skills/` | Example skill folders (each a `SKILL.md`) for `AgentSkillsMiddleware` (§10). |
| `deploy/` | Container/deploy assets: `Dockerfile`, `build.sh`, `entrypoint.sh`, `run.sh`. |
| `docs/` | Tutorials, examples, CLI docs, dev guide. |
| `tests/fixtures/` | HOCON test cases; `tests/integration/` drives them. |

## 2. Delegation between agents (AAOSA)

Routing is driven by **AAOSA** (Adaptive Agent Oriented Software Architecture): each agent decides whether to
answer itself or delegate to the down-chain agents in its `tools`, based on each down-chain agent's name and its
`function.description`. `aaosa_instructions` and `aaosa_call` (from `registries/aaosa.hocon`, a substitution-only
file) implement it — the Designer emits this for all agents:

```hocon
include "registries/aaosa.hocon",
"function": ${aaosa_call}{ "description": "Controls the TV." },
"instructions": ${instructions_prefix} """Your name is TV. ...""" ${aaosa_instructions},
```

Docs: [user_guide.md → AAOSA](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#aaosa).

## 3. The build loop

To build a new network:

1. **Generate a baseline** with the Agent Network Designer (§4) from a plain-English use case.
2. **Refine the HOCON by hand** (§5): improve instructions, add branch agents, and wire in
   tools/mcp/middleware/apps as required.
3. **Register and enable** it in `registries/generated/manifest.hocon` (§5) — the Designer usually does this, but
   verify.
4. **Lint and load it** to confirm the HOCON parses and runs correctly (`ns run` / `ns chat`, §13).
5. **Add test fixtures** with ANTeGen to check the network behaves as required; if not, refine it (§14).
6. **Documentation** is opt-in — ask the user first (§15).

## 4. Agent Network Designer

Write the use case (or the change you want) to a file, then run one-shot:

```bash
echo "Build a network for a coffee shop's order-status and loyalty-points lookup" > /tmp/prompt.txt
ns chat agent_network_designer --one-shot --first_prompt_file /tmp/prompt.txt
```

Produces agents, links, instructions, toolbox/mcp wiring, and `sample_queries`; registers the manifest entry;
saves under `registries/generated/`. To iterate on an existing generated network, pass it via `--sly_data`:

```bash
ns chat agent_network_designer --one-shot --first_prompt_file /tmp/prompt.txt \
  --sly_data '{"agent_network_hocon_file": "registries/generated/coffee_shop.hocon"}'
```

The Designer gives a baseline only — refining the `.hocon` yourself (§5) is expected. Docs:
[cli/chat.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/cli/chat.md).

## 5. Agent network HOCON

A network is one `.hocon` file (JSON + comments, multi-line strings, `${}` substitutions). Docs:
[agent HOCON reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md),
[user_guide.md → Hocon files](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#hocon-files).

### Agent types

| Type | Marked by | Role |
|------|-----------|------|
| **Front Man** | first in `tools`, **no** `parameters` | entry point, talks to the user |
| **Branch agent** | has `function.parameters` | LLM sub-agent, called by name |
| **Coded tool** | has `class` | Python logic (§8); no LLM behavior |
| **Toolbox tool** | has `toolbox` | runs directly (§7) |
| **External agent** | name is `/path` or `http(s)://host:port/agent` | another network as a tool (§9) |
| **MCP server** | URL starting `https://mcp` or ending `/mcp` | tools over MCP (§9) |

### Fields

- **Per-agent:** `name`, `function.description`, `instructions`, `function.parameters`, `tools`,
  `class`/`toolbox`, `args`, `llm_config` (§6), `allow` (§8), `middleware` (§10).
- **Front-Man only:** `function.sly_data_schema` / `sly_data_output_schema`, `max_message_history`,
  `structure_formats`.
- **Network-level:** `metadata` (`description`/`tags`/`sample_queries`), `llm_config` (§6), **`max_steps`**
  (recursion budget — not `max_iterations`), **`max_execution_seconds`** (wall-clock). Rarer keys + full defaults
  in the docs above.

### Registering the network (manifest)

`registries/manifest.hocon` includes per-group manifests. Add yours to `registries/generated/manifest.hocon` as
`"my_network.hocon": true` (serve + list), or the detailed form
`{ "serve": true, "public": false, "mcp": true }` — `serve` loads/runs it, `public` lists it in `/list` (set
`false` to keep it reachable but unlisted, e.g. a support network), `mcp` exposes it as an MCP tool (§9).
Docs:
[manifest_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/manifest_hocon_reference.md).

## 6. LLM configuration

All example/generated networks import a top-level `llm_config` file (§5) so model choice lives in one place. What it resolves to
(provider, model, fallback order) is in [config/llm_config.hocon](config/llm_config.hocon) which in turn points to
[developer_llm_config.hocon](config/developer_llm_config.hocon).
Compatible providers include `openai`, `anthropic`, `azure-openai`, `gemini`, `nvidia`, `ollama`, `bedrock`, or a
custom LangChain `class` (key setup in §0). The built-in model catalog is
[default_llm_info.hocon](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/llms/default_llm_info.hocon).
End-users can also pass their own keys at request time via `sly_data.llm_config` (§8; see `byok_llm_config.hocon`).

Docs:
[agent HOCON reference → llm_config](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#llm_config).

## 7. Toolbox: pre-built tools

Before writing a coded tool, check the **toolbox** — ready-made tools (web search, RAG, code execution,
Gmail/Jira, …). Reference by name; pass settings via `args` (merged over the tool's defaults):

```hocon
{ "name": "policy_web_search", "toolbox": "ddgs_search", "args": { "num_results": 3 } }
```

Catalog:
[toolbox_info.hocon](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/neuro_san_studio/toolbox/toolbox_info.hocon)
Defining/Customizing:
[toolbox_info_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/toolbox_info_hocon_reference.md).

## 8. Coded tools, sly_data, external APIs

When no toolbox tool fits, implement a `CodedTool` under `coded_tools/<agent_name>/`. No manifest entry — you wire
it as an agent node in the network HOCON (an up-chain agent lists it in `tools`), giving the node a
`function` (`description` + `parameters`) and `"class": "<module>.<ClassName>"` — the `.py` file name, then the
class inside it (snake_case → PascalCase). So `order_lookup.py` with `class OrderLookup` →
`"class": "order_lookup.OrderLookup"`. **Prefer `async_invoke`** — the synchronous `invoke()` blocks the event
loop.

```python
class OrderLookup(CodedTool):
    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        return f"Order {args['order_id']} is shipped"
```

`args` comes from `function.parameters`; `sly_data` is the private dict below. No-args constructor, JSON-friendly
return, wrap blocking I/O in `asyncio.to_thread(...)`. Docs:
[user_guide.md → Coded tools](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools).

**sly_data** — network-wide private channel for secrets/inter-agent state: client passes it in, any coded tool
reads/writes it, never reaches the LLM stream. Use a distinct key per purpose (any tool that reads sly_data reads
all of it). Doesn't cross into external/other-network agents without an explicit `allow` policy; schemas are
Front-Man-only. Also carries MCP auth headers (§9). `allow` schema:
[agent HOCON reference → allow](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md#allow).

**Finding a new API** — reuse the toolbox (§7) and `registries/tools/` vendor adapters (§9) first. Else search
[public-apis](https://github.com/public-apis/public-apis), [APIs.guru](https://apis.guru/),
[RapidAPI Hub](https://rapidapi.com/hub), [Apify Store](https://apify.com/store), or the vendor's own docs. Before
wiring one in, confirm base URL, **auth**, **rate limits**, pricing, and **terms**; prefer official/free tiers;
keep keys out of HOCON (§15). If the choice is ambiguous or the API has cost/usage limits, ask which provider to
use. If the user must act to get access (account, key, billing, terms), name the env var and link the pricing page.

## 9. MCP and external agents

An agent can consume/expose **MCP** tools, delegate to **other networks**, or bridge to **other frameworks**.

1. **MCP** — reference a server by URL (starts `https://mcp` or ends `/mcp`); its tools become callable. Auth
   headers travel via `sly_data.http_headers` (keyed by MCP URL) or server-side in
   [mcp_info.hocon](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/neuro_san_studio/mcp/mcp_info.hocon)
   (`MCP_SERVERS_INFO_FILE`). Expose your own network as MCP with `"mcp": true` in its manifest (§5). Docs:
   [mcp_service.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/mcp_service.md).
2. **Other neuro-san networks** — list one as a tool to hand off a query (compose "agent webs"). sly_data only
   crosses under an explicit `allow` policy (§8):

   ```hocon
   "tools": ["/expedia"]                            # network on this server (expedia.hocon)
   "tools": ["http://192.168.1.1:8080/expedia"]     # network on another neuro-san server
   ```

3. **Other frameworks** (A2A, CrewAI, LangGraph) — bridge with a coded tool acting as a client, e.g. the
   [A2A research report](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples/tools/a2a_research_report.md).
4. **SaaS adapters** in `registries/tools/` — copy one as a starting point: Salesforce
   [Agentforce](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples/tools/agentforce.md)
   (`agentforce.hocon`), Google
   [Agentspace](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples/tools/agentspace_adapter.md)
   (`agentspace_adapter.hocon`),
   [ServiceNow](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples/tools/now_agents.md),
   and others.

## 10. Middleware (skills, memory, checklist)

**Middleware** injects code at agent hook points (`abefore_agent`/`aafter_agent`, `abefore_model`/`aafter_model`,
`awrap_model_call`, `awrap_tool_call` — async preferred). Attach per agent via `middleware` (order matters);
class-based `AgentMiddleware` only. Docs:
[user_guide.md → Middleware](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#middleware).
Three commonly used middlewares ship with the repo:

- **Skills** (`agent_skills_middleware.AgentSkillsMiddleware`, args `skill_sources`/`keep_skill_in_context`) — a
  skill is a folder with a `SKILL.md`; metadata loads first, content pulls in on demand (progressive disclosure).
  Example: [job_guessing_skill.hocon](registries/basic/job_guessing_skill.hocon). Docs:
  [user_guide.md → Agent Skills](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#agent-skills).
  **Security:** review any internet-sourced skill — it can reference untrusted tools/resources.
- **Persistent memory** (`persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware`) — memory
  across sessions (create/read/append/delete/search/list). Attach to **your own** agent, don't import the
  reference network. Backends: `json_file`/`markdown_file` (local, per `(network, agent)`, **not** per user) or
  `mem0` (cloud, per end user — for shared/production). Refs: `registries/tools/persistent_memory_local.hocon`,
  `persistent_memory_mem0.hocon`; docs
  [local](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples/tools/persistent_memory_local.md)
  ·
  [mem0](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples/tools/persistent_memory_mem0.md).
- **Checklist** (`agent_checklist_middleware.AgentChecklistMiddleware`, args `checklist_title`/
  `keep_checklist_in_context`/`progress_reporter`) — `pending`/`in_progress`/`done`/`skipped` tracking for
  multi-step tasks. Example:
  [coding_assistant.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples/basic/coding_assistant.md).

## 11. Plugins (observability, logging, authorization)

**Plugins** extend the server for deployment use-cases; registered in `config/plugins.hocon`, toggled by env var,
never required to run. All extend `BasePlugin` (`neuro_san_studio/interfaces/base_plugin.py`). Docs (with links to
each tool's own docs): [plugins.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/plugins.md).

- **Observability** — Langfuse / Arize Phoenix / LangSmith. Off by default (`LANGFUSE_ENABLED`, `PHOENIX_ENABLED`,
  `LANGSMITH_TRACING`).
- **Logging** — Log Bridge, Rich structured console logs. On by default (`LOGBRIDGE_ENABLED` to disable).
- **Authorization** — Open FGA (ReBAC).

## 12. Building an app on a network

Wrap a network in your own app via the neuro-san **session client** — `DirectAgentSession` runs it in-process (no
server; async variants exist). Docs:
[clients.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/clients.md),
[integration quick start](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/integration_quickstart.md).
Examples in `apps/` (each with its own `requirements.txt`): `slack/` (Slack app), `conscious_assistant/` + `cruse/`
(Flask UIs), `log_analyzer/`, `wwaw/`.

**CRUSE** (Context-React User Experience) is a built-in dynamic UI that adapts to the network (AI-generated themes,
form widgets, threads). Enable by importing the experimental `cruse_theme_agent` / `cruse_widget_agent`
(`ns import`), then open the Cruse page. Docs:
[cruse_interface.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/cruse_interface.md).

## 13. Running, linting, testing

```bash
ns run                     # server (localhost:8080) + nsflow UI (localhost:4173)
ns chat my_network         # chat directly, no server
ns chat --list             # list networks
ns check-llm-keys          # validate provider keys
ns check-config            # validate config/llm_config.hocon
```

`ns <command> --help` for flags. Logs under `logs/` (`server.log`, `nsflow.log`, `thinking_dir/`); verbose coded-
tool logging via `export AGENT_SERVICE_LOG_JSON=logging.hocon`.

Before finishing, everything must lint and pass (line length **119**):

```bash
make lint    # ruff format + ruff check + pylint, source and tests
make test    # runs make lint, then pytest with coverage (excludes integration tests)
```

Integration tests (`tests/fixtures/`, §14) run via `make test-integration`, which sets the required env vars
(`AGENT_TOOL_PATH=coded_tools/`, `AGENT_MANIFEST_FILE=registries/manifest.hocon`) for you — export those same
values first if you call pytest directly (`pytest -s -m "integration_basic"` narrows to one group).

Validate a network before running with the
[HOCON validator CLI](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/hocon_validator_cli.md); docs
are markdown-linted (`pymarkdown --config ./.pymarkdownlint.yaml scan ./docs ./README.md`).

**Import/export:** `ns import` pulls example networks (by group/name, or from a file/`.zip`); `ns export
my_network` bundles a network + all dependencies into one shareable file. Docs:
[import](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/cli/import.md),
[export](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/cli/export.md).

## 14. Test cases (fixtures + ANTeGen)

Fixtures are HOCON under `tests/fixtures/<group>/<network>/*.hocon`, run by
`tests/integration/test_integration_test_hocons.py`. A fixture names the `agent` and lists `interactions` (input
`text` → expected `response`, e.g. `keywords` or a `structure`). Spec:
[test_case_hocon_reference.md](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md).

Generate with **ANTeGen**: `ns chat agent_network_test_generator`, ask e.g. *"Generate test cases for
basic/music_nerd_pro"*. Two follow-ups are on you: **review** the generated `keywords`/`gist`/`value`/`sly_data`
(LLM-generated, not always right), and **register** the fixture in `test_integration_test_hocons.py` for CI. Docs:
[agent_network_test_generator.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/agent_network_test_generator.md).

## 15. Conventions, docs, pitfalls

**Documentation is opt-in — ask first, don't write by default.** When asked:

- Network in `generated/`: short doc at `docs/examples/generated/<network>.md` (intro, `## Prerequisites`,
  `## File`, `## Description`, optional `## Example conversation`) + a line/TOC entry in
  [examples.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/examples.md).
- Curated example (`basic/`, `industry/`, `tools/`): heavier — follow the
  [dev_guide.md checklist](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/dev_guide.md#checklist)
  (metadata, per-network doc, `examples.md` entry, registered test fixture).
- A feature, not a network (toolbox tool, plugin, middleware): update the matching reference doc
  ([toolbox.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/toolbox.md),
  [plugins.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/plugins.md),
  [search_tools.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/search_tools.md),
  [user_guide.md → Middleware](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#middleware)).

**House rules:**

- Every network sets `max_steps` and `max_execution_seconds` — never unbounded.
- Long-form flags (`--force`, not `-f`); no secrets in HOCON (env/`.env`); `logging`, never `print`.
- Keep changes minimal and focused — no unrequested refactors.
- Moving a network between folders: follow the
  [dev_guide.md](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/dev_guide.md) reorg checklist
  (manifest, fixture, docs, cross-refs; tool refs become path-based like `/tools/ddgs_search`).
- Branches `feature/…` `fix/…` `docs/…`; commits one line, issue number first (`#123: ...`). Full PR checklist:
  [CONTRIBUTING.md](CONTRIBUTING.md).

**Pitfalls:**

- The Front Man must be an LLM agent, not a coded/toolbox tool.
- Network-level `tools` (agent *definitions*) ≠ an agent's `tools` (down-chain agents it can *call*).
- A `toolbox` agent can't have `tools` — it runs code, can't call sub-agents.
- Don't assume the default model supports tool-calling; check `capabilities` in the LLM info config.
