# Intranet Agents With Jev Routing

The **Intranet Agents With Jev Routing** network is the
[Intranet Agents With Tools](intranet_agents_with_tools.md) network, unchanged, with a fast path in front of its
AAOSA routing. Before the front man's LLM runs, the
[`JevToolSelectorMiddleware`](../../../middleware/jev_tool_selector_middleware.py) asks
[Jev](https://typesafe.ai/), TypeSafe AI's typed-decision model, which department handles the latest message in
the context of the conversation. When Jev is confident and the message is not ambiguous, the middleware dispatches
an AAOSA `Fulfill` (or `Follow up`) call to that department itself and the LLM only writes the answer. When Jev is
not confident, finds the message ambiguous, or sees no routing decision at all, the turn runs exactly as in
Intranet Agents With Tools: the front man's own AAOSA instructions, with the five department heads as its tools,
discover the responsible department.

Jev is not an LLM: it does not generate text. Given a state and typed questions it returns, in a few hundred
milliseconds, the chosen option with a probability for every option and a confidence score. The decision costs no
LLM call, and it is only taken when it is clear; everything else keeps the behavior of the original network.

Disabled by default: it requires `pip install typesafe-sdk` and the `TYPESAFE_API_KEY` environment variable.

---

## File

[intranet_agents_with_jev_routing.hocon](../../../registries/industry/intranet_agents_with_jev_routing.hocon)

---

## What is different from Intranet Agents With Tools

- The front man, the five department heads (IT, Finance, Procurement, Legal, HR), the 15 department agents, their
  descriptions, instructions and the HCM coded tools are the same (the coded tools are referenced by their fully
  qualified class names, as the memory-routing variant does). The front man keeps its AAOSA instructions.
- Because a routed turn bypasses the head, anything only the head knows is not available on the fast path: in
  this network the IT head's instructions say that IT requests need a GSD ticket, and Security and Networking do
  not. A routed VPN question therefore gets Networking's answer without the GSD pointer, while the fallback path
  goes through IT and gets it. Two ways to keep such knowledge: give it to the department agents too, or list the
  heads rather than the departments in `candidates` (one Jev decision then saves the front man's `Determine`
  round-trips but not the head's).
- The 15 department agents are added to the front man's `tools`, next to the heads and `URLProvider`, so a
  Jev decision can be dispatched to a department directly. The middleware decides, per turn, which of these tools
  the LLM sees: on a routed turn only the chosen department and `URLProvider`; on a fallback turn only the five
  heads and `URLProvider`, i.e. the original network's tool list.
- The front man carries the `JevToolSelectorMiddleware`. On a routed turn its system prompt is replaced by
  `routed_instructions` ("the responsible department has already been consulted: its answer is in the tool
  result"); on a fallback turn its own AAOSA instructions are used untouched.
- `max_steps` and `max_execution_seconds` are set at the network level, at neuro-san's default values (10,000
  steps, 300 s), so a fallback turn runs with exactly the bounds the baseline runs with (a tighter 180 s limit
  cut an AAOSA fallback turn short in the data-driven tests).
- Each Jev decision (path taken, department, confidence, ambiguity, probabilities, latency) is returned to the
  client in `sly_data`: `jev_turn` for the current turn, `jev_tool_selection` for the whole conversation, and
  `jev_current_department` for the department of the last routed turn.

---

## How routing works

The middleware is declared on the front man:

```hocon
"middleware": [
    {
        "class": "middleware.jev_tool_selector_middleware.JevToolSelectorMiddleware",
        "args": {
            "instructions": "Given the `conversation` (latest user message last) and `current_department` (the department that handled the previous message, or none), which department handles the latest user message?",
            "candidates": ["Security", "Networking", "Budgeting", "...", "Payroll", "AbsenceManagement"],
            "reserved_criteria": {
                "same": "The latest message continues the exchange with `current_department`: ...",
                "none": "The latest message needs no department: a greeting, thanks, small talk, ...",
                "unclear": "The latest message is too vague to route, or it needs more than one department."
            },
            "ambiguous_instructions": "Does the latest user message in `conversation` concern more than one department, or is it too vague to route to a single department?",
            "ambiguous_threshold": 0.7,
            "min_confidence": 0.75,
            "on_unclear": "aaosa",
            "fallback_tools": ["IT", "Finance", "Procurement", "Legal", "HR"],
            "always_include": ["URLProvider"],
            "mode": "dispatch",
            "dispatch_args": { "inquiry": "$user_message", "mode": "Fulfill" },
            "followup_args": { "inquiry": "$conversation", "mode": "Follow up" },
            "routed_instructions": ${routed_instructions},
            "history_turns": 6,
            "timeout_seconds": 3,
            "fail_open": true,
            "sly_data": null,
            "journal": null,
            "origin_str": null
        }
    }
]
```

On the first model call of a user turn, the middleware:

1. Builds one Jev `choice` question whose options are the 15 candidate departments, each described by its
   `function.description` (the text that already tells the LLM when to call it), plus three reserved options:
   `same` (the message continues the exchange with the current department), `none` (no department is needed)
   and `unclear` (too vague, or more than one department). A yes/no question asks whether the message is
   ambiguous.
2. Sends as state the last `history_turns` user and assistant messages of the conversation and the
   `current_department` of the previous routed turn, and gets back the chosen option, its confidence, the
   probability of every option and the ambiguity probability (one call, typically 200 to 500 ms).
3. Resolves the **path** of the turn:
   - `jev`: a department, with confidence at least `min_confidence` and ambiguity below `ambiguous_threshold`.
     In `dispatch` mode the middleware synthesizes the tool call `{"inquiry": <message>, "mode": "Fulfill"}` and
     returns it **without calling the LLM**; the agent loop executes it like any model-requested tool call.
   - `same`: Jev picked `same`, or picked the current department again. The call is a `Follow up` and, because
     down-chain agents keep no history between turns, the inquiry is the recent conversation
     (`$conversation`) rather than the latest message alone.
   - `none`: the LLM answers from the conversation with only `URLProvider` available.
   - `aaosa`: Jev picked `unclear`, or the confidence is below `min_confidence`, or the ambiguity probability
     reaches `ambiguous_threshold`. The LLM runs with the five heads and `URLProvider` and its own AAOSA
     instructions, which is exactly a turn of Intranet Agents With Tools. (`on_unclear` can instead be `ask`,
     which has the LLM ask the user which of the most likely departments they mean, or `else_tool`.)
4. Shapes every later model call of the same turn to the path (tools and system prompt), and rejects at
   execution time any tool call outside the path, the same enforcement neuro-san's own
   `LlmConfigToolSelectorMiddleware` applies.
5. Journals the decision (visible in the nsflow chat panel as `MyIntranet > JevToolSelectorMiddleware`) and records
   it in `sly_data`.

If Jev cannot be reached (connection, rate limit, server error), the middleware fails open: the turn takes the
`aaosa` path, so a Jev outage degrades to the original network rather than to an error (set
`"fail_open": false` to fail the turn instead). Authentication and validation errors propagate, since they are
configuration mistakes.

`current_department` comes from `sly_data`, which neuro-san's clients send back with the next turn; without it
(a client that drops `sly_data`) the `same` path cannot be taken and a follow-up is routed on the conversation
text alone.

The alternative `"mode": "narrow"` keeps the LLM in the routing step: the tool list is narrowed to Jev's pick and
`tool_choice` forces it, while the LLM fills in the arguments. `dispatch` is the mode that removes the LLM call.

---

## Comparison with AAOSA routing

Two experiments were run against the same server (`gpt-5.2`, `jev-1.13.0`), with neuro-san's own token
accounting for "LLM calls", "Tokens" and "LLM cost". The three configurations share the department agents,
their instructions and the HCM coded tools:

- **AAOSA** - `industry/intranet_agents_with_tools`, unchanged.
- **Jev-only** - a benchmark-only variant with a flat front man (the 15 departments, no heads) where every turn
  is dispatched to Jev's pick over the latest message, with no fallback. It is this network's hocon with the
  reserved options, the ambiguity question, the conversation state and `fallback_tools` removed, and is what a
  "replace routing with a decision model" design does.
- **Jev routing** - this network.

### Clear queries: the fast path

Same five queries, three runs each, medians, measured after the edge-case run on the same server. **LLM
selector** is the flat network routed by neuro-san's `LlmConfigToolSelectorMiddleware` (an extra `gpt-5.2`
structured-output call narrows the tools to one); it is not shipped. Jev's own cost is not in the table: at
$0.042 per million input tokens a decision over 15 department descriptions costs about $0.0001.

| Query | Network | Wall time | LLM calls | Tokens | LLM cost | Jev time |
|---|---|---|---|---|---|---|
| How many days of vacation do I have left? | AAOSA | 24.1 s | 11 | 13,963 | $0.039 | – |
|  | LLM selector | 13.9 s | 8 | 7,336 | $0.017 | – |
|  | **Jev routing** | **6.4 s** | **4** | 4,428 | $0.011 | 0.17 s |
| Schedule vacation from December 20 to December 31 | AAOSA | 22.0 s | 10 | 13,481 | $0.043 | – |
|  | LLM selector | 14.3 s | 9 | 8,377 | $0.019 | – |
|  | **Jev routing** | **7.3 s** | **5** | 4,817 | $0.012 | 0.17 s |
| I need to take a sick day tomorrow | AAOSA | 29.5 s | 17 | 22,201 | $0.072 | – |
|  | LLM selector | 15.5 s | 8 | 7,327 | $0.018 | – |
|  | **Jev routing** | **7.9 s** | **5** | 4,862 | $0.013 | 0.21 s |
| How do I check my pay stub? | AAOSA | 81.0 s | 31 | 36,365 | $0.126 | – |
|  | LLM selector | 16.1 s | 5 | 4,876 | $0.018 | – |
|  | **Jev routing** | **7.1 s** | **3** | 2,512 | $0.009 | 0.25 s |
| How do I get VPN access when working from home? | AAOSA | 63.1 s | 18 | 23,760 | $0.086 | – |
|  | LLM selector | 12.4 s | 5 | 4,302 | $0.013 | – |
|  | **Jev routing** | **13.4 s** | **3** | 3,378 | $0.016 | 0.17 s |
| **All five queries (median of 15 runs)** | AAOSA | 38.4 s | 17 | 22,201 | $0.072 | – |
|  | LLM selector | 14.9 s | 7 | 7,055 | $0.018 | – |
|  | **Jev routing** | **7.3 s** | **4** | 4,220 | $0.012 | 0.17 s |

Jev routing took the `jev` path in all 15 runs (AbsenceManagement for the three leave questions, Payroll,
Networking): the reserved options and the ambiguity question did not pull any of these queries off the fast
path. No request timed out. On the VPN query the LLM selector's wall time was lower than Jev routing's (12.4 s
vs 13.4 s) although Jev routing made fewer LLM calls (3 vs 5); the other four queries favor Jev routing on
every column. Wall time includes LLM latency, which varies between runs (the pay-stub query took 44 s and
19 s on AAOSA in the edge-case run, 81 s here).

#### Keeping the graph identical: heads as candidates

The 15 direct edges from the front man to the departments exist only so the middleware can dispatch to them;
on a fallback turn the LLM is handed the baseline's tools (the turn record's `llm_tools` field shows
`["Finance", "HR", "IT", "Legal", "Procurement", "URLProvider"]`; on a routed turn `["Payroll", "URLProvider"]`).
If the network definition itself must stay byte-identical, list the five heads as `candidates` instead and keep
the front man's tool list unchanged. Jev then picks the head and the head still runs its own `Determine` over
its departments, so the fast path keeps head-level knowledge (the IT head's GSD pointer) but costs the head's
round-trips. Measured on the same five queries (benchmark-only variant, same middleware settings):

| Query | Wall time | LLM calls | Tokens | LLM cost | Jev time | Jev pick |
|---|---|---|---|---|---|---|
| How many days of vacation do I have left? | 15.9 s | 11 | 12,387 | $0.028 | 0.22 s | HR |
| Schedule vacation from December 20 to December 31 | 10.7 s | 6 | 6,715 | $0.018 | 0.17 s | HR |
| I need to take a sick day tomorrow | 17.3 s | 14 | 14,738 | $0.040 | 0.29 s | HR |
| How do I check my pay stub? | 13.3 s | 7 | 6,672 | $0.020 | 0.20 s | HR |
| How do I get VPN access when working from home? | 24.1 s | 8 | 11,100 | $0.041 | 0.16 s | IT |
| **All five queries (median of 15 runs)** | 15.6 s | 8 | 8,304 | $0.028 | 0.20 s | |

Median over the five queries: 15.6 s / 8 LLM calls / $0.028, against 7.3 s / 4 / $0.012 for this network,
14.9 s / 7 / $0.018 for the LLM selector and 38.4 s / 17 / $0.072 for AAOSA. Jev picked the same head in all
three runs of every query.

### Edge cases: where a single decision over the latest message is not enough

Eight scripted conversations, two runs each, carrying `chat_context` and `sly_data` between turns as neuro-san's
clients do. Every turn was checked from the raw stream before it was counted: the middleware's journaled
decision matches the `sly_data` record, the department call the front man actually made (`Invoking: ... with
{"inquiry": ..., "mode": ...}`) matches the path, no call outside the path executed, and the turn ended without
an error. Three samples hit a provider stall or a DNS failure on the test machine and were re-run; the raw data
of every run, including the excluded ones, is kept with the PR notes.

#### "How do I check my pay stub?" (control)

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 14-22 | 19-44 s | answers |
| Jev-only | Payroll 1.0 -> Fulfill | 3 | 9 s | answers |
| Jev routing | `jev` -> Payroll 1.0 -> Fulfill | 3-4 | 9-12 s | answers |

#### "I just got married. What do I need to update?"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 30-33 | 44-103 s | benefits, payroll, IT covered |
| Jev-only | Benefits 0.77-0.82 -> Fulfill | 3-4 | 20-22 s | **benefits-only** checklist |
| Jev routing | `unclear`, ambiguity 0.91-0.92 -> AAOSA path | 25-26 | 42-46 s | name change / benefits / payroll |

#### "Where can I find the cafeteria menu?"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 18-20 | 16-19 s | invents a menu page |
| Jev-only | Benefits 0.71-0.72 -> Fulfill | 3 | 7 s | **Benefits agent** invents a menu page |
| Jev routing | `none` 0.45-0.47 (vs `unclear` 0.4x) | 2-4 | 4-6 s | invents a menu page, no department |

#### "Can you help me with something?"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 28-30 | 30-34 s | asks what you need |
| Jev-only | Networking 0.53-0.54 -> Fulfill | 3 | 9-17 s | **offers network help only** |
| Jev routing, run 1 | `unclear` 0.90, ambiguity 0.96 -> AAOSA path | 28 | 32.7 s | tree walk, asks what you need |
| Jev routing, run 2 | `unclear` 0.92, ambiguity 0.96 -> AAOSA path | 2 | 4.4 s | asks what you need, no head called |

#### "It's still not working." as the first message

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 28 | 38 s | asks which part |
| Jev-only | Networking 0.98-0.99 -> Fulfill | 3-4 | 12-17 s | **network-only** questions |
| Jev routing | `unclear` 0.94-0.95 -> AAOSA path | 28-29 | 39-67 s | asks which part (baseline + Jev call) |

#### "Hi! Thanks for the help yesterday."

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | no department | 2 | 3 s | greets back |
| Jev-only | Networking 0.65-0.66 -> Fulfill | 3 | 8-10 s | **Networking agent** greets back |
| Jev routing | `none` 1.0 | 2 | 3 s | greets back |

The two multi-turn conversations exercise the `same` path and the confidence fallback. Down-chain agents keep
no history between turns in neuro-san, so what the department receives on a follow-up decides the outcome.

#### Sick day, turn 1: "I need to take a sick day tomorrow"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 14-25 | 39-43 s | books 2026-10-03 or asks the location |
| Jev-only | AbsenceManagement 1.0 -> Fulfill | 5 | 10 s | books 2026-10-03 |
| Jev routing | `jev` -> AbsenceManagement 1.0 -> Fulfill | 4-5 | 7-11 s | books 2026-10-03 |

#### Sick day, turn 2: "Just the one day, yes - please book it"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 12-24 | 47-79 s | books 2026-10-03 or asks the location |
| Jev-only | AbsenceManagement 0.97-0.98, **sentence alone** | 4-5 | 8-11 s | `ScheduleLeaveAPI("", "")`, asks date |
| Jev routing | `same` 0.79-0.85 -> Follow up + conversation | 4 | 6-9 s | `ScheduleLeaveAPI(2026-10-03, 2026-10-03)` |

#### Sick day, turn 3: "How many vacation days will I have left after that?"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 15-18 | 33-80 s | 12.73 days |
| Jev-only | AbsenceManagement 1.0, sentence alone | 4-5 | 9-13 s | balance, then **asks which leave** |
| Jev routing | AbsenceManagement 0.65-0.68 < 0.75 -> AAOSA path | 6-26 | 15-30 s | sick leave separate, asks a detail |

#### Sick day, turn 4: "How do I check my pay stub?"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 9-14 | 21-24 s | answers |
| Jev-only | Payroll 1.0 -> Fulfill | 3 | 8-10 s | answers |
| Jev routing | `jev` -> Payroll 1.0 -> Fulfill | 3 | 6-8 s | answers |

#### VPN, turn 1: "I can't connect to the VPN from home"

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Determine tree walk | 7-11 | 23-71 s | troubleshooting steps |
| Jev-only | Networking 1.0 -> Fulfill | 3-4 | 18-20 s | troubleshooting steps |
| Jev routing | `jev` -> Networking 1.0 -> Fulfill | 3 | 12-15 s | troubleshooting steps |

#### VPN, turn 2: "It's still not working."

| Network | Routing | LLM calls | Wall time | Outcome |
|---|---|---|---|---|
| AAOSA | Fulfill with context | 7-8 | 45-62 s | asks for the error code |
| Jev-only | Networking 0.98-0.99, sentence alone | 2 | 9-11 s | **asks what "it" is** |
| Jev routing | `same` 0.80-0.84 -> Follow up + conversation | 3 | 10-11 s | asks for client and error |

What this shows:

- On a clear turn both Jev networks take the same fast path, and the hybrid costs the same as Jev-only.
- Jev-only always picks a department: Benefits for the cafeteria, Networking for a greeting, for "can you help
  me" and for a context-free "it's still not working". The picks are consistent across runs and come with
  confidences of 0.53–0.72, which is why a confidence threshold alone is not enough: a greeting was routed to
  Networking at 0.66.
- The reserved options and the ambiguity question move those turns off the fast path: `unclear` for the
  compound and content-free messages (ambiguity 0.92–0.96), `none` for the greeting (1.0). On the fallback path
  the turn costs what AAOSA costs plus one Jev call (0.2–0.7 s); it is never cheaper than the baseline, and on
  the context-free message it is exactly the baseline (28 calls).
- Follow-ups are the case where the hybrid is both faster and more correct than Jev-only: with the conversation
  in the `Follow up` inquiry, AbsenceManagement booked the right date in both runs, while the context-free
  dispatch produced a booking with empty dates. When Jev's confidence drops on a follow-up that needs an earlier
  result (turn 3, 0.65-0.68), the fallback handles it the way AAOSA does (a tree walk of 26 calls in one run, a
  direct HR -> AbsenceManagement check of 6 calls in the other); both runs say sick leave is tracked separately.
- The fallback path is the baseline: the front man's system prompt on a fallback turn was compared with the
  baseline's, taken from the stream, and is identical (except whitespace), and the tools are the baseline's. Its
  behavior still varies between runs like the baseline's does: on the vague message it walked the tree in one
  run (28 calls) and asked back in the other (2 calls), while AAOSA walked the tree in all five of its runs on
  that message; two runs are too few to say whether that gap is real.
- The cafeteria message is a near tie between `none` (0.45-0.51) and `unclear` (0.42-0.48). In these runs `none`
  won both times (2-4 LLM calls); in an earlier run it split, and the `unclear` side costs a tree walk (about
  21 calls). Neither network has a department for it, and every configuration invented a menu page.

### Why a typed-decision model and not the LLM selector

neuro-san already ships `LlmConfigToolSelectorMiddleware` (see neuro-san's `intranet_agents_middleware.hocon`
example): before each model call an extra LLM call, with structured output, narrows the agent's tools to at most
`max_tools`, and only the advertised tools may execute. It solves the same problem as this middleware, the cost
of AAOSA's `Determine` round-trips, and it needs no extra dependency. This example uses Jev instead because:

- **No LLM call for the routing step.** The selector adds one LLM call per model call; Jev's decision is one
  HTTP call of 0.2 s and the routed department is called directly (`dispatch` mode), so a clear query costs 3-4
  LLM calls instead of 7 (table above: 7.3 s / $0.012 vs 14.9 s / $0.018 median; the LLM selector also hung once
  for 442 s in an earlier run of the same benchmark).
- **A probability for every option and a confidence score**, not just a pick. The selector returns a narrowed
  list with no measure of how sure it is, so there is nothing to threshold. Jev's distribution is what makes
  the reserved options (`same`, `none`, `unclear`), the `ambiguous` question, `min_confidence` and the fallback
  path possible, and it is returned to the client in `sly_data` for audit.
- **Consistent decisions.** Jev picked the same option in every run of every turn measured here (3 runs x 5
  queries, 2 runs x 12 edge-case turns), whereas an LLM selection is sampled.
- **Cost.** A Jev decision over 18 options costs about $0.0001; the selector's call is a full LLM request with
  all tool descriptions in the prompt.

Where the LLM selector remains the better choice: when a decision model cannot be called (no network, no key),
when the tool set changes at run time in ways the criteria cannot describe, or when the selection needs
free-form reasoning over the whole conversation rather than a classification. The two are not exclusive: Jev
can decide the department and `LlmConfigToolSelectorMiddleware` can still narrow a department's own tools.

### Reproducing the comparison

The comparison is written as standard neuro-san data-driven test cases
([test_case_hocon_reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md)):
the same interactions are run against `industry/intranet_agents_with_tools` and against this network, in
`tests/fixtures/industry/intranet_agents_with_tools/` and `tests/fixtures/industry/intranet_agents_with_jev_routing/`
(pay stub, married, cafeteria, vague, context-free follow-up, greeting, the 4-turn sick-day conversation, the
2-turn VPN conversation). The baseline cases assert the gist of the answer; the Jev cases additionally assert,
per turn, the path the middleware recorded (`jev_turn.path`, `jev_turn.department`) and the tools the LLM was
given (`jev_turn.llm_tools`). They are registered in `tests/integration/test_integration_test_hocons.py`
(`integration_industry`) and need `OPENAI_API_KEY` and `TYPESAFE_API_KEY`; the driver carries `chat_context` and
`sly_data` between interactions, so the `same` path is exercised.

The data-driven driver asserts behavior, not cost. Wall time, LLM calls, tokens and cost in the tables above
were measured with a small streaming client (not part of this contribution) that sends the same queries and
conversations to each network through a running server with `chat_filter` `MAXIMAL`, carries `chat_context`
and `sly_data` between turns, and reads the front man's `total_token_accounting` message (neuro-san's own
accounting) and the `jev_turn` record from the stream; the per-turn checks above were made on the recorded
stream events. The two
benchmark-only variants in the tables are this network's hocon with one change each and are not shipped: the
**LLM selector** replaces the middleware block with neuro-san's `LlmConfigToolSelectorMiddleware` block from
`intranet_agents_middleware.hocon` (`max_tools: 1`, `always_include: ["URLProvider"]`) on the flat front man;
**heads as candidates** keeps the baseline's front man tool list and sets `candidates` to the five heads.

---

## Setup

1. `pip install -r coded_tools/industry/intranet_agents_with_jev_routing/requirements.txt` (the `typesafe-sdk` package)
2. Get a key at [console.typesafe.ai](https://console.typesafe.ai/keys) and set `TYPESAFE_API_KEY` in your
   environment or `.env` (see `.env.example`).
3. Enable `industry/intranet_agents_with_jev_routing.hocon` in `registries/industry/manifest.hocon`.
4. Start the server as usual (`ns run` or `python -m neuro_san_studio run`) and pick
   `industry/intranet_agents_with_jev_routing` in the nsflow UI.

The Jev model version can be pinned with the `model` argument of the middleware (for example
`"model": "jev-1.13.0"`); by default the SDK uses `TYPESAFE_DEFAULT_MODEL` or `jev-latest`.

---

## Example Conversation

### Human

```text
How do I check my pay stub?
```

### AI (intranet_agents_with_jev_routing)

```markdown
To check your pay stub in MyIntranet:

1. Log in to MyIntranet.
2. Open Payroll (sometimes shown as HR / Payroll).
3. Select Pay Slips / Pay Stubs.
4. Choose the pay period/date you want.
5. Click View (open) or Download (PDF) (save/print).

If you don't see Payroll or Pay Slips/Pay Stubs, tell me (1) desktop or mobile and (2) what menu items you see
under HR/Payroll, and I'll point you to the right path.
```

The `sly_data` returned with the answer contains the decision:

```json
{
    "jev_turn": {
        "path": "jev",
        "department": "Payroll",
        "reason": "jev",
        "choice": "Payroll",
        "confidence": 1.0,
        "ambiguous": 0.0,
        "probabilities": { "Payroll": 1.0, "Benefits": 0.0, "same": 0.0, "none": 0.0, "unclear": 0.0, "...": 0.0 },
        "previous_department": null,
        "llm_tools": ["Payroll", "URLProvider"],
        "model": "jev-1.13.0",
        "latency_ms": 250,
        "mode": "dispatch"
    },
    "jev_current_department": "Payroll",
    "jev_tool_selection": [ "...one record per turn..." ]
}
```

---

## Architecture Overview

### Frontman Agent: **MyIntranet**

- Acts as the entry point for all employee inquiries
- Routes with `JevToolSelectorMiddleware`: a clear inquiry is dispatched to one of the 15 department agents and
  the front man composes the final answer; an unclear one is handled with the AAOSA protocol through the five
  department heads, as in Intranet Agents With Tools
- Can call `URLProvider` to add a link

### Department heads (fallback path only)

IT, Finance, Procurement, Legal and HR, with the same descriptions, instructions and down-chain agents as in
[Intranet Agents With Tools](intranet_agents_with_tools.md#architecture-overview).

### Department agents

Security, Networking, Budgeting, Accounting, FinancialReporting, Purchasing, VendorManagement,
ContractNegotiation, Contracts, Compliance, LegalAdvice, Immigration, Benefits, Payroll and AbsenceManagement,
unchanged; reachable directly from the front man on a routed turn and through their head on a fallback turn.

### Functional Tools

AbsenceManagement calls `ScheduleLeaveAPI` and `CheckLeaveBalancesAPI`; the front man and AbsenceManagement call
`URLProvider`. These are the coded tools of Intranet Agents With Tools, referenced by their fully qualified
class names.
