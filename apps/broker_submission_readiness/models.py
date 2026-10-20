"""Typed data contracts for broker submission readiness checks."""

from typing import TypedDict


class Policy(TypedDict):
    """Synthetic policy context retrieved from the local IBM i mock."""

    policy_number: str
    insured_name: str
    business_description: str
    mailing_address: str
    annual_revenue: int
    requested_limit: int
    required_documents: list[str]
    required_fields: list[str]
    annual_revenue_materiality_percent: int
    requested_limit_materiality_percent: int


class Submission(TypedDict):
    """Structured values provided for a new-business or renewal submission."""

    policy_number: str
    business_name: str
    business_description: str
    mailing_address: str
    annual_revenue: int
    requested_limit: int
    broker_name: str
    broker_email: str
    documents: list[str]


class Comparison(TypedDict):
    """A field-by-field comparison against the current policy record."""

    field: str
    existing_value: str | int
    submitted_value: str | int
    changed: bool
    material: bool
    explanation: str


class EmailDraft(TypedDict):
    """A draft message that is never transmitted by this application."""

    subject: str
    body: str


class ReadinessReport(TypedDict):
    """Stable JSON-compatible output contract for the user interface."""

    policy: Policy
    submission: Submission
    readiness_status: str
    readiness_source: str
    missing_fields: list[str]
    missing_documents: list[str]
    field_errors: list[str]
    comparisons: list[Comparison]
    material_changes: list[str]
    triggered_rules: list[str]
    rule_explanations: list[str]
    summary: str
    email_draft: EmailDraft
    human_review_required: bool
    underwriting_decision_made: bool
