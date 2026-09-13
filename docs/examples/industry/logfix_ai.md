# LogFix AI

LogFix AI is a grounded multi-agent incident-triage network that turns sanitized application logs into an explainable,
support-ready response. It separates evidence extraction, classification, root-cause analysis, runbook retrieval,
troubleshooting guidance, and stakeholder communication across focused agents.

---

## File

[logfix_ai.hocon](../../../registries/industry/logfix_ai.hocon)

---

## Purpose

Support engineers often begin incident triage with noisy logs and limited context. LogFix AI helps them identify what
failed, preserve the evidence behind the diagnosis, retrieve relevant runbook guidance, distinguish safe checks from
approval-required actions, and draft an incident update.

The example is designed for sanitized demonstration data. It must not receive credentials, tokens, customer
information, confidential payloads, or unrestricted production logs.

## Network Flow

```text
sanitized log
  -> logfix_ai_triage_manager
  -> log_reader
       -> log_parser_tool
  -> error_classifier
  -> root_cause_analyzer
  -> runbook_retriever
       -> runbook_search_tool
  -> fix_advisor
  -> update_writer
  -> support-ready incident response
```

## Components

| Component | Responsibility |
| --- | --- |
| `logfix_ai_triage_manager` | Coordinates the workflow and assembles the final response. |
| `log_reader` | Extracts high-signal evidence through a deterministic coded tool. |
| `error_classifier` | Classifies the issue as a database timeout, API failure, memory issue, or unknown. |
| `root_cause_analyzer` | Ranks plausible causes and identifies validation checks. |
| `runbook_retriever` | Retrieves packaged Markdown guidance for the classification. |
| `fix_advisor` | Orders low-risk troubleshooting checks and marks controlled actions. |
| `update_writer` | Drafts a concise stakeholder update. |

## Coded Tools and Grounding

`log_parser_tool` extracts service names, API paths, exceptions, HTTP statuses, timeouts, connection pools, and evidence
lines. `runbook_search_tool` maps the classification to packaged Markdown guidance under
`coded_tools/logfix_ai/grounding/`.

The coded tools preserve deterministic evidence while the agents provide coordination and explanation.

## Example Input

```text
2026-09-02 10:15:22 ERROR OrderService
HikariPool-1 - Connection is not available, request timed out after 30000ms.
java.sql.SQLTransientConnectionException:
orders-db - Connection is not available, request timed out after 30000ms.
API /orders returned HTTP 500
```

## Expected Response

The final response contains:

1. Issue summary
2. Evidence found
3. Classification
4. Likely root causes
5. Recommended checks
6. Approval-required actions
7. Draft incident update
8. Safety note

## Validation

From the repository root:

```text
ns validate --verbose --registry-dir . registries/industry/logfix_ai.hocon
```

Unit tests cover database timeouts, API failures, memory issues, unknown input, empty input, runbook matches, and safe
runbook fallback behavior.

The data-driven integration fixture is available at
[`tests/fixtures/industry/logfix_ai_test.hocon`](../../../tests/fixtures/industry/logfix_ai_test.hocon).
