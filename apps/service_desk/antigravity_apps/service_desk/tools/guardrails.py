"""
antigravity_apps/service_desk/tools/guardrails.py
==================================================
Enterprise IT Service Desk — Pydantic Output Guardrails
--------------------------------------------------------
Implements:
  - ServiceNowTicketSchema : strict Pydantic model enforcing controlled vocabularies
  - TicketGuardrail        : LLM output interceptor that validates, strips markdown
                             artifacts, and returns a typed execution-status tuple

Author  : Cognizant AI Lab — Antigravity Platform Engineering
Python  : 3.10+
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

class CategoryEnum(str, Enum):
    Network  = "Network"
    Database = "Database"
    Hardware = "Hardware"
    IAM      = "IAM"


class PriorityEnum(str, Enum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


# ---------------------------------------------------------------------------
# Strict Pydantic schema
# ---------------------------------------------------------------------------

class ServiceNowTicketSchema(BaseModel):
    """
    Strict schema for the structured-classifier agent's JSON output.

    All fields are required. Any deviation from the controlled vocabularies
    raises a ``ValidationError`` before the payload is forwarded downstream.
    """

    model_config = {
        "extra":       "forbid",      # reject unknown fields — blocks hallucinated keys
        "str_strip_whitespace": True,
        "use_enum_values": True,
    }

    category: CategoryEnum = Field(
        ...,
        description="ITSM category strictly bounded to: Network, Database, Hardware, IAM.",
    )
    priority: PriorityEnum = Field(
        ...,
        description="Incident priority strictly bounded to: HIGH, MEDIUM, LOW.",
    )
    justification: str = Field(
        ...,
        min_length=10,
        max_length=1_000,
        description="Plain-text rationale from the classifier (10–1000 characters).",
    )

    # ------------------------------------------------------------------
    # Field-level validators
    # ------------------------------------------------------------------

    @field_validator("category", mode="before")
    @classmethod
    def normalise_category(cls, v: Any) -> str:
        """Accept 'network' → 'Network', 'IAM' → 'IAM', etc."""
        if isinstance(v, str):
            # Title-case everything except IAM which is all-caps
            mapped = {c.lower(): c for c in CategoryEnum.__members__}
            normalised = mapped.get(v.strip().lower())
            if normalised is None:
                raise ValueError(
                    f"Invalid category {v!r}. "
                    f"Allowed: {list(CategoryEnum.__members__.keys())}"
                )
            return normalised
        return v

    @field_validator("priority", mode="before")
    @classmethod
    def normalise_priority(cls, v: Any) -> str:
        """Accept 'high', 'High', 'HIGH' uniformly."""
        if isinstance(v, str):
            upper = v.strip().upper()
            if upper not in PriorityEnum.__members__:
                raise ValueError(
                    f"Invalid priority {v!r}. "
                    f"Allowed: {list(PriorityEnum.__members__.keys())}"
                )
            return upper
        return v

    @model_validator(mode="after")
    def justification_no_pii_markers(self) -> "ServiceNowTicketSchema":
        """
        Heuristic guard — reject justifications that look like they still
        contain raw credentials or phone numbers (PII scrubber should have
        run first, but this is a defence-in-depth check).
        """
        pii_hint = re.search(
            r"(password\s*[:=]|passwd\s*[:=]|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b)",
            self.justification,
            re.IGNORECASE,
        )
        if pii_hint:
            raise ValueError(
                "Justification field appears to contain PII or raw credentials. "
                "Ensure the PII scrubber runs before the classifier."
            )
        return self


# ---------------------------------------------------------------------------
# Execution status
# ---------------------------------------------------------------------------

class GuardrailStatus(str, Enum):
    OK              = "OK"
    VALIDATION_FAIL = "VALIDATION_FAIL"
    PARSE_ERROR     = "PARSE_ERROR"
    EMPTY_OUTPUT    = "EMPTY_OUTPUT"


# ---------------------------------------------------------------------------
# Interceptor
# ---------------------------------------------------------------------------

# Regex to strip markdown fenced code blocks (```json … ```, ``` … ```)
_MARKDOWN_FENCE_RE = re.compile(
    r"```(?:json|JSON)?\s*([\s\S]*?)```",
    re.MULTILINE,
)

# Fallback: grab the first {...} block if the model wraps JSON in prose
_JSON_BLOCK_RE = re.compile(r"\{[\s\S]+\}", re.MULTILINE)


class TicketGuardrail:
    """
    LLM output interceptor for the structured-classifier agent.

    Responsibilities
    ----------------
    1. Strip markdown fences (```json … ```) from raw LLM text.
    2. Parse the extracted string as JSON.
    3. Validate against ``ServiceNowTicketSchema``.
    4. Return a typed ``(GuardrailStatus, validated_object | error_detail)`` tuple.

    Usage
    -----
    >>> guardrail = TicketGuardrail()
    >>> status, result = guardrail.validate_output(raw_llm_output)
    >>> if status == GuardrailStatus.OK:
    ...     payload = result           # ServiceNowTicketSchema instance
    ... else:
    ...     handle_error(result)       # str describing the failure
    """

    def __init__(self, *, strict_pii_check: bool = True) -> None:
        self.strict_pii_check = strict_pii_check
        logger.info(
            "TicketGuardrail initialised (strict_pii_check=%s)", strict_pii_check
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_output(
        self, raw_llm_output: str
    ) -> tuple[GuardrailStatus, ServiceNowTicketSchema | str]:
        """
        Validate a raw LLM text blob against the ServiceNow ticket schema.

        Parameters
        ----------
        raw_llm_output : str
            The verbatim string returned by the LLM agent.

        Returns
        -------
        (GuardrailStatus.OK,              ServiceNowTicketSchema)  on success
        (GuardrailStatus.VALIDATION_FAIL, str: human-readable errors)  on schema violation
        (GuardrailStatus.PARSE_ERROR,     str: parse failure detail)   on JSON error
        (GuardrailStatus.EMPTY_OUTPUT,    str: message)                when output is blank
        """
        if not raw_llm_output or not raw_llm_output.strip():
            logger.warning("Guardrail received empty LLM output")
            return GuardrailStatus.EMPTY_OUTPUT, "LLM returned an empty response."

        # Step 1 — strip markdown fences
        json_str = self._extract_json(raw_llm_output)
        if json_str is None:
            logger.error("Guardrail could not locate a JSON block in LLM output")
            return (
                GuardrailStatus.PARSE_ERROR,
                "No JSON object found in the LLM output. "
                "Raw output (truncated): " + raw_llm_output[:300],
            )

        # Step 2 — parse JSON
        try:
            data: dict[str, Any] = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error("JSON parse failure: %s", exc)
            return (
                GuardrailStatus.PARSE_ERROR,
                f"JSON parsing failed: {exc}. "
                f"Extracted string (truncated): {json_str[:300]}",
            )

        # Step 3 — Pydantic validation
        try:
            ticket = ServiceNowTicketSchema(**data)
        except ValidationError as exc:
            # Collect all Pydantic errors into a readable summary
            error_summary = self._format_validation_errors(exc)
            logger.warning("Schema validation failed: %s", error_summary)
            return GuardrailStatus.VALIDATION_FAIL, error_summary

        logger.info(
            "Guardrail PASSED — category=%s priority=%s",
            ticket.category,
            ticket.priority,
        )
        return GuardrailStatus.OK, ticket

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """
        Try to extract a JSON string from *text*.

        Strategy (in order):
        1. Pull the content from inside a markdown fenced block.
        2. Grab the first ``{…}`` block in the raw text.
        3. Treat the entire stripped text as JSON.
        """
        # Strategy 1 — markdown fence
        fence_match = _MARKDOWN_FENCE_RE.search(text)
        if fence_match:
            candidate = fence_match.group(1).strip()
            if candidate:
                return candidate

        # Strategy 2 — bare JSON block anywhere in prose
        block_match = _JSON_BLOCK_RE.search(text)
        if block_match:
            return block_match.group(0).strip()

        # Strategy 3 — maybe the whole thing is JSON
        stripped = text.strip()
        if stripped.startswith("{"):
            return stripped

        return None

    @staticmethod
    def _format_validation_errors(exc: ValidationError) -> str:
        """Convert a Pydantic ValidationError into a concise human-readable string."""
        lines = []
        for error in exc.errors():
            field_path = " → ".join(str(loc) for loc in error["loc"]) or "root"
            lines.append(f"  • [{field_path}] {error['msg']} (type={error['type']})")
        return "Validation errors:\n" + "\n".join(lines)
