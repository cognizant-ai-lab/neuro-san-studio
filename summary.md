# Project Summary — Enterprise Architect Advisor

## Problem Statement

Enterprise IT transformation and cloud modernisation projects fail at a high rate — not because of technology gaps,
but because of poor architectural decisions made early. Organisations lack access to senior enterprise architects
across all domains simultaneously: cloud strategy, application modernisation, data platforms, integration, security,
operations, and FinOps. Consultants are expensive and slow. Generic AI chatbots give generic answers that ignore the
specific technology stack, compliance context, and business constraints of the organisation.

The result: architecture decisions are made with incomplete analysis, hidden trade-offs, and no structured
documentation — leaving teams exposed to costly rework mid-project.

---

## Solution

**Enterprise Architect Advisor** is a conversational AI system that replicates the experience of engaging a full
bench of senior enterprise architects in a single session. It uses a **12-agent Neuro SAN network** to:

1. **Understand the user's specific context** through a smart intake process — extracting what is confirmed,
   what is missing, and what needs to be scored as options
2. **Run a domain-complete analysis** across up to 8 specialist domains concurrently — cloud strategy, application
   architecture, data platforms, integration patterns, security & compliance, operations, FinOps, and AI enablement
3. **Peer-review the findings** through a Critique Board and Governance Reviewer before any output is produced
4. **Write four governance-ready documents** to disk: executive summary, decision matrix, detailed findings, and roadmap
5. **Continue as a domain expert** in Phase 3 — routing follow-up questions to the right specialist and updating
   affected documents live when new information is provided

---

## How It Works

### Conversation Flow

```
User: "We're migrating our Java monolith to Azure. SQL Server database. SOC 2 required. 18 months."

Phase 1 → Chief confirms: Java, SQL Server, Azure, SOC 2, 18 months
          Asks only what's missing: hosting preference, DR approach, budget, licensing
          
User: "Go ahead with assumptions. No existing CI/CD. Team knows Docker."

Phase 2 → 7 specialists run in parallel (~60–90 seconds total):
          cloud_strategy, application, data, security, operations, finops, (no AI signal → skipped)
          → Critique Board reviews cross-domain coherence
          → Governance Reviewer flags any MAJOR compliance gaps
          → 4 documents written to outputs/enterprise_architect_advisor/java-azure-migration/
          
Chief → Executive summary in chat + follow-up questions grounded in actual findings

User: "Can SQL Server Managed Instance handle all our SQL Server Agent jobs?"

Phase 3 → Decision Router classifies: data_architect domain, High confidence
          data_architect answers with specific MI compatibility guidance
          detailed_findings.md updated with Amendment Log
```

### Key Intelligent Behaviours

**Dynamic Intake Suppression** — The system never re-asks what the user already told it. If Azure is confirmed, no
cloud-provider question appears. If HIPAA is confirmed, no generic compliance question appears. The intake template
is mathematically derived from the gap between what is known and what is missing for each plausible domain.

**Evidence-Gated Routing** — A specialist only runs when at least one field in its domain has a confirmed signal.
An infrastructure-only request (VM migration) correctly skips application, data, and integration specialist questions
— all three domains have zero signal and their questions are suppressed by the domain gate.

**Concurrent Specialist Execution** — All selected specialists are issued as tool calls in a single LLM response
turn, enabling the Neuro SAN framework to execute them in parallel. This reduces Phase 2 wall-clock time from 8–10
minutes (sequential) to 60–90 seconds (parallel) for a typical full-domain analysis.

**Concurrency Telemetry** — `CallLedgerMiddleware` attached to each specialist records per-agent start and end
times in `sly_data["ea_call_ledger"]`. This provides an auditable record confirming that specialists ran
concurrently rather than sequentially, and enables performance dashboards.

**Topic-Continuity Follow-up Routing** — The Phase 3 router applies a continuity bias: if the prior follow-up
matched `data_architect`, adjacent questions about the same database topic stay routed to `data_architect` without
reclassification. This prevents jarring domain switches mid-conversation.

**Self-Correcting Governance Loop** — If the Governance Reviewer raises a MAJOR concern about a specialist's
findings (e.g., an insufficient SOC 2 control design), the affected specialist is called again with the specific
concern before the final output is written. Minor concerns are surfaced as Open Questions in the detailed findings.

---

## Deliverables Produced

| File | Contents |
|---|---|
| `executive_summary.md` | Business problem, confirmed understanding, assumptions made, headline recommendation, what to validate next |
| `architecture_decision_matrix.md` | Decision area → recommended option → score → rationale → alternatives |
| `detailed_findings.md` | Per-specialist option tables, full weighted breakdown for winner, critique board output, governance output, risk register, open questions |
| `roadmap.md` | Five-phase delivery plan: Discovery, Foundation, Core Migration, Modernisation, Optimisation & AI Enablement |

---

## Technology Stack

| Component | Technology |
|---|---|
| Agent framework | [Neuro SAN](https://github.com/cognizant-ai-lab/neuro-san) |
| Agent config | HOCON (declarative, no agent code) |
| LLM provider | Azure OpenAI (GPT-4o / GPT-4) |
| Middleware | Custom `CallLedgerMiddleware` (Python asyncio) |
| Coded tool | `DocumentWriter` (Python, file I/O) |
| Testing | Neuro SAN `DataDrivenAgentTestDriver` + pytest |
| Test evaluation | Gist (LLM semantic), keywords (exact match), not_keywords (exact exclusion) |

---

## Test Coverage

Five data-driven integration test fixtures validate the system end-to-end using real LLM calls:

| Fixture | What it tests |
|---|---|
| `fixture1_rich_input_broad_routing` | Phase 1: confirmed fields (Azure, HIPAA) are not re-asked |
| `fixture2_vague_input_scope_question` | Phase 1: vague input → scope question asked, no analysis produced |
| `fixture3_infra_only_domain_gated_intake` | Phase 1: infra-only signal → app/data/integration questions suppressed |
| `fixture4_compliance_signal_security_routing` | Phase 2: SOC 2 signal → security_architect runs, compliance findings produced |
| `fixture5_followup_topic_continuity` | Phase 3: two consecutive SQL Server questions both routed to data_architect |

All 5 tests pass consistently against Azure OpenAI. Total runtime: ~5 minutes.

---

## What Makes This Different from a Simple Chatbot

| Capability | Generic chatbot | Enterprise Architect Advisor |
|---|---|---|
| Domain coverage | Single model, single context | 8 specialist domains, concurrent analysis |
| Analysis depth | Generic advice | Scored option tables (100-pt rubric) per domain |
| Assumption transparency | Hidden | Every assumed default labelled, listed in executive summary |
| Document output | Chat text only | 4 structured files to disk, shareable and version-controllable |
| Follow-up handling | Re-answers from scratch | Routes to specialist; updates only affected doc sections |
| Governance | None | L2 review board + self-correcting loop for MAJOR concerns |
| Auditability | None | Per-specialist timing ledger, Amendment Log in updated files |
