# Enterprise Architect Advisor

The **Enterprise Architect Advisor** is a 12-agent, two-phase advisory network for enterprise IT
transformation and cloud modernisation. It combines structured intake, evidence-gated specialist
routing, peer review, and governed document generation to produce four architecture deliverables
in a single conversational session.

---

## File

[enterprise_architect_advisor.hocon](../../../registries/nagarjunvk/enterprise_architect_advisor.hocon)

---

## Description

A hierarchical multi-agent network built around three phases of interaction:

- **Phase 1 — Intake & Confirmation**: The Chief Enterprise Architect extracts the user's
  context via the Context Analyst and the Decision Router's plausibility pass, then generates
  a targeted intake template that asks only the questions whose specialist domains have a
  concrete signal. Already-confirmed fields and Comparison Fields (scored options) are never
  re-asked.

- **Phase 2 — Full Analysis**: After the user replies (or says "go ahead"), the network runs
  a full multi-specialist analysis. The Decision Router evidence-gates which of the eight domain
  specialists to invoke and issues all their tool calls concurrently. The Critique Board and
  Governance Reviewer then provide a peer review pass. Four deliverable files are written to disk.

- **Phase 3 — Scoped Follow-Up**: Follow-up questions are classified by the Decision Router and
  routed to the one or two most relevant specialists. New information triggers a targeted document
  update (Phase 3B) rather than re-running the full analysis.

**Key Capabilities:**

- **Evidence-Gated Routing**: Specialists are only activated when at least one of their domain
  fields was confirmed or signalled by the user — no domain analysis is invented.
- **Dynamic Intake Template**: Suppresses confirmed and comparison fields automatically; the
  number of intake questions adapts to exactly what is missing.
- **Concurrent Specialist Execution**: All selected specialists are called in a single response
  turn, enabling parallel execution by the framework.
- **Scored Decision Matrix**: Each specialist produces a weighted option table (100-point rubric)
  covering Business Alignment, Technical Fit, Migration Complexity, Operational Simplicity,
  Security & Compliance, Cost Efficiency, and Future Readiness.
- **Four Structured Deliverables**: `executive_summary.md`, `architecture_decision_matrix.md`,
  `detailed_findings.md`, and `roadmap.md` — written to
  `outputs/enterprise_architect_advisor/<project-name>/`.
- **Assumption Transparency**: Every field defaulted by the network is labelled "Assumed Needed"
  and surfaced explicitly in `executive_summary.md`.
- **Live Document Updates**: Phase 3B re-runs the affected specialists and regenerates only the
  impacted files, appending an Amendment Log.
- **Concurrency Telemetry**: Per-specialist wall-clock start and end times are recorded in
  `sly_data["ea_call_ledger"]` via `CallLedgerMiddleware`.

---

## Example Conversation

### Human

```text
We want to move our on-premises Java monolith to the cloud. We use SQL Server for the
database and our compliance team has flagged SOC 2 requirements.
```

### AI (chief_enterprise_architect)

```text
[L0 (1) · L1 (9) · L2 (2) | PHASE 1 — INTAKE & CONFIRMATION]

**Confirmed from your brief:**
• **Transformation intent**: Cloud migration of an on-premises Java monolith
• **Backend technology**: Java (backend confirmed)
• **Database engine**: SQL Server
• **Compliance requirement**: SOC 2

**Not yet signalled**: AI / ML enablement scope (will be skipped unless you mention it).

---
To make sure I get this right, please fill in what you know.
It is fine to write "not sure" for anything — I will use a reasonable default and flag it.

1. Is this a pure infrastructure lift-and-shift (move the servers as-is), or do you also
   want to modernise the application itself (e.g., break the monolith apart, containerise,
   re-platform)?
2. Current frontend technology (framework / language used in the browser tier)?
3. Current architecture pattern — is the Java monolith a single deployable WAR/JAR, or
   does it already have some modular structure?
4. Approximate scale / user base (daily active users, transaction volumes, or team size)?
5. Current DR / backup approach and acceptable downtime for the migration cutover?
6. Any existing Windows Server or SQL Server licensing agreements (Software Assurance,
   Enterprise Agreement) that could qualify for Azure Hybrid Benefit discounts?
7. Budget or cost-reduction target, if any?

Project name (used as the output folder for your deliverables):
  📁 java-monolith-cloud-migration
Change it if you like, or leave it as-is.

Reply with your answers, or just say "go ahead" and I will proceed with reasonable
assumptions for anything left blank.
```

### Human

```text
We want to modernise, not just lift-and-shift. Frontend is React. About 5,000 daily users.
No formal DR plan yet. We have an Enterprise Agreement with Microsoft. Go ahead for the rest.
```

### AI (chief_enterprise_architect)

```text
[L0 (1) · L1 (9) · L2 (2) | PHASE 2 — FULL ANALYSIS COMPLETE]

Analysed a full cloud-modernisation programme for a Java monolith (React frontend, SQL Server,
SOC 2 compliance, ~5,000 DAU, Microsoft Enterprise Agreement). All eight specialist domains had
signals and were activated. The headline recommendation is Azure as the primary cloud platform —
the existing Microsoft EA and SQL Server licensing make Azure Hybrid Benefit savings significant,
and SOC 2 Type II attestation is straightforward on Azure's compliance portfolio. The
top-recommended migration strategy is Replatform (containerise the monolith into Azure Kubernetes
Service) rather than a full refactor, balancing modernisation benefit against delivery risk for
a 5,000-DAU workload. One major governance concern was flagged: the absence of a DR plan requires
an RPO/RTO definition before the Foundation phase begins.

Full documents saved to: outputs/enterprise_architect_advisor/java-monolith-cloud-migration/

Here are some questions you might want to explore next:
• What Azure SQL Database tier (General Purpose vs Business Critical) is right for our SQL Server
  workload, and does the EA licensing cover managed instance?
• How should we approach decomposing the Java monolith — strangler-fig pattern or domain-driven
  bounded contexts?
• What SOC 2 controls are already covered by Azure's shared responsibility model, and what do we
  own?
• How does Azure Hybrid Benefit interact with our EA for both Windows Server and SQL Server licences?
• What does the Phase 2 Foundation / Landing Zone look like — which Azure services should we
  provision first?
• The critique board flagged network egress costs as a risk — how material is that at 5,000 DAU?
Or say 'update the docs' after giving me new information and I will regenerate the affected files.

<sub>Agents this run: context_analyst, decision_router_agent, cloud_strategy_architect,
application_architect, data_architect, integration_architect, security_architect,
operations_architect, finops_architect, critique_board, governance_reviewer, document_writer
(12/12)</sub>
```

---

## Architecture Overview

### L0 — Frontman: `chief_enterprise_architect`

- Sole interface between the user and the advisory network across all three phases.
- Runs the Phase 1 intake algorithm (confirmed-field suppression, domain-gated question selection).
- Generates and persists a project name used as the `session_id` for all four deliverable files.
- After Phase 2, orchestrates critique, governance, and document writing.
- In Phase 3, classifies follow-up questions and routes them to the correct specialist without
  re-running the full analysis.

**Direct tools called by chief**: `context_analyst`, `decision_router_agent`, `critique_board`,
`governance_reviewer`, `document_writer`

---

### L1 — Support Agents

#### `context_analyst`
Extracts and classifies all business and technology fields from user input. Tags every field as
**Confirmed**, **Assumed Needed**, **Comparison Needed**, or **Unknown**. Applies Default Assumption
Rules in `phase="full"` (e.g., Angular for frontend, SQL Server for database when not stated).
Returns a structured markdown table and an "Assumed Defaults Applied" summary.

#### `decision_router_agent`
Evidence-gate dispatcher with three modes:
- **`preview`** (Phase 1): returns a plausibility list of specialist domains without executing any
  specialist.
- **`full`** (Phase 2): applies the evidence gate, outputs a ROUTING PLAN, then issues all selected
  specialist calls concurrently in a single response turn.
- **`followup`** (Phase 3): classifies a follow-up question against domain signals and returns a
  FOLLOW-UP ROUTING block (Matched domain(s), Confidence, Reason) without executing specialists.

---

### L1 — Domain Specialists (called by `decision_router_agent` in Phase 2)

Each specialist is evidence-gated: it only runs when at least one field in its domain has a
confirmed signal. All specialists use a shared 100-point scoring rubric and produce a lean option
table with a full weighted breakdown for the top-recommended option.

| Specialist | Domain |
|---|---|
| `cloud_strategy_architect` | Target cloud platform, migration strategy, cloud adoption drivers |
| `application_architect` | App hosting model, architecture patterns, containerisation, modernisation |
| `data_architect` | Database targets, data-platform strategy, analytics, ETL |
| `integration_architect` | APIs, messaging, ESB, event-driven patterns, ETL integrations |
| `security_architect` | Identity/IAM, network security, compliance controls (HIPAA, SOC 2, PCI, GDPR…) |
| `operations_architect` | DevOps/CI-CD, IaC, observability, DR, VM/server migration cutover |
| `finops_architect` | Cost modelling, Azure Hybrid Benefit / licensing, FinOps practices |
| `ai_architect` | AI/ML/GenAI enablement scope — only when explicitly signalled |

**Special rule**: `operations_architect` and `finops_architect` are always plausible when any
infrastructure or hosting change is in scope, even if not named explicitly.

---

### L2 — Review Board

#### `critique_board`
Reviews all specialist findings for architecture quality, technical risk, and modernisation
coherence. Flags inconsistencies across domains (e.g., a containerisation recommendation that
conflicts with the chosen database target).

#### `governance_reviewer`
Reviews findings for compliance posture and cost governance. Distinguishes **MAJOR** concerns
(trigger a specialist re-run in Phase 2 Step 9) from **minor** concerns (surfaced as Open
Questions in `detailed_findings.md`).

---

## Coded Tools

#### `DocumentWriter`

[document_writer.py](../../../coded_tools/industry/enterprise_architect_advisor/document_writer.py)

Writes or updates the four deliverable files to `outputs/enterprise_architect_advisor/<session_id>/`.
Called by `chief_enterprise_architect` four times in Phase 2 (mode `"create"`) and once or more in
Phase 3B (mode `"update"`).

Permitted filenames: `executive_summary.md`, `architecture_decision_matrix.md`,
`detailed_findings.md`, `roadmap.md`.

The `session_id` parameter maps to the project name generated in Phase 1 and determines the output
subfolder. If the LLM passes an explicit `null` for `session_id`, the tool falls back to a
timestamp-based folder name.

---

## Middleware

#### `CallLedgerMiddleware`

[call_ledger_middleware.py](../../../middleware/enterprise_architect_advisor/call_ledger_middleware.py)

Attached to each of the eight domain specialists. Records per-specialist wall-clock execution
windows in `sly_data["ea_call_ledger"]` — a list of `{agent_name, start_time, end_time}` entries
in ISO-8601 UTC format. A shared `asyncio.Lock` stored in `sly_data["ea_ledger_lock"]` protects
the list from torn writes when specialists run concurrently.

Also sets `sly_data["ea_ran_<agent_name>"] = True` as a convenience flag for downstream code that
needs to check which specialists actually executed.

---

## Debugging Hints

Check the logs for:

- **Phase 1 intake template correctness**: verify that no "Confirmed" field appears as a question,
  and no Comparison Field (migration strategy, hosting model, etc.) is asked — these are scored
  as options in Phase 2 and must never be posed as blank questions.
- **Decision Router plausibility pass** (`mode="preview"`): confirm the PLAUSIBILITY LIST lists
  the expected domains as plausible. If an expected specialist is missing, check whether the
  relevant context fields were tagged Confirmed or Comparison Needed by `context_analyst`.
- **Concurrent specialist calls**: in Phase 2 the ROUTING PLAN should list all selected specialists,
  and the framework should show them executing in parallel (not one-by-one).
- **Document writer session folder**: verify all four files land in the same
  `outputs/enterprise_architect_advisor/<project-name>/` subfolder. Mismatched `session_id`
  arguments between calls will scatter files across multiple folders.
- **Governance re-run**: if `governance_reviewer` flags a MAJOR concern, the affected specialist
  should be called a second time. Check the logs to confirm the re-run happened.
- **Phase 3 topic continuity**: for back-to-back follow-up questions on the same domain, the
  Decision Router should apply a topic-continuity bias (via `previous_specialist`) rather than
  reclassifying from scratch on every turn.

---

## Testing

This agent network includes test coverage across all three interaction phases:

- [fixture1_rich_input_broad_routing.hocon](../../../tests/fixtures/nagarjunvk/enterprise_architect_advisor/fixture1_rich_input_broad_routing.hocon)
  — Phase 1: rich input with confirmed fields (Azure, HIPAA) verifies that already-confirmed fields
  are not re-asked in the intake template.

- [fixture2_vague_input_scope_question.hocon](../../../tests/fixtures/nagarjunvk/enterprise_architect_advisor/fixture2_vague_input_scope_question.hocon)
  — Phase 1: vague input verifies that the agent asks a scope-clarifying question rather than
  launching directly into a full analysis.

- [fixture3_infra_only_domain_gated_intake.hocon](../../../tests/fixtures/nagarjunvk/enterprise_architect_advisor/fixture3_infra_only_domain_gated_intake.hocon)
  — Phase 1: infrastructure-only input (VM migration, no application/data/integration signals)
  verifies that application, data, and integration questions are suppressed by the domain gate.

- [fixture4_compliance_signal_security_routing.hocon](../../../tests/fixtures/nagarjunvk/enterprise_architect_advisor/fixture4_compliance_signal_security_routing.hocon)
  — Two-turn: SOC 2 compliance signal in Turn 1 → Phase 2 verifies that `security_architect`
  runs and produces compliance-focused findings.

- [fixture5_followup_topic_continuity.hocon](../../../tests/fixtures/nagarjunvk/enterprise_architect_advisor/fixture5_followup_topic_continuity.hocon)
  — Four-turn: Phase 2 full analysis followed by two consecutive SQL Server follow-up questions,
  verifying that Phase 3 topic-continuity correctly routes both to `data_architect` without
  reclassifying from scratch.

Run tests using:

```bash
# Run all Enterprise Architect Advisor tests
pytest tests/integration/test_integration_test_hocons.py -k nagarjunvk_ea -v

# Run a single fixture
pytest tests/integration/test_integration_test_hocons.py -k "fixture2"
```
