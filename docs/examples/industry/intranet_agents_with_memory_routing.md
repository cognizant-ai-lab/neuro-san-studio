# Intranet Agents With Memory Routing

**Intranet Agents With Memory Routing** is the [Intranet Agents With Tools](intranet_agents_with_tools.md) network with
one added capability: the top-level "front-man" agent **learns which agents to route a query to, and remembers it**.

The first time it sees an inquiry of a given kind, it uses AAOSA to discover which down-chain agents can fulfill it. It
then caches that route (the fulfilling leaf agents and the parameters they need) in persistent memory under a
generalized topic. On later inquiries of the same kind, it gathers the required parameters up front and calls those
leaf agents directly, skipping the AAOSA discovery round-trips. This saves a significant number of tokens on repeat
inquiries.

Only the route is cached: a reusable, generalized topic. No user-specific information is ever stored in memory.

## File

[intranet_agents_with_memory_routing.hocon](../../../registries/industry/intranet_agents_with_memory_routing.hocon)

---

## What is different from Intranet Agents With Tools

The department and leaf agents (IT, Finance, Procurement, Legal, HR, and their sub-agents and coded tools) are
unchanged; only the routing changes. Everything new lives on the front-man agent, `MyIntranet`:

- **Persistent memory middleware.** `PersistentMemoryMiddleware` is attached to `MyIntranet` and auto-registers a
  `persistent_memory` tool (backed by the `mem0` store) with the `create`, `read`, `list`, and `delete` operations
  enabled. The agent uses it to store routing state, not personal facts.
- **A `CallAgent` tool.** On a cache hit, the front-man uses `CallAgent` to call the cached leaf agents directly by
  name instead of walking the AAOSA tree again.
- **A two-step routing policy** in the front-man's instructions (see below).
- **A custom memory preamble** supplied from HOCON (see [Overriding the memory preamble](#overriding-the-memory-preamble)).

---

## How routing works

The front-man runs **Step 1 first on every inquiry**, and only falls back to Step 2 when the cache has no matching
route.

### Step 1: Route via the memory cache

1. Call `persistent_memory` with `operation="list"` to get all cached topic names.
2. Using its own judgment, decide whether any cached topic (e.g. `schedule_absence`) matches the current inquiry.
3. On a match, `read` that topic to recover its `leaf_agents` and required `parameters`. On no match, go to Step 2.
4. Cross-check the required parameters against what the user has already provided. If any are missing, ask for all of
   them in a single message and wait for the user's reply.
5. Once all parameters are in hand, call each cached leaf agent with `CallAgent` using `mode="Fulfill"`.
6. If a leaf agent reports that more information is needed, collect it from the user and call that agent again with
   `mode="Follow up"`, repeating until it is satisfied.
7. Compile the leaf agents' answers into a single natural-language response for the user.

### Step 2: Route via Determine (only on a cache miss)

1. Call the department-level down-chain agents with `mode="Determine"` to find which can handle the inquiry.
2. Follow up and fulfill through the tree (calling leaf agents with `mode="Fulfill"`) until the inquiry is answered.
3. Read the `Handled by:` line from the responses, generalize the inquiry into a short `snake_case` topic
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

`PersistentMemoryMiddleware` prepends a short "you have a memory tool" preamble to the system prompt that tells the LLM
when and how to use the `persistent_memory` tool. Its built-in default is aimed at a personal-fact store. This network
uses memory as a routing cache instead, so it supplies its own preamble via the `preamble` key inside `memory_config`,
rather than editing the shared default:

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

## Example conversation

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

**Note:** the agent coordination mechanism is assumed to be AAOSA. For full details on the department and leaf agents,
refer to [Intranet Agents With Tools](intranet_agents_with_tools.md).
