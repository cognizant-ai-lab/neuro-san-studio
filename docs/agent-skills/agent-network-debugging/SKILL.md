---
name: agent-network-debugging
description: Diagnose a misbehaving neuro-san-studio network — wrong agent answers, a tool/agent never gets
  called, an infinite loop or max_steps exceeded, "agent not found", or sly_data/MCP data not arriving. Use when
  a network isn't behaving as expected and you need the root cause, not a guessed fix.
---

# Debugging a misbehaving network

Match the symptom to where the bug actually lives — don't guess at instructions wording before ruling these out.

**"Agent not found" / can't `ns chat` it at all**
- Is it registered in a manifest that's actually included by `registries/manifest.hocon`? An empty/missing
  `registries/generated/manifest.hocon` means nothing in `generated/` serves.
- Registered from a subfolder manifest? The runtime name gets that folder's prefix —
  `ns chat generated/my_network`, not `ns chat my_network`. See `agent-network-hocon-reference` skill.
- Run `ns validate my_network.hocon` first — catches HOCON syntax errors before you chase a phantom behavior bug.

**A down-chain agent is never delegated to**
- AAOSA delegation is the *calling* LLM reading each candidate's `function.description` — a vague or overlapping
  description is the most common cause of "it never calls X." Sharpen the description, not the instructions.
- Confirm the agent's exact `name` appears in the caller's `tools` list — a typo here fails silently, the LLM
  just never sees that option.
- `aaosa_instructions`/`aaosa_call` missing from the caller (forgot `include "registries/aaosa.hocon"` or the
  substitution)? Without it the agent has no delegation logic to run at all.

**A coded tool / toolbox tool never triggers**
- Missing or under-specified `function.parameters`? The calling LLM can't pass arguments it was never told exist.
- Coded tool: does `"class"` resolve? Check `AGENT_TOOL_PATH` and the module/class naming convention — see
  `agent-network-env-vars` and `agent-network-tool-integration` skills.
- Toolbox tool: does the `toolbox` name match an entry in `toolbox_info.hocon` (or `AGENT_TOOLBOX_INFO_FILE`)?
  A typo'd toolbox name fails at load time, not gracefully.
- The LLM never calls *any* tool? Check `capabilities` in the LLM info config — not every model supports
  tool-calling, and this fails silently rather than erroring.

**Infinite loop / hits `max_steps` or times out**
- Cyclic delegation (A calls B calls A) with no exit condition in the instructions — the graph itself is a valid
  cycle, but nothing tells either agent when to stop and answer.
- `max_steps`/`max_execution_seconds` absent entirely (not just high) — always set them, see the house rule in
  `agent-network-hocon-reference` skill.
- For a periodic (cron-triggered) network specifically, see `agent-network-periodic-triggers` skill — a bad
  `text` trigger can retrigger the same failure every cycle.

**`sly_data` or MCP auth data isn't arriving where expected**
- By default **no `sly_data` crosses a network boundary** — an external/other-network agent needs an explicit
  `allow` policy per key. See `agent-network-tool-integration` skill.
- MCP auth headers: check `sly_data.http_headers` is keyed by the exact MCP URL, or that
  `MCP_SERVERS_INFO_FILE` actually points where you think — see `agent-network-env-vars` skill.

**Network won't load / errors immediately on start**
- Is the **first** agent in `tools` a `class`/`toolbox` agent instead of an LLM agent? The Front Man must be LLM —
  see the pitfalls in `agent-network-hocon-reference` skill.
- Does a `toolbox` agent also have a `tools` list? It can't — it executes code directly, it doesn't delegate.
- Did you put an agent *definition* where a *reference* belongs, or vice versa — confusing the network-level
  `tools` array (definitions) with an agent's own `tools` field (down-chain agent names it can call)?

**A scheduled (periodic) network just never fires**
- Check the server log for a warning, not an error — an invalid `cron_schedule` string gets that interaction
  silently disabled (`enable: false`) rather than failing the manifest load. See `agent-network-periodic-triggers`
  skill.
- `"periodic": false` or the key simply absent both mean "off" — easy to leave unset by accident when copying a
  manifest entry from another network.

**Wrong model responds, or a client-supplied key/fallback isn't taking effect**
- BYOK via `sly_data.llm_config`: keys are the **lowercase** env var name (`openai_api_key`, not
  `OPENAI_API_KEY`) — a casing mismatch is silently ignored, not rejected. See `agent-network-llm-config` skill.
- A `fallbacks` list can mask a real config problem — if the primary model errors, you silently get a fallback's
  answer and may not notice you're not testing what you think you're testing.
- Custom LLM `class` (e.g. a LangChain provider path) misspelled — fails at network load, not at inference time.

**MCP tool doesn't show up in the tool list**
- The URL must literally start with `https://mcp` or end in `/mcp` to be recognized as an MCP server — anything
  else gets parsed as an external agent reference instead and fails to connect the way you'd expect.

**Persistent memory seems to leak between users, or doesn't persist at all**
- Local backends (`json_file`/`markdown_file`) are scoped per `(network, agent)`, **not per end user** — every
  user talking to that agent shares the same memory store. If you need per-user isolation, that's what `mem0` is
  for. See `agent-network-middleware` skill.

**`ns validate` passed but the network still misbehaves at runtime**
- `ns validate` only checks HOCON structure — it makes no LLM calls, so a network that's syntactically valid but
  semantically broken (vague descriptions, missing delegation logic, wrong model capability) passes it cleanly.
  Passing validate rules out syntax errors, nothing else.

**General first move**: reproduce with the smallest possible `ns chat` input, then check `logs/thinking_dir/` and
`server.log` before touching any HOCON — the step-by-step trace usually shows exactly which agent/tool step
diverged from what you expected, which turns a guess into a fix.
