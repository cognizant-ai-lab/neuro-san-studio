# Persistent Memory

The **Persistent Memory** tool gives an agent long-term, per-user, per-agent
memory: a CRUD + keyword-search store that survives across sessions. It is
exposed to the LLM as a single `persistent_memory` tool, but it is registered
on the agent automatically by a middleware — not by listing it in `tools: [...]`.

---

## File

[persistent_memory.hocon](../../../registries/tools/persistent_memory.hocon)

---

## Prerequisites

No extra pip dependencies for the default JSON / markdown file backends.

The optional summariser (LLM-backed auto-compaction + read/search
post-processing) needs:

```bash
pip install langchain-openai
```

and an `OPENAI_API_KEY` in the environment. Leave the summariser block
absent — or set `enabled = false` — to skip this.

---

## Storage backends

Memory is file-backed. Two formats are shipped and interchangeable:

| Backend id      | On-disk format | Layout                                                                    |
| :-------------- | :------------- | :------------------------------------------------------------------------ |
| `json_file`     | JSON           | `<root>/<agent_network>/<agent>/<topic>.json` — one file per topic        |
| `markdown_file` | Markdown       | `<root>/<agent_network>/<agent>/<topic>.md` — one H1 section per key      |

The default is `json_file`. To switch, set `store_config.backend` in the
HOCON or the `MEMORY_BACKEND` environment variable.

`root_path` defaults to `./memory` and is resolved relative to the
**process working directory** when the neuro-san server starts — in
practice the root of the repo. Pass an absolute path if you need
deterministic behaviour under a different working directory.

Backend selection is layered — later wins:

1. `store_config` block inside the middleware `args` in HOCON.
2. `MEMORY_STORE_CONFIG` env var (a JSON object, shallow-merged on top of the HOCON).
3. Individual env vars: `MEMORY_BACKEND`, `MEMORY_ROOT_PATH`.

This lets you ship HOCON with one backend and swap it at deploy time without
editing files.

---

## Minimal HOCON

```hocon
"middleware": [
    {
        "class": "middleware.persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware",
        "args": {
            "agent_network_name": "persistent_memory",
            "agent_name":         "MemoryAssistant",

            "store_config": {
                "backend":   "json_file",
                "root_path": "./memory"
            },

            # Which operations the LLM is allowed to call. Omit to allow all seven.
            "enabled_operations": ["create", "read", "update", "delete", "search", "list"]
        }
    }
]
```

The seven supported operations are `create`, `read`, `update`, `append`,
`delete`, `search`, and `list`. Restrict this list for read-only or
write-only agents — the LLM cannot pick an operation that is not in the
whitelist because the schema's enum is narrowed at startup.

---

## Optional summariser

Add a `memory_summariser` block to compress accumulated memory before the
LLM sees it, and to auto-compact the on-disk file once it grows past a
threshold:

```hocon
"memory_summariser": {
    "enabled"           = true
    "model"             = "gpt-4.1-mini"
    "instructions"      = "You are a summariser. Keep the output under 500 chars."
    "compact_on_write"  = true
    "compact_threshold" = 500
    "personalisation"   = ""   # optional extension to the instructions
}
```

- `compact_on_write` — when `true`, every successful write that pushes the
  stored content past `compact_threshold` triggers an in-place rewrite
  using the summariser output. Failures are best-effort: the original
  write is never rolled back.
- `personalisation` — appended to the base `instructions` on every call.
  Use this for per-deployment tone or content preferences without
  touching the base prompt.

---

## Example conversation

### Human

```text
Hi, I'm Mike. I always order black coffee from Henry's.
```

### AI (Memory Assistant)

```text
Got it, Mike — I'll remember that you prefer black coffee from Henry's.
```

(Under the hood the agent called
`persistent_memory(operation="create", key="coffee_preference", content="black coffee from Henry's")`.)

### Human (next session)

```text
What's my usual?
```

### AI (Memory Assistant)

```text
Your usual is a black coffee from Henry's.
```

(The agent called `persistent_memory(operation="search", query="usual coffee")`
and got the previously stored entry back.)

---

## Architecture overview

### Frontman agent: **Memory Assistant**

- A single agent with one `middleware` block.
- No explicit `tools:` entry for `persistent_memory` — the middleware
  registers it on startup.
- Instructions tell the agent to call `persistent_memory` on every turn:
  `search` at the start to surface relevant memory, `create` / `update` /
  `delete` when the user shares or corrects a fact.

### Middleware: `PersistentMemoryMiddleware`

- Wraps `PersistentMemoryTool` as a LangChain `StructuredTool` named
  `persistent_memory`.
- Injects a short preamble into the system prompt describing the tool
  and the enabled operations.
- Optional summariser post-processes `read` / `search` results and
  handles auto-compaction on write.

### Tool: `PersistentMemoryTool`

- Dispatches to per-operation handlers (`_handle_create`,
  `_handle_read`, …).
- Enforces the `enabled_operations` whitelist on every LLM call.
- Delegates storage to a pluggable `MemoryStore` backend selected by
  `MemoryStoreFactory`.

### Namespace

Every entry lives under a 3-tuple namespace
`(agent_network_name, agent_name, topic)`. `topic` is the filename on
disk — typically a user id pulled from `sly_data["user_id"]` if the LLM
does not supply one explicitly. This keeps users' memories isolated
from each other and from other agents on the same deployment.

---

## Debugging hints

- Check `<root>/<agent_network>/<agent>/` — the on-disk files are
  human-readable. Hand-edits survive round-trips for both backends.
- If the agent complains that an operation is "not enabled", confirm
  `enabled_operations` in the HOCON includes the name the LLM used.
- If the summariser is configured but never fires, check
  `compact_threshold` and the raw file size. Content shorter than the
  threshold is returned raw — no LLM call.
- The summariser requires `langchain-openai` and an API key. Set
  `enabled = false` in the `memory_summariser` block to bypass it
  entirely.

---
