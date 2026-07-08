# Intranet Agents With Memory Routing

The **Intranet Agents With Memory Routing** network is the [Intranet Agents With Tools](intranet_agents_with_tools.md)
network with one extra capability: the top-level "front-man" agent **learns which agents to route queries to** and
remembers it.

Normally, every inquiry walks the full AAOSA tree: the front-man asks its down-chain agents who can help, follows up
through the tree, and only then fulfills the request. That discovery costs several LLM round-trips on every inquiry,
even for a kind of question it has already answered before.

This network avoids repeating that work. The **first** time it sees an inquiry of a given kind, it still runs the full
AAOSA discovery, but it then records the result as a reusable **route** in persistent memory: which leaf agents
fulfilled the request and which parameters they needed. It stores this under a generalized topic, so the route is
decoupled from the one specific request that produced it.

The **next** time a similar inquiry comes in, the front-man looks up that topic, collects the required parameters from
the user up front, and calls the recorded leaf agents directly, skipping the AAOSA discovery round-trips (and the
tokens they cost). Only the route is stored, the leaf-agent names and the parameter names; the user's own values are
never saved.

For example, the first time a user asks to book time off, the front-man discovers through AAOSA that
`AbsenceManagement` handles it and needs a start date and an end date. It saves a topic such as `schedule_absence`
with `leaf_agents: ["AbsenceManagement"]` and `parameters: ["start_date", "end_date"]`. When any user later asks to
take a sick day or a vacation, it matches `schedule_absence`, asks the user for the dates, and calls
`AbsenceManagement` directly, with no rediscovery.

## File

[intranet_agents_with_memory_routing.hocon](../../../registries/industry/intranet_agents_with_memory_routing.hocon)

---

## What is different from Intranet Agents With Tools

The department and leaf agents are unchanged; only the routing has changed. Everything new lives on the front-man
agent, `MyIntranet`:

- **Persistent memory middleware.** The
  [`PersistentMemoryMiddleware`](../tools/persistent_memory_mem0.md) is attached to `MyIntranet` and auto-registers a
  `persistent_memory` tool (backed by the `mem0` store) with the `create`, `read`, `list`, and `delete` operations
  enabled. It is a tool the agent uses for routing state, not a personal-fact store.
- **A `CallAgent` tool.** On a cache hit, the front-man uses
  [`CallAgent`](../../../neuro_san_studio/coded_tools/call_agent.py) to call the cached leaf agents directly by
  name instead of walking the AAOSA tree again.
- **A two-step routing policy** in the front-man's instructions (see [How routing works](#how-routing-works)).
- **A custom memory middleware tool preamble** supplied from HOCON (see [Overriding the memory preamble](#overriding-the-memory-preamble)).

---

## How routing works

On **every** inquiry the front-man runs Step 1 first:

### Step 1: Route via memory cache

1. Call `persistent_memory` with `operation="list"` to get all cached topic names.
2. Judge whether any cached topic (e.g. `schedule_absence`) matches the current inquiry.
3. On a match, `read` that topic to recover its `leaf_agents` and required `parameters`.
4. Cross-check the required parameters against what the user has already provided. If any are missing, ask for all of
   them in a single message and wait for the user's reply.
5. Once all parameters are in hand, call each cached leaf agent with `CallAgent` using `mode="Fulfill"`.
6. If a leaf agent needs more information, collect it from the user and call that agent again with `mode="Follow up"`,
   repeating until it is satisfied.
7. Compile the leaf agents' answers into a single response for the user.

### Step 2: Route via Determine (only if there is no relevant cache present)

1. Call the department-level down-chain agents with `mode="Determine"` to find who can handle the inquiry.
2. Determine / Follow up / Fulfill through the tree until the inquiry is answered.
3. Read the `Handled by:` line from the leaf agents, generalize the inquiry into a short `snake_case` topic
   (e.g. `schedule_absence` covers sick day, vacation, and PTO, not `sick_day_tuesday`), and `create` a memory entry:

   ```json
   {
       "leaf_agents": ["<verbatim names from the Handled by: line>"],
       "parameters": ["<required param name>"]
   }
   ```

The next inquiry of the same kind is then served straight from Step 1.

---

## Overriding the memory preamble

`PersistentMemoryMiddleware` adds a default short "you have a memory tool" preamble to the system prompt to inform the
LLM on when and how to use the persistent memory tool. This network uses memory as a routing cache instead, so it
supplies its own preamble via the `preamble` key inside `memory_config`, rather than editing the shared default:

```hocon
"middleware": [
    {
        "class": "middleware.persistent_memory.persistent_memory_middleware.PersistentMemoryMiddleware",
        "args": {
            "origin_str": true,
            "memory_config": {
                "storage": { "backend": "mem0" },
                "enabled_operations": ["create", "read", "list", "delete"],
                "preamble": """
You have a 'persistent_memory' tool for facts that must survive across turns and sessions.
...
                """
            }
        }
    }
]
```

When `preamble` is omitted, the middleware falls back to its built-in default.

---

For more details on the functionality of the intranet agent network, please refer to
[Intranet Agents With Tools](intranet_agents_with_tools.md).
