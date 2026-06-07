"""
antigravity_apps/service_desk/app.py
=====================================
Execution Runtime Wrapper — IT Service Desk Auto-Classifier
-----------------------------------------------------------
Pipeline stages
  1. Load the Antigravity network blueprint (HOCON config).
  2. Feed a realistic, messy raw email (contains phones, credentials,
     forwarded header chains) through the TicketParserTool PII scrubber.
  3. Simulate the structured-classifier LLM call (with intentional first
     bad output to exercise the guardrail retry loop).
  4. Validate via TicketGuardrail.
  5. Build and stream the final ServiceNow incident payload to stdout.

Author  : Cognizant AI Lab — Antigravity Platform Engineering
Python  : 3.10+

Run
---
    python -m antigravity_apps.service_desk.app
    # or
    python antigravity_apps/service_desk/app.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Optional pyhocon import — graceful degradation if not installed
# ---------------------------------------------------------------------------
try:
    from pyhocon import ConfigFactory  # type: ignore

    _HOCON_AVAILABLE = True
except ImportError:
    _HOCON_AVAILABLE = False

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
# Ensure the workspace root is on sys.path so this can be run directly
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from antigravity_apps.service_desk.tools.ticket_parser import (
    TicketParserTool,
    RedactionReport,
)
from antigravity_apps.service_desk.tools.guardrails import (
    GuardrailStatus,
    ServiceNowTicketSchema,
    TicketGuardrail,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

# Force stdout to UTF-8 on Windows (avoids CP-1252 UnicodeEncodeError)
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s -- %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("antigravity.service_desk.app")


# ===========================================================================
# Constants
# ===========================================================================

_CONFIG_PATH = Path(__file__).parent / "config" / "pipeline_network.hocon"

# ---------------------------------------------------------------------------
# Realistic, deliberately messy raw email — the kind that floods a helpdesk
# ---------------------------------------------------------------------------
_RAW_EMAIL = """
From: alice.wong@acmecorp.com
To: it-support@acmecorp.com
Cc: john.smith@acmecorp.com, noc-team@acmecorp.com
Date: Fri, 6 Jun 2025 09:14:33 -0500
Reply-To: alice.wong@acmecorp.com
Subject: [URGENT] Production DB cluster unreachable — auth failing + network drops

---------- Forwarded message ---------
From: bob.martinez@acmecorp.com
To: alice.wong@acmecorp.com
Date: Thu, 5 Jun 2025 23:58:12 -0500

Hey Alice,

Bob here.  We've been getting alerts since about 11 PM last night.
Our prod Postgres cluster (10.12.5.200) started throwing connection timeouts.
Call me at (512) 867-5309 if this is urgent, or reach me on my cell: +1-800-555-0199.

Here's what we tried:
  - Restarted the replica nodes.
  - Confirmed the app creds:   password=Tr0ub4dor&3  db_user=prod_rw_user
  - Double-checked our DB token: token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.FAKE"
  - api_key=sk-prod-ABCDEF1234567890  (this is the monitoring key — rotated already)
  - Ran EXPLAIN ANALYZE on the slow queries — replication lag is at 47 seconds.

The network team says there were two BGP flaps on the core routers at 11:02 PM
and again at 01:15 AM.  Packet loss is 12 % on the uplink to the DB subnet.
About 80 users on the East Coast trading desk are completely locked out.

Alice, please escalate immediately.  The head of trading called my mobile 
+1 (212) 555-0178 three times already.  This is a P1.

Best,
Bob Martinez
Senior SRE — ACME Corp
Direct: 512.867.5309  |  Emergency: (800) 555‑0199
--------- End Forwarded Message ----------

Hi IT Support,

Forwarding Bob's note.  We need a proper incident ticket RIGHT NOW.
The issue touches both the Database layer (Postgres replication lag, auth) 
AND the Network layer (BGP flaps, 12 % packet loss).  Both need to be logged.

Primary concern: Database — production trading DB cluster is down.
~80 East Coast users impacted → P1/Critical severity.

Please classify and route this immediately.

Thanks,
Alice Wong
VP Engineering | ACME Corp
alice.wong@acmecorp.com | +1 (415) 555-0162
"""


# ===========================================================================
# Pipeline helpers
# ===========================================================================

def _banner(title: str) -> None:
    width = 72
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def _section(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  >>  {title}")
    print("-" * 60)


def _stream_print(text: str, *, delay: float = 0.008) -> None:
    """Simulate streaming output character by character."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


# ---------------------------------------------------------------------------
# Stage 1 — Load network config
# ---------------------------------------------------------------------------

def load_network_config(config_path: Path) -> dict[str, Any] | None:
    """
    Parse the HOCON blueprint and return a Python dict.
    If pyhocon is not installed, log a warning and continue in degraded mode.
    """
    _section("Stage 1 — Loading Antigravity Network Blueprint")

    if not config_path.exists():
        logger.error("Config not found: %s", config_path)
        return None

    if not _HOCON_AVAILABLE:
        logger.warning(
            "pyhocon is not installed. Install with: pip install pyhocon\n"
            "Continuing in degraded mode — config file will not be parsed."
        )
        print(f"  Config path  : {config_path}")
        print("  Status       : SKIPPED (pyhocon not installed)")
        return None

    config = ConfigFactory.parse_file(str(config_path))
    net    = config["network"]

    print(f"  Network name : {net['name']}")
    print(f"  Version      : {net['version']}")
    print(f"  Environment  : {net['environment']}")
    print(f"  Agents       : {[a['id'] for a in net['agents']]}")
    print(f"  Fallback IDs : {[fc['id'] for fc in net['fallback_chain']]}")

    # Resolve active fallback chain from env (default: openai_primary_chain)
    active_chain_id = os.environ.get(
        "ANTIGRAVITY_FALLBACK_CHAIN", "openai_primary_chain"
    )
    active_chain = next(
        (fc for fc in net["fallback_chain"] if fc["id"] == active_chain_id), None
    )
    if active_chain:
        print(f"\n  Active chain : {active_chain_id}")
        print(f"  Primary LLM  : {active_chain['primary']}")
        print("  Fallback providers (in order):")
        for fb in active_chain["fallbacks"]:
            print(
                f"    [{fb['priority']}] {fb['provider']:50s}  "
                f"triggers={fb['trigger_on']}"
            )

    logger.info("Network config loaded successfully from %s", config_path)
    return dict(config)


# ---------------------------------------------------------------------------
# Stage 2 — PII Scrubber (ingestion_agent logic)
# ---------------------------------------------------------------------------

def run_ingestion_agent(raw_email: str) -> tuple[str, RedactionReport]:
    """Run the TicketParserTool PII scrubber — mirrors ingestion_agent behaviour."""

    _section("Stage 2 — ingestion_agent: PII Scrubbing")
    print("  Input length  :", len(raw_email), "chars")

    parser = TicketParserTool(redact_token="[REDACTED]")
    clean_text, report = parser.redact_pii(raw_email)

    print(f"\n  Redaction summary:")
    print(f"    Phones removed        : {report.phones_redacted}")
    print(f"    Credentials removed   : {report.credentials_redacted}")
    print(f"    Email headers stripped: {report.email_headers_redacted}")
    print(f"    Email addresses masked: {report.email_addresses_redacted}")
    print(f"    ---------------------------------")
    print(f"    TOTAL redactions      : {report.total_redactions}")

    print("\n  Redaction audit log:")
    for entry in report.redaction_log:
        print(f"    {entry}")

    print("\n  Clean text preview (first 600 chars):")
    print(textwrap.indent(clean_text[:600] + ("..." if len(clean_text) > 600 else ""), "    "))

    return clean_text, report


# ---------------------------------------------------------------------------
# Stage 3 — Simulated LLM calls (structured_classifier_agent)
# ---------------------------------------------------------------------------

# We simulate TWO LLM responses:
#   • attempt_1 — deliberately malformed (wrong priority value, extra field)
#     to exercise the guardrail retry/correction loop.
#   • attempt_2 — correct output after the guardrail sends a correction prompt.

_SIMULATED_LLM_RESPONSES = [
    # Attempt 1 — bad: unknown priority "CRITICAL", extra key "confidence"
    """\
```json
{
  "category": "Database",
  "priority": "CRITICAL",
  "justification": "The production Postgres cluster is experiencing severe replication lag and connection timeouts, with BGP-related packet loss on the uplink subnet.",
  "confidence": 0.97
}
```
""",
    # Attempt 2 — correct after correction prompt
    """\
```json
{
  "category": "Database",
  "priority": "HIGH",
  "justification": "Production Postgres cluster is fully unreachable. Replication lag is at 47 seconds, BGP flaps caused 12% packet loss on the DB subnet, and approximately 80 East Coast trading-desk users are locked out. Root cause spans both database connectivity and upstream network instability."
}
```
""",
]


def _simulate_llm_call(attempt: int, clean_text: str) -> str:
    """
    Pretend to call an LLM.  In a real Antigravity deployment the
    LLMAgent handles provider routing, retry, and fallback automatically.
    """
    provider_chain = [
        ("openai/gpt-4o",                       0.0),
        ("anthropic/claude-3-5-sonnet-20241022", 0.3),  # fallback after simulated 429
    ]
    # On attempt 1 we simulate a 429 on OpenAI then fallback to Anthropic
    if attempt == 0:
        print("  [LLM] Calling openai/gpt-4o ...")
        time.sleep(0.3)
        print("  [LLM] [!] Received status_429 from openai/gpt-4o -- triggering fallback chain")
        time.sleep(0.2)
        print("  [LLM] Falling back to anthropic/claude-3-5-sonnet-20241022 ...")
        time.sleep(0.4)
    else:
        print("  [LLM] Calling anthropic/claude-3-5-sonnet-20241022 (retry after guardrail fail) ...")
        time.sleep(0.4)

    return _SIMULATED_LLM_RESPONSES[min(attempt, len(_SIMULATED_LLM_RESPONSES) - 1)]


# ---------------------------------------------------------------------------
# Stage 3 — Classifier + Guardrail loop
# ---------------------------------------------------------------------------

def run_classifier_agent(
    clean_text: str,
    *,
    max_retries: int = 2,
) -> tuple[GuardrailStatus, ServiceNowTicketSchema | str]:
    """
    Simulate structured_classifier_agent:
      - Call LLM
      - Validate output via TicketGuardrail
      - Retry with correction prompt on schema failure
    """
    _section("Stage 3 — structured_classifier_agent: Classification + Guardrail")

    guardrail = TicketGuardrail(strict_pii_check=True)
    status: GuardrailStatus | None = None
    result: ServiceNowTicketSchema | str = ""

    for attempt in range(max_retries + 1):
        print(f"\n  -- Attempt {attempt + 1}/{max_retries + 1} --")
        raw_response = _simulate_llm_call(attempt, clean_text)

        print("  [GUARDRAIL] Validating LLM output ...")
        status, result = guardrail.validate_output(raw_response)

        if status == GuardrailStatus.OK:
            print(f"  [GUARDRAIL] [PASSED] on attempt {attempt + 1}")
            break
        else:
            print(f"  [GUARDRAIL] [FAILED] {status.value}:")
            print(textwrap.indent(str(result), "    "))
            if attempt < max_retries:
                print("  [GUARDRAIL] Sending correction prompt to LLM ...")

    return status, result


# ---------------------------------------------------------------------------
# Stage 4 — Build final ServiceNow payload
# ---------------------------------------------------------------------------

def build_servicenow_payload(
    clean_text: str,
    ticket: ServiceNowTicketSchema,
) -> dict[str, Any]:
    _section("Stage 4 — Building Final ServiceNow Incident Payload")

    parser = TicketParserTool()
    payload = parser.map_to_servicenow_payload(
        clean_text=clean_text,
        category=ticket.category,
        priority=ticket.priority,
        caller_id="alice.wong",
        assignment_group="NOC-L2-AutoClassify",
        initial_state="New",
    )

    # Attach guardrail justification as a work note
    payload["work_notes"] = (
        f"Classifier justification: {ticket.justification}\n"
        f"PII scrubbed by TicketParserTool before ingestion."
    )

    return payload


# ===========================================================================
# Main entrypoint
# ===========================================================================

def main() -> None:
    _banner("Antigravity IT Service Desk -- Auto-Classifier Pipeline")

    # -------------------------------------------------------------------
    # Stage 1 — Config
    # -------------------------------------------------------------------
    config = load_network_config(_CONFIG_PATH)

    # -------------------------------------------------------------------
    # Stage 2 — Ingestion / PII scrubbing
    # -------------------------------------------------------------------
    clean_text, redaction_report = run_ingestion_agent(_RAW_EMAIL)

    # -------------------------------------------------------------------
    # Stage 3 — Classification + Guardrail validation
    # -------------------------------------------------------------------
    status, result = run_classifier_agent(clean_text, max_retries=2)

    if status != GuardrailStatus.OK:
        _banner("PIPELINE ABORTED -- Guardrail could not be satisfied")
        print(f"  Final status : {status.value}")
        print(f"  Detail       : {result}")
        sys.exit(1)

    ticket: ServiceNowTicketSchema = result  # type: ignore[assignment]

    # -------------------------------------------------------------------
    # Stage 4 — ServiceNow payload
    # -------------------------------------------------------------------
    payload = build_servicenow_payload(clean_text, ticket)

    # -------------------------------------------------------------------
    # Final output — stream to console
    # -------------------------------------------------------------------
    _banner("Pipeline Complete -- Final ServiceNow Incident Payload")

    print("\n  +-- Classifier Output (Guardrail Validated) --------------------------")
    print(f"  |  Category      : {ticket.category}")
    print(f"  |  Priority      : {ticket.priority}")
    print(f"  |  Justification : {textwrap.fill(ticket.justification, width=60, subsequent_indent='  |               ')}")
    print("  +----------------------------------------------------------------------")

    print("\n  +-- ServiceNow REST Payload (Table: incident) ------------------------")
    formatted_json = json.dumps(payload, indent=2)
    for line in formatted_json.splitlines():
        print(f"  |  {line}")
    print("  +----------------------------------------------------------------------")

    print("\n  +-- Redaction Report -------------------------------------------------")
    print(f"  |  Total PII items removed : {redaction_report.total_redactions}")
    print(f"  |    * Phones              : {redaction_report.phones_redacted}")
    print(f"  |    * Credentials         : {redaction_report.credentials_redacted}")
    print(f"  |    * Email headers       : {redaction_report.email_headers_redacted}")
    print(f"  |    * Email addresses     : {redaction_report.email_addresses_redacted}")
    print("  +----------------------------------------------------------------------")

    print("\n  [OK] Antigravity pipeline executed successfully.\n")

    # Optionally write the payload to a file for downstream consumption
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "servicenow_payload.json"
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  Payload written -> {output_file}")


if __name__ == "__main__":
    main()
