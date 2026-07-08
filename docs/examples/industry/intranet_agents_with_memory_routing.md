# Intranet Agents With Memory Routing

The **Intranet Agents With Memory Routing** network is the [Intranet Agents With Tools](intranet_agents_with_tools.md)
network with one extra capability: the top-level "front-man" agent **learns how to route** and remembers it. The
first time it sees an inquiry of a given kind, it discovers which down-chain agents fulfill it. It then caches that
route — the fulfilling leaf agents and the parameters they require — in persistent memory under a generalized topic.
The next time a similar inquiry comes in, it reads the cached route and calls those leaf agents directly, skipping the
discovery round-trips.

## File

[intranet_agents_with_memory_routing.hocon](../../../registries/industry/intranet_agents_with_memory_routing.hocon)

---

## What is different from Intranet Agents With Tools

The department/leaf agents (IT, Finance, Procurement, Legal, HR, and their sub-agents and coded tools) are unchanged.
Everything new lives on the front-man agent, `MyIntranet`:

- **Persistent memory middleware.** The `PersistentMemoryMiddleware` is attached to `MyIntranet` and auto-registers a
  `persistent_memory` tool (backed by the `mem0` store) with the `create`, `read`, `list`, and `delete` operations
  enabled. It is a tool the agent uses for routing state, not a personal-fact store.
- **A `CallAgent` tool.** On a cache hit, the front-man uses `CallAgent` to call the cached leaf agents directly by
  name instead of walking the AAOSA tree again.
- **A two-step routing policy** in the front-man's instructions (see below).
- **A custom memory preamble** supplied from HOCON (see [Overriding the memory preamble](#overriding-the-memory-preamble)).

---

## How routing works

On **every** inquiry the front-man runs Step 1 first:

### Step 1 — Route via memory cache

1. Call `persistent_memory` with `operation="list"` to get all cached topic names.
2. Judge whether any cached topic (e.g. `schedule_absence`) matches the current inquiry.
3. On a match, `read` that topic to recover its `leaf_agents` and required `parameters`.
4. Collect any missing parameters from the user in a single message.
5. Call each cached leaf agent with `CallAgent` using `mode="Fulfill"` and compile the results.

### Step 2 — Route via Determine (only on a cache miss)

1. Call the department-level down-chain agents with `mode="Determine"` to find who can handle the inquiry.
2. Follow up / fulfill through the tree until the inquiry is answered.
3. Read the `Handled by:` line from the leaf agents, generalize the inquiry into a short `snake_case` topic
   (e.g. `schedule_absence` covers sick day, vacation, and PTO — not `sick_day_tuesday`), and `create` a memory entry:

   ```json
   {
       "leaf_agents": ["<verbatim names from the Handled by: line>"],
       "parameters": ["<required param name>"]
   }
   ```

The next inquiry of the same kind is then served straight from Step 1.

> **Why `mode` matters:** the leaf agents follow AAOSA. Called **with** a `mode` (`Determine`, `Fulfill`, or
> `Follow up`) they return a structured, parseable block; called **without** a `mode` they reply with user-facing
> natural-language text. The front-man therefore always passes a `mode` when calling them programmatically.

---

## Overriding the memory preamble

`PersistentMemoryMiddleware` adds a short "you have a memory tool" preamble to the system prompt. Its default is aimed
at a personal-fact store. This network uses memory as a routing cache instead, so it supplies its own preamble via the
middleware's `preamble` HOCON argument rather than editing the shared default:

```hocon
"middleware": [
    {
        "class": "middleware.persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware",
        "args": {
            "origin_str": true,
            "memory_config": { "storage": { "backend": "mem0" }, "enabled_operations": ["create", "read", "list", "delete"] },
            "preamble": """
You have a 'persistent_memory' tool for facts that must survive across turns and sessions.
...
            """
        }
    }
]
```

When `preamble` is omitted, the middleware falls back to its built-in default (`build_preamble`).

---

## Example Conversation

### Human

```text
How many days of vacation do I have left?
```

### AI (intranet_agents_with_memory_routing)

```text
You can find out how many days of vacation you have left by accessing the Absence Management tool on the company's intranet.
It will provide you with the most accurate and up-to-date information regarding your vacation balance.

For more details, please visit company's intranet.
```

The first time this is asked, the front-man discovers the route through AAOSA and caches it under a topic such as
`check_leave_balance`. Subsequent leave-balance questions are routed directly to the cached leaf agent.

---

## Architecture Overview

The agent tree is identical to [Intranet Agents With Tools](intranet_agents_with_tools.md); refer to that document for
the full department/leaf breakdown. The only structural additions are on the front-man:

- **`MyIntranet` (front-man)** — carries the `persistent_memory` middleware and the `CallAgent` tool, and runs the
  two-step routing policy above.
- Can call IT, Finance, Procurement, Legal, HR, and URLProvider agents (unchanged).

**Note**: it is assumed that the agent coordination mechanism is AAOSA.

---
