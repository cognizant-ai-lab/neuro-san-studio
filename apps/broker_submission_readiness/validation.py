"""Deterministic validation of required submission fields and documents."""

from typing import Any

from apps.broker_submission_readiness.models import Policy
from apps.broker_submission_readiness.models import Submission

FIELD_LABELS = {
    "business_name": "Business name",
    "business_description": "Business description",
    "mailing_address": "Mailing address",
    "annual_revenue": "Annual revenue",
    "requested_limit": "Requested coverage limit",
    "broker_name": "Broker name",
    "broker_email": "Broker email",
}
DOCUMENT_LABELS = {
    "acord_125": "ACORD 125 application",
    "acord_126": "ACORD 126 liability section",
    "loss_runs": "Currently valued loss runs",
    "property_schedule": "Property/location schedule",
}


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_submission(policy: Policy, submission: Submission) -> dict[str, list[str]]:
    """Return missing field/document labels and explicit input errors."""
    missing_fields = [
        FIELD_LABELS.get(field, field.replace("_", " ").title())
        for field in policy["required_fields"]
        if _is_missing(submission.get(field))
    ]
    missing_documents = [
        DOCUMENT_LABELS.get(document, document.replace("_", " ").title())
        for document in policy["required_documents"]
        if document not in submission["documents"]
    ]
    field_errors: list[str] = []

    for field, label in (
        ("annual_revenue", FIELD_LABELS["annual_revenue"]),
        ("requested_limit", FIELD_LABELS["requested_limit"]),
    ):
        value = submission.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            field_errors.append(f"{label} must be a positive whole-dollar amount.")

    broker_email = submission.get("broker_email", "").strip()
    if broker_email and ("@" not in broker_email or broker_email.startswith("@") or broker_email.endswith("@")):
        field_errors.append("Broker email must contain a valid-looking email address.")

    return {
        "missing_fields": missing_fields,
        "missing_documents": missing_documents,
        "field_errors": field_errors,
    }
