# Architecture — Enterprise Architect Advisor

## What This Project Does

Enterprise Architect Advisor is a conversational advisory system that helps enterprise teams navigate cloud
modernisation and IT transformation decisions. A user describes their current system in plain English; the advisor
confirms what it understands, asks only the questions that are genuinely missing, runs a multi-specialist analysis,
and produces four governance-ready architecture deliverables — all in a single session.

The system is built as a **12-agent Neuro SAN network**: a front-man orchestrator, nine L1 specialist agents
(including a context extractor, a router, and eight domain experts), and two L2 review agents.

---

## Agent Hierarchy

```
L0  chief_enterprise_architect          ← sole interface to the user; owns all 3 phases
 │
 ├─ L1  context_analyst                 ← extracts & classifies all fields from user input
 ├─ L1  decision_router_agent           ← evidence-gates which specialists to invoke
 │       │
 │       ├─ L1  cloud_strategy_architect
 │       ├─ L1  application_architect
 │       ├─ L1  data_architect
 │       ├─ L1  integration_architect
 │       ├─ L1  security_architect
 │       ├─ L1  operations_architect
 │       ├─ L1  finops_architect
 │       └─ L1  ai_architect
 │
 ├─ L2  critique_board                  ← cross-domain architecture quality review
 ├─ L2  governance_reviewer             ← compliance + cost governance gate
 └─     document_writer                 ← coded tool; writes 4 files to disk
```

**Total: 12 agents** (1 L0 + 9 L1 + 2 L2) + 1 coded tool

---

## Three-Phase Interaction Model

### Phase 1 — Intake & Confirmation

The `chief_enterprise_architect` calls `context_analyst` (phase=`intake`) to tag every input field as
**Confirmed**, **Unknown**, **Comparison Needed**, or **Assumed Needed**. It then calls `decision_router_agent`
(mode=`preview`) for a plausibility list of which specialist domains have signal — without executing any specialist.

A **Dynamic Intake Template** is built using four suppression rules:
1. **Confirmed-field suppression** — already-stated fields never appear as questions
2. **Comparison-field exclusion** — target cloud, migration strategy, etc. are scored as options in Phase 2, never asked
3. **Scope-clarifying question** — always asked unless scope is unambiguous
4. **Domain-gated fields** — questions appear only if their specialist domain was marked plausible

### Phase 2 — Full Analysis

After the user replies (or says "go ahead"), `context_analyst` is called again (phase=`full`) applying Default
Assumption Rules to any remaining blanks. `decision_router_agent` (mode=`full`) issues **all selected specialist
tool calls in a single response turn**, enabling parallel execution by the Neuro SAN framework.

Fixed sequence after specialists respond:
1. `critique_board` — architecture quality + cross-domain coherence review
2. `governance_reviewer` — compliance posture + cost governance gate
3. If a MAJOR concern is raised, the affected specialist re-runs with the specific concern
4. `document_writer` called 4× to write deliverables to `outputs/enterprise_architect_advisor/<project>/`
5. Chat reply: executive summary paragraph + file path + 5–7 grounded follow-up questions

### Phase 3 — Scoped Follow-up

Every subsequent message is classified by `decision_router_agent` (mode=`followup`) using:
- **Keyword matching** against specialist domain field sets
- **Topic-continuity bias** — if the prior turn matched a specialist, adjacent questions on the same topic stay with
  that specialist without reclassification (via `previous_specialist` parameter)

**Phase 3A** (Q&A): one or two specialists are called; the rest of the network is silent.  
**Phase 3B** (Doc Update): new factual information triggers specialist re-runs for only the affected sections;
files are updated with an Amendment Log appended.

---

## Evidence Gate

A specialist domain is **PLAUSIBLE** only when at least one of its fields is tagged Confirmed or Comparison Needed
by `context_analyst`. Domains with every field Unknown are skipped.

Special rule: `operations_architect` and `finops_architect` are always plausible when any infrastructure or hosting
change is in scope — VM migration, cloud move, or server consolidation implicitly triggers both.

---

## Scoring Rubric

Every specialist produces a weighted option table (100-point scale):

| Criterion | Weight |
|---|---|
| Business Alignment | 20 pts |
| Technical Fit | 20 pts |
| Migration Complexity (lower = better) | 15 pts |
| Operational Simplicity (simpler = better) | 15 pts |
| Security & Compliance | 15 pts |
| Cost Efficiency | 10 pts |
| Future Readiness | 5 pts |

The full weighted breakdown is produced only for the top-recommended option; all other options use the lean table format.

---

## Concurrency Telemetry — CallLedgerMiddleware

All eight domain specialists carry a `CallLedgerMiddleware` instance attached via the Neuro SAN middleware system.

**What it does:**
- `abefore_model` — records `start_time` (ISO-8601 UTC) on the first LLM call for that agent
- `aafter_model` — records `end_time` and upserts an entry `{agent_name, start_time, end_time}` into
  `sly_data["ea_call_ledger"]`
- Also sets `sly_data["ea_ran_<agent_name>"] = True` as a boolean convenience flag

**Thread safety:** a single `asyncio.Lock` is stored in `sly_data["ea_ledger_lock"]` and shared across all
concurrently-running specialist instances to prevent torn writes to the ledger list.

The ledger enables downstream tooling (dashboards, post-run analytics) to measure actual specialist wall-clock
execution windows and verify that specialists ran in parallel rather than sequentially.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **All specialists called in one turn** | Neuro SAN executes parallel tool calls when they are issued together; sequential calls are 3–5× slower for an 8-specialist analysis |
| **Chat reply is summary only — tables go to disk** | Keeps the conversational response readable; the full detail is available in structured files the user can share or version-control |
| **Gist evaluator uses Azure OpenAI** | Library default uses OpenAI API key; overridden via local `registries/gist.hocon` + `conftest.py` patch so tests work with Azure credentials only |
| **Dynamic intake — no fixed question list** | The number of intake questions adapts to exactly what the user stated; confirmed fields are never re-asked, which the test suite validates explicitly |
| **Topic-continuity in Phase 3** | Without it, every follow-up question would re-classify from scratch; the bias parameter routes adjacent questions to the same specialist, avoiding jarring domain switches |

---

## Agentic System Highlights

This project demonstrates several advanced agentic patterns:

- **Hierarchical delegation** — L0 orchestrates L1 specialists through L2 reviewers before writing outputs
- **Evidence-gated routing** — no domain analysis is invented; each specialist runs only with confirmed signal
- **Concurrent specialist execution** — all Phase 2 specialists invoked in a single LLM turn for parallelism
- **Shared state bulletin board** — `sly_data` used for cross-agent communication (ledger, project name, lock)
- **Middleware instrumentation** — wall-clock telemetry without modifying agent logic
- **Self-correcting loop** — governance MAJOR concerns trigger a specialist re-run before final output
- **Live document updates** — Phase 3B regenerates only affected file sections; Amendment Log provides audit trail
