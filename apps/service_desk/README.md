# Antigravity IT Service Desk — Auto-Classifier

> **Enterprise-grade multi-agent IT service desk automation built on the [Antigravity](https://github.com/cognizant-ai-lab/antigravity) framework.**  
> Developed by **Cognizant AI Lab — Antigravity Platform Engineering**

---

## What This Does

This application solves three real-world Fortune 500 enterprise deployment problems:

| Problem | Solution |
|---|---|
| Mid-workflow API rate-limit failures | HOCON `fallback_chain` cascades GPT-4o → Claude → Gemini → Ollama automatically |
| LLM hallucinations in structured output | Pydantic v2 guardrail with controlled-vocab enums, retry loop + correction prompt |
| PII leakage into ITSM systems | Regex-based scrubber removes phones, credentials, email header chains before storage |

---

## Directory Layout

```
antigravity_apps/
└── service_desk/
    ├── app.py                        # Execution runtime wrapper (run this)
    ├── config/
    │   └── pipeline_network.hocon   # Multi-agent network blueprint
    └── tools/
        ├── ticket_parser.py         # PII scrubber + ServiceNow payload builder
        └── guardrails.py            # Pydantic schema + LLM output interceptor
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Sivaraj/antigravity-service-desk.git
cd antigravity-service-desk

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the pipeline
python -m antigravity_apps.service_desk.app
```

---

## Pipeline Stages

```
Raw messy email (phones, passwords, forwarded chains)
        │
        ▼
[Stage 1] Load HOCON network blueprint
        │
        ▼
[Stage 2] ingestion_agent  →  PII scrubber (TicketParserTool)
        │   Removes: phones, credentials, email headers, email addresses
        ▼
[Stage 3] structured_classifier_agent  →  LLM call (with fallback chain)
        │   Validates output via Pydantic guardrail
        │   Retries with correction prompt on schema violation
        ▼
[Stage 4] Build ServiceNow incident payload
        │
        ▼
output/servicenow_payload.json  (ready to POST to ServiceNow REST API)
```

---

## Live Output Example

```
+-- Classifier Output (Guardrail Validated) --------------------------
|  Category      : Database
|  Priority      : HIGH
|  Justification : Production Postgres cluster is fully unreachable.
|               Replication lag is at 47 seconds, BGP flaps caused
|               12% packet loss on the DB subnet...
+----------------------------------------------------------------------

+-- Redaction Report -------------------------------------------------
|  Total PII items removed : 17
|    * Phones              : 5
|    * Credentials         : 3
|    * Email headers       : 8
|    * Email addresses     : 1
+----------------------------------------------------------------------
```

---

## Fallback Chain (HOCON Config)

| Priority | Provider | Trigger |
|---|---|---|
| 1 (primary) | `openai/gpt-4o` | — |
| 2 | `anthropic/claude-3-5-sonnet` | `rate_limit`, `status_429`, `api_timeout` |
| 3 | `anthropic/claude-3-haiku` | `rate_limit`, `status_429` |
| 4 | `google/gemini-1.5-pro` | `status_429`, `api_timeout`, `service_unavailable` |
| 5 | `ollama/local-llama` (local) | All of the above + `status_503` |

---

## ServiceNow Payload Fields

| Field | Value | Description |
|---|---|---|
| `category` | `Database` | Auto-classified ITSM category |
| `urgency` | `1` | Critical |
| `impact` | `1` | Critical |
| `priority` | `1` | P1 — highest severity |
| `state` | `1` | New |
| `assignment_group` | `NOC-L2-AutoClassify` | Auto-routed team |

---

## Requirements

```
pydantic>=2.7.0,<3.0.0
pyhocon>=0.3.60
openai>=1.30.0
anthropic>=0.28.0
```

---

## License

MIT — Cognizant AI Lab
