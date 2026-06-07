"""
antigravity_apps/service_desk/tools/ticket_parser.py
=====================================================
Enterprise IT Service Desk — Ticket Parser & PII Scrubber
----------------------------------------------------------
Implements:
  - TicketParserTool  : regex-based PII redaction (phones, credentials, email header chains)
  - map_to_servicenow_payload : maps clean text to a standard ServiceNow Incident table payload

Author  : Cognizant AI Lab — Antigravity Platform Engineering
Python  : 3.10+
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redaction patterns
# ---------------------------------------------------------------------------

# Phone numbers — supports E.164, US, intl, dotted, dashed, parens
_PHONE_PATTERN = re.compile(
    r"""
    (?:                            # optional country code
        \+?1[-.\s]?
    )?
    (?:
        \(\d{3}\)[-.\s]?           # (NXX) with optional separator
        | \d{3}[-.\s]              # NXX with separator
    )
    \d{3}                          # Exchange
    [-.\s]?
    \d{4}                          # Subscriber
    (?:\s?(?:x|ext|extension)\.?\s?\d{1,6})?   # optional extension
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Inline credentials — password=, passwd=, pwd=, token=, secret=, api_key= (value up to whitespace / quote)
_CREDENTIAL_PATTERN = re.compile(
    r"""
    (?P<key>
        password|passwd|pwd|token|secret|api[_-]?key|apikey|auth|bearer|credential
    )
    \s*[:=]\s*                     # delimiter
    (?P<value>
        "(?:[^"\\]|\\.)*"          # double-quoted value
        | '(?:[^'\\]|\\.)*'        # single-quoted value
        | \S+                      # bare (no whitespace) value
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Email header chains — lines that begin with "From:", "To:", "Cc:", "Sent:", "Date:", "Reply-To:"
_EMAIL_HEADER_PATTERN = re.compile(
    r"""
    ^
    (?:From|To|Cc|Bcc|Sent|Date|Reply-To|Delivered-To|Return-Path|X-[\w-]+)
    \s*:
    [^\n]*
    """,
    re.MULTILINE | re.VERBOSE | re.IGNORECASE,
)

# Standalone email addresses (after header lines are stripped)
_EMAIL_ADDR_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# ---------------------------------------------------------------------------
# ServiceNow urgency / impact mapping
# ---------------------------------------------------------------------------

_PRIORITY_MAP: dict[str, dict[str, int]] = {
    "HIGH":   {"urgency": 1, "impact": 1},
    "MEDIUM": {"urgency": 2, "impact": 2},
    "LOW":    {"urgency": 3, "impact": 3},
}

_CATEGORY_TO_SUBCATEGORY: dict[str, str] = {
    "Network":  "Connectivity",
    "Database": "Performance",
    "Hardware": "Failure",
    "IAM":      "Access Control",
}

# ServiceNow Incident state codes
_INCIDENT_STATE = {
    "New":         1,
    "In Progress": 2,
    "On Hold":     3,
    "Resolved":    6,
    "Closed":      7,
    "Cancelled":   8,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RedactionReport:
    """Audit record of everything that was scrubbed from a raw text blob."""
    phones_redacted: int = 0
    credentials_redacted: int = 0
    email_headers_redacted: int = 0
    email_addresses_redacted: int = 0
    redaction_log: list[str] = field(default_factory=list)

    @property
    def total_redactions(self) -> int:
        return (
            self.phones_redacted
            + self.credentials_redacted
            + self.email_headers_redacted
            + self.email_addresses_redacted
        )


# ---------------------------------------------------------------------------
# Core tool
# ---------------------------------------------------------------------------

class TicketParserTool:
    """
    Production-grade PII scrubber and ServiceNow payload builder.

    Usage
    -----
    >>> parser = TicketParserTool()
    >>> clean, report = parser.redact_pii(raw_email_text)
    >>> payload = parser.map_to_servicenow_payload(clean, "Network", "HIGH")
    """

    def __init__(self, redact_token: str = "[REDACTED]") -> None:
        self.redact_token = redact_token
        logger.info("TicketParserTool initialised with redact_token=%r", redact_token)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def redact_pii(self, raw_text: str) -> tuple[str, RedactionReport]:
        """
        Scrub all PII categories from *raw_text*.

        Returns
        -------
        clean_text : str
            Sanitised text safe to forward to downstream LLM agents.
        report : RedactionReport
            Audit object summarising what was removed.
        """
        report = RedactionReport()
        text = raw_text

        # 1. Email header chains  (strip entire header lines first)
        def _strip_header(m: re.Match) -> str:  # type: ignore[type-arg]
            report.email_headers_redacted += 1
            report.redaction_log.append(f"[HEADER] stripped: {m.group(0)[:60]!r} …")
            return ""

        text = _EMAIL_HEADER_PATTERN.sub(_strip_header, text)

        # 2. Inline credentials  (keep key name, redact value)
        def _strip_credential(m: re.Match) -> str:  # type: ignore[type-arg]
            report.credentials_redacted += 1
            report.redaction_log.append(
                f"[CRED] key={m.group('key')!r} value-redacted"
            )
            return f"{m.group('key')}={self.redact_token}"

        text = _CREDENTIAL_PATTERN.sub(_strip_credential, text)

        # 3. Phone numbers
        def _strip_phone(m: re.Match) -> str:  # type: ignore[type-arg]
            report.phones_redacted += 1
            report.redaction_log.append(f"[PHONE] redacted: {m.group(0)!r}")
            return self.redact_token

        text = _PHONE_PATTERN.sub(_strip_phone, text)

        # 4. Residual standalone email addresses
        def _strip_email(m: re.Match) -> str:  # type: ignore[type-arg]
            report.email_addresses_redacted += 1
            report.redaction_log.append(f"[EMAIL] redacted: {m.group(0)!r}")
            return self.redact_token

        text = _EMAIL_ADDR_PATTERN.sub(_strip_email, text)

        # 5. Collapse excessive blank lines created by redaction
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        logger.info(
            "Redaction complete — %d total items removed",
            report.total_redactions,
        )
        return text, report

    # ------------------------------------------------------------------

    def map_to_servicenow_payload(
        self,
        clean_text: str,
        category: str,
        priority: str,
        *,
        caller_id: str = "api_ingest_agent",
        assignment_group: str = "NOC-L2-AutoClassify",
        initial_state: str = "New",
    ) -> dict[str, Any]:
        """
        Build a standard ServiceNow Incident table JSON payload.

        Parameters
        ----------
        clean_text        : Sanitised incident description (PII-free).
        category          : One of Network | Database | Hardware | IAM.
        priority          : One of HIGH | MEDIUM | LOW.
        caller_id         : ServiceNow sys_id or user name of the reporter.
        assignment_group  : Target resolver group.
        initial_state     : Lifecycle state for the new ticket.

        Returns
        -------
        dict matching the ServiceNow REST Table API `incident` schema.
        """
        priority_upper = priority.upper()
        category_title = category.title()

        urgency = _PRIORITY_MAP.get(priority_upper, {}).get("urgency", 3)
        impact  = _PRIORITY_MAP.get(priority_upper, {}).get("impact",  3)
        subcategory = _CATEGORY_TO_SUBCATEGORY.get(category_title, "General")
        state_code  = _INCIDENT_STATE.get(initial_state, 1)

        # Derive short_description — first non-blank line ≤ 160 chars
        short_desc = next(
            (line.strip() for line in clean_text.splitlines() if line.strip()),
            "Auto-classified IT Incident",
        )[:160]

        payload: dict[str, Any] = {
            "short_description": short_desc,
            "description":       clean_text,
            "category":          category_title,
            "subcategory":       subcategory,
            "urgency":           str(urgency),
            "impact":            str(impact),
            "priority":          str(max(urgency, impact)),   # ServiceNow derived priority
            "state":             str(state_code),
            "caller_id":         caller_id,
            "assignment_group":  assignment_group,
            "comments":          (
                f"Auto-ingested via Antigravity AI Pipeline.\n"
                f"Classifier priority={priority_upper}, category={category_title}."
            ),
            "work_notes":        "PII scrubbed by TicketParserTool before ingestion.",
        }

        logger.debug("ServiceNow payload built: %s", payload)
        return payload
