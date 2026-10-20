"""Local synthetic policy retrieval standing in for a future IBM i REST API."""

import json
from pathlib import Path
from typing import Any

from apps.broker_submission_readiness.models import Policy

DATA_FILE = Path(__file__).parent / "data" / "policies.json"


class PolicyNotFoundError(LookupError):
    """Raised when a policy number is not present in the synthetic data set."""


def _require_string(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Policy property {key!r} must be a string.")
    return value


def _require_positive_integer(record: dict[str, Any], key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"Policy property {key!r} must be a positive integer.")
    return value


def _require_string_list(record: dict[str, Any], key: str) -> list[str]:
    value = record.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Policy property {key!r} must be a list of strings.")
    return list(value)


def _parse_policy(policy_number: str, raw_record: Any) -> Policy:
    if not isinstance(raw_record, dict):
        raise ValueError(f"Policy {policy_number!r} must be a JSON object.")

    record: dict[str, Any] = raw_record
    revenue_threshold = _require_positive_integer(record, "annual_revenue_materiality_percent")
    limit_threshold = _require_positive_integer(record, "requested_limit_materiality_percent")
    policy: Policy = {
        "policy_number": _require_string(record, "policy_number"),
        "insured_name": _require_string(record, "insured_name"),
        "business_description": _require_string(record, "business_description"),
        "mailing_address": _require_string(record, "mailing_address"),
        "annual_revenue": _require_positive_integer(record, "annual_revenue"),
        "requested_limit": _require_positive_integer(record, "requested_limit"),
        "required_documents": _require_string_list(record, "required_documents"),
        "required_fields": _require_string_list(record, "required_fields"),
        "annual_revenue_materiality_percent": revenue_threshold,
        "requested_limit_materiality_percent": limit_threshold,
    }
    if policy["policy_number"] != policy_number:
        raise ValueError(f"Policy key {policy_number!r} does not match its policy_number property.")
    return policy


def load_policies(path: Path = DATA_FILE) -> dict[str, Policy]:
    """Load and validate policy records from the local synthetic JSON file."""
    raw_data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError("The synthetic policy file must contain a JSON object.")
    policies: dict[str, Policy] = {}
    for key, value in raw_data.items():
        if not isinstance(key, str):
            raise ValueError("Synthetic policy keys must be strings.")
        policies[key] = _parse_policy(key, value)
    return policies


def get_policy(policy_number: str, path: Path = DATA_FILE) -> Policy:
    """Return a defensive copy of one synthetic policy record."""
    policy = load_policies(path).get(policy_number)
    if policy is None:
        raise PolicyNotFoundError(f"No synthetic policy found for {policy_number!r}.")
    return {
        **policy,
        "required_documents": list(policy["required_documents"]),
        "required_fields": list(policy["required_fields"]),
    }
