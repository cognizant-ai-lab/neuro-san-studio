# Enterprise Architect Advisor

A **12-agent, two-phase advisory system** built on the [Neuro SAN](https://github.com/cognizant-ai-lab/neuro-san)
framework that guides enterprises through cloud modernisation and IT transformation. Give it a plain-English description
of your current system and goals — it asks only the questions it needs, runs eight domain specialists concurrently,
reviews the findings, and produces four structured deliverable documents.

**Hackathon submission** — Cognizant AI Hackathon 2026

---

## Quick Overview

| Phase | What happens |
|---|---|
| **Phase 1 — Intake** | Agent extracts confirmed fields, asks only what is missing |
| **Phase 2 — Analysis** | Up to 8 specialists run concurrently; L2 critique + governance review; 4 files written to disk |
| **Phase 3 — Follow-up** | Questions routed to the relevant specialist; new info triggers targeted doc updates |

Deliverables written to `outputs/enterprise_architect_advisor/<project-name>/`:
- `executive_summary.md`
- `architecture_decision_matrix.md`
- `detailed_findings.md`
- `roadmap.md`

---

## Requirements

- Python 3.11 or 3.12 (Python 3.13 also works)
- An **Azure OpenAI** resource with a deployed GPT-4 or GPT-4o model

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/enterprise-architect-advisor.git
cd enterprise-architect-advisor
```

### 2. Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure credentials

Copy the example env file and fill in your Azure OpenAI values:

```bash
cp .env.example .env
```

Edit `.env`:

```
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-key>
OPENAI_API_VERSION=2025-04-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=<your-deployment-name>
```

> ⚠️ `.env` is gitignored and must **never** be committed.

---

## Running the Agent

Start the Neuro SAN server with the agent network loaded:

```bash
ns run
```

Then open the web UI at **http://localhost:4173** (nsflow), select **Enterprise Architect Advisor**, and start a conversation.

Or use the CLI chat:

```bash
ns chat --agent nagarjunvk/enterprise_architect_advisor
```

**Example first message:**

```
We are modernising our Java Spring Boot monolith to Azure. 
The database is SQL Server and we have SOC 2 Type II requirements. 
Timeline is 12 months.
```

---

## Running the Tests

The test suite runs entirely in-process (no server required):

```bash
pytest tests/integration/test_integration_test_hocons.py -k nagarjunvk_ea -v
```

All 5 fixtures should pass. Each test takes 1–3 minutes (LLM calls). Full suite: ~5 minutes.

---

## Project Structure

```
registries/nagarjunvk/          # Agent network HOCON definition
coded_tools/industry/           # DocumentWriter coded tool
middleware/enterprise_architect_advisor/  # CallLedgerMiddleware (concurrency telemetry)
tests/fixtures/nagarjunvk/      # 5 data-driven integration test fixtures
config/                         # LLM configuration
docs/examples/nagarjunvk/       # Agent network documentation
```

---

## Documentation

- [Architecture](architecture.md) — Agent hierarchy, design decisions, concurrency model
- [Project Summary](summary.md) — What the system does and how it works
- [Agent Network Docs](docs/examples/nagarjunvk/enterprise_architect_advisor.md) — Full agent reference
