# Persistent memory middleware

`PersistentMemoryMiddleware` attaches long-term memory to any Neuro-san-studio
agent. Drop it into an agent's `middleware` block and the framework registers
a `persistent_memory` tool, injects a memory-aware preamble into the system
prompt, and persists every write to disk under a `(network, agent)`
namespace.

Writes are per-call: each tool invocation is a self-contained
read-modify-write against disk, guarded by a per-key `asyncio.Lock`. There
is no end-of-turn flush — a crash mid-turn loses at most the call that was
in flight.

## Why middleware, not a coded tool

Memory needs two things the agent lifecycle already gives you: a tool the
LLM calls, and a preamble that teaches the LLM when to call it. A coded
tool can register the former but not the latter, so every HOCON would have
to copy the rules by hand. Middleware ships both together. See
[Middleware](../../user_guide.md#middleware) for the generic concept.

## Configuration

> **Important:** attach `PersistentMemoryMiddleware` to the `middleware` block
> of **your own agent** — do not import the `persistent_memory` agent network
> as a sub-network. The middleware is what registers the tool and injects the
> preamble; calling the reference network from another agent will not give
> that agent memory.

Full configuration with every key shown at its default. Only `class` is
required; every other key is optional and falls back to the value below.

```hocon
"middleware": [
    {
        "class": "middleware.persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware",  # (required)
        "args": {
            "origin_str": true,                          # framework-injected dotted call path; used to derive the (network, agent) namespace
            "memory_config": {
                "storage": {
                    "backend":          "json_file",     # or "markdown_file"
                    "folder_name":        "./memory",      # relative to the server's CWD
                    "file_name": "memory"         # json_file backend only
                },
                "summarization": {
                    "max_topic_size":  1000,              # 0 disables summarization
                    "model":           "gpt-5.4-mini",
                    "personalization": ""                # appended to the summarizer prompt
                },
                "enabled_operations": ["create", "read", "append", "delete", "search", "list"]
            }
        }
    }
]
```

A complete reference agent using this middleware lives at
[`registries/tools/persistent_memory.hocon`](../../../registries/tools/persistent_memory.hocon).

## Quick try

The reference network registers a `MemoryAssistant` agent. Start the
server, point your client at it, and have a short conversation with two
people sharing facts:

```text
You:   Hi, I'm Mike. I always order black coffee from Henry's.
Agent: Got it, Mike — I'll remember that.

You:   By the way, my friend Jason only drinks matcha lattes.
Agent: Noted — I'll remember Jason's matcha preference too.
```

Behind the scenes the agent made two calls, one per person:

```text
persistent_memory(operation="create", topic="mike",
                  content="Orders black coffee from Henry's.")
persistent_memory(operation="create", topic="jason",
                  content="Only drinks matcha lattes.")
```

Each person is a separate topic, and every fact about that person lives
under their topic. Restart the server and open a fresh session:

```text
You:   What does Jason drink?
Agent: Jason only drinks matcha lattes.

You:   And what's my usual?
Agent: Your usual is a black coffee from Henry's.
```

The agent reconstructed both facts from disk. What was written depends on
the backend:

**`json_file` backend** — one file per agent, all topics inside it:

```text
./memory/memory_tutorial/MemoryAssistant/
└── memory.json
```

```json
{
  "mike":  "Orders black coffee from Henry's.",
  "jason": "Only drinks matcha lattes."
}
```

**`markdown_file` backend** — one file per topic:

```text
./memory/memory_tutorial/MemoryAssistant/
├── mike.md
└── jason.md
```

```markdown
# mike

Orders black coffee from Henry's.
```

```markdown
# jason

Only drinks matcha lattes.
```

## Storage backends

Two backends ship. Both share the same on-disk layout
(`<root>/<network>/<agent>/…`) and the same atomic write (temp-file rename,
so an interrupted write never leaves a torn file).

| Backend         | Layout                         | Lock granularity                | Best for                                   |
| :-------------- | :----------------------------- | :------------------------------ | :----------------------------------------- |
| `json_file`     | one `memory.json` per agent    | one lock per `(network, agent)` | Few topics, many writes per topic          |
| `markdown_file` | one `<topic>.md` per topic     | one lock per topic              | Many topics, parallel writes, hand-editing |

Either backend works; pick whichever fits your setup. Configure it via
the `storage` block:

```hocon
"storage": {
    "backend":          "markdown_file",
    "folder_name":        "./memory",
    "file_name": "memory"
}
```

The three keys:

- **`backend`** — which store to use. Either `json_file` (one
  `memory.json` per agent) or `markdown_file` (one `.md` file per
  topic). Defaults to `json_file`.
- **`folder_name`** — directory where memory files are written, relative
  to the server's working directory. The middleware appends
  `/<network>/<agent>/` beneath it so each agent gets its own slice.
  Defaults to `./memory`.
- **`file_name`** — file stem for the JSON backend only; the
  final path is `<folder_name>/<network>/<agent>/<file_name>.json`.
  Ignored by the markdown backend. Defaults to `memory`.

## Summarization

Topics grow. Left alone, a single topic can balloon past the context
window. The summarizer consolidates oversized topics inline, under the
same lock that performed the write, so no concurrent reader ever observes
the oversized intermediate state.

```hocon
"summarization": {
    "max_topic_size":  1000,
    "model":           "gpt-5.4-mini",
    "personalization": "Write summaries in a warm, concise tone."
}
```

The three keys:

- **`max_topic_size`** — character threshold past which a topic is
  summarized. Any write, `read`, or `search` that sees
  `len(content) > max_topic_size` fires the summarizer inline. Set to `0`
  (or omit the whole `summarization` block) to disable summarization
  entirely.
- **`model`** — OpenAI model used to generate the summary. Defaults to
  `gpt-5.4-mini`.
- **`personalization`** — optional string appended to the summarizer
  prompt. A hook for per-deployment tone ("warm and concise", "strictly
  factual", etc.).

`list` returns keys only, so it never triggers the summarizer. Summarizer
failures are caught — the original content stays on disk, so a transient
LLM error cannot destroy memory.

## Restricting operations

All six operations are available by default. Narrow the whitelist to
constrain the LLM:

```hocon
"enabled_operations": ["read", "search", "list"]
```

The JSON-schema `enum` visible to the LLM is narrowed at startup — it
literally cannot pick a disabled operation. Common shapes:

- **Read-only:** `["read", "search", "list"]`
- **Append-only:** `["read", "append", "search", "list"]`
- **Full:** omit the key, or list all six

Unknown entries are dropped with a warning. If *every* entry is unknown
the middleware raises at startup — a loud failure beats a silent "no
tools".

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│ HOCON                                                         │
│   "middleware": [ PersistentMemoryMiddleware ]                │
└───────────────────────────────────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────┐
│ PersistentMemoryMiddleware                                    │
│   - Parses HOCON → TopicStore + TopicSummarizer               │
│   - Registers the `persistent_memory` tool on the agent       │
│   - Injects a preamble into the system prompt                 │
└───────────────────────────────────────────────────────────────┘
               │ (at tool-call time)
               ▼
┌───────────────────────────────────────────────────────────────┐
│ PersistentMemoryTool                                          │
│   - Validates args, dispatches to _handle_<op>                │
│   - Talks to the store under the store's lock                 │
│   - Runs the summarizer inline on oversized content           │
└───────────────────────────────────────────────────────────────┘
               │
               ▼
┌───────────────────────────────────────────────────────────────┐
│ TopicStore (abstract)                                         │
│   JsonFileStore     — one memory.json per agent               │
│   MarkdownFileStore — one .md file per topic                  │
└───────────────────────────────────────────────────────────────┘
```

Each agent gets its own slice of disk so memories never leak between agents
or networks. The slice is identified by a `(network, agent)` pair — for
example, a `MemoryAssistant` in the `memory_tutorial` network writes to
`./memory/memory_tutorial/MemoryAssistant/`.

The middleware figures out this pair automatically from the agent's
runtime call path, which the framework passes in as `origin_str`. Setting
`"origin_str": true` in the middleware args asks the framework to inject
this path; if you forget, the namespace falls back to
`./memory/unknown/unknown/` and you'll see a warning in the logs.

## Reference

Unknown keys in `memory_config` at either level are ignored with a
warning — typos surface quickly without crashing the server.

### Operations

| Operation | Required args      | Returns                                    |
| :-------- | :----------------- | :----------------------------------------- |
| `create`  | `topic`, `content` | `{"status": "created", "topic": ...}`      |
| `read`    | `topic`            | `{"topic": ..., "content": ...}`           |
| `append`  | `topic`, `content` | `{"status": "appended", "topic": ...}`     |
| `delete`  | `topic`            | `{"status": "deleted", "topic": ...}`      |
| `search`  | `query`, `limit?`  | `{"results": [{"topic", "content", ...}]}` |
| `list`    | —                  | `{"topics": [...]}`                        |

`create` overwrites. `append` adds a timestamped line. `delete` removes
the entire topic (not a single line). `search` keyword-ranks across this
agent's topics.

### Debugging

- **Inspect on disk.** `<root>/<network>/<agent>/` holds the raw files
  for either backend. Hand-edit them and the next `read` picks up your
  change.
- **"Operation X is not enabled"** — check `enabled_operations` in your
  HOCON. The error message lists exactly what is enabled.
- **Summaries never appear** — either `max_topic_size` is too high for
  your content, the `model` string is wrong, or the summarizer is
  erroring and swallowing the failure. Every summarizer error is logged
  at `WARNING`.
- **`unknown` in filesystem paths** — `origin_str` was empty or
  malformed. In almost every deployment this means `"origin_str": true`
  is missing from the middleware `args`.

### Source

- `middleware/persistent_memory/middleware.py` — the middleware itself.
- `middleware/persistent_memory/persistent_memory_tool.py` — the
  `persistent_memory` tool the LLM calls.
- `middleware/persistent_memory/topic_store.py` — abstract store base.
- `middleware/persistent_memory/json_file_store.py`,
  `markdown_file_store.py` — backends.
- `middleware/persistent_memory/topic_summarizer.py` — the `ChatOpenAI`
  wrapper.
- `registries/tools/persistent_memory.hocon` — the reference network.
