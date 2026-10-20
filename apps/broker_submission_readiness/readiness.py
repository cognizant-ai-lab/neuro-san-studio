"""Business rules for completeness status and human-readable artifacts."""

from apps.broker_submission_readiness.consistency import compare_submission
from apps.broker_submission_readiness.models import Comparison
from apps.broker_submission_readiness.models import EmailDraft
from apps.broker_submission_readiness.models import Policy
from apps.broker_submission_readiness.models import ReadinessReport
from apps.broker_submission_readiness.models import Submission

RULE_EXPLANATIONS = {
    "MISSING_REQUIRED_FIELDS": "At least one policy-required submission field is blank.",
    "MISSING_REQUIRED_DOCUMENTS": "At least one policy-required document was not supplied.",
    "INVALID_FIELD_VALUES": "At least one provided value failed the deterministic input checks.",
    "BUSINESS_NAME_CHANGED": "The submitted business name differs from the existing policy.",
    "BUSINESS_DESCRIPTION_CHANGED": "The submitted business description differs from the existing policy.",
    "MAILING_ADDRESS_CHANGED": "The submitted mailing address differs from the existing policy.",
    "ANNUAL_REVENUE_MATERIAL_CHANGE": "Annual revenue changed by at least the policy's configured threshold.",
    "REQUESTED_LIMIT_MATERIAL_CHANGE": (
        "Requested coverage limit changed by at least the policy's configured threshold."
    ),
}


def decide_readiness(
    missing_fields: list[str], missing_documents: list[str], field_errors: list[str]
) -> tuple[str, list[str]]:
    """Decide intake completeness; this is not an underwriting outcome."""
    rules: list[str] = []
    if missing_fields:
        rules.append("MISSING_REQUIRED_FIELDS")
    if missing_documents:
        rules.append("MISSING_REQUIRED_DOCUMENTS")
    if field_errors:
        rules.append("INVALID_FIELD_VALUES")

    status = "NEEDS INFORMATION" if rules else "READY FOR UNDERWRITER REVIEW"
    return status, rules


def _change_rules(comparisons: list[Comparison]) -> list[str]:
    rules_by_field = {
        "Business name": "BUSINESS_NAME_CHANGED",
        "Business description": "BUSINESS_DESCRIPTION_CHANGED",
        "Mailing address": "MAILING_ADDRESS_CHANGED",
        "Annual revenue": "ANNUAL_REVENUE_MATERIAL_CHANGE",
        "Requested coverage limit": "REQUESTED_LIMIT_MATERIAL_CHANGE",
    }
    return [
        rules_by_field[comparison["field"]]
        for comparison in comparisons
        if comparison["changed"] and comparison["material"]
    ]


def _build_summary(
    policy: Policy,
    status: str,
    missing_fields: list[str],
    missing_documents: list[str],
    material_changes: list[str],
) -> str:
    lines = [
        f"Policy {policy['policy_number']} for {policy['insured_name']}: {status}.",
        f"Required fields missing: {len(missing_fields)}; required documents missing: {len(missing_documents)}.",
        f"Material differences flagged for human underwriter review: {len(material_changes)}.",
        "This is not an underwriting, pricing, acceptance, or rejection decision; it checks intake completeness only.",
    ]
    return " ".join(lines)


def _build_email_draft(
    policy: Policy,
    submission: Submission,
    missing_fields: list[str],
    missing_documents: list[str],
    field_errors: list[str],
) -> EmailDraft:
    recipient = submission["broker_name"].strip() or "Broker"
    if missing_fields or missing_documents or field_errors:
        follow_up: list[str] = []
        if missing_fields:
            follow_up.append("Please provide or confirm the following information: " + ", ".join(missing_fields) + ".")
        if missing_documents:
            follow_up.append("Please provide the following documents: " + ", ".join(missing_documents) + ".")
        if field_errors:
            follow_up.append("Please correct the following items: " + " ".join(field_errors))
        body = (
            f"Hello {recipient},\n\n"
            f"We are reviewing the submission for policy {policy['policy_number']} ({policy['insured_name']}). "
            "To complete the intake review, please send:\n\n"
            + "\n".join(f"- {item}" for item in follow_up)
            + "\n\nThis request concerns submission completeness only and is not an underwriting decision.\n\n"
            "Thank you."
        )
        subject = f"Information needed for policy {policy['policy_number']}"
    else:
        body = (
            f"Hello {recipient},\n\n"
            f"We have received the submission information for policy {policy['policy_number']} "
            f"({policy['insured_name']}). The submission is complete for intake and is ready for underwriter review. "
            "No underwriting or pricing decision has been made.\n\nThank you."
        )
        subject = f"Submission received for policy {policy['policy_number']}"

    if submission["broker_email"].strip():
        body = f"To: {submission['broker_email'].strip()}\n\n{body}"
    return {"subject": subject, "body": body}


def build_report(policy: Policy, submission: Submission, validation: dict[str, list[str]]) -> ReadinessReport:
    """Build the stable report from deterministic validation and comparison results."""
    comparisons = compare_submission(policy, submission)
    readiness_status, triggered_rules = decide_readiness(
        validation["missing_fields"], validation["missing_documents"], validation["field_errors"]
    )
    change_rules = _change_rules(comparisons)
    all_rules = triggered_rules + change_rules
    material_changes = [
        f"{comparison['field']}: {comparison['explanation']}"
        for comparison in comparisons
        if comparison["changed"] and comparison["material"]
    ]
    return {
        "policy": policy,
        "submission": submission,
        "readiness_status": readiness_status,
        "readiness_source": "deterministic_python_business_rules",
        "missing_fields": validation["missing_fields"],
        "missing_documents": validation["missing_documents"],
        "field_errors": validation["field_errors"],
        "comparisons": comparisons,
        "material_changes": material_changes,
        "triggered_rules": all_rules,
        "rule_explanations": [RULE_EXPLANATIONS[rule] for rule in all_rules],
        "summary": _build_summary(
            policy,
            readiness_status,
            validation["missing_fields"],
            validation["missing_documents"],
            material_changes,
        ),
        "email_draft": _build_email_draft(
            policy,
            submission,
            validation["missing_fields"],
            validation["missing_documents"],
            validation["field_errors"],
        ),
        "human_review_required": True,
        "underwriting_decision_made": False,
    }
