"""Deterministic comparison of submission values with current policy values."""

from apps.broker_submission_readiness.models import Comparison
from apps.broker_submission_readiness.models import Policy
from apps.broker_submission_readiness.models import Submission


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _is_material_change(existing: int, submitted: int, threshold_percent: int) -> bool:
    if existing == 0:
        return submitted != 0
    return abs(submitted - existing) * 100 >= existing * threshold_percent


def compare_submission(policy: Policy, submission: Submission) -> list[Comparison]:
    """Compare populated policy fields and flag configured material changes."""
    comparisons: list[Comparison] = []
    fields: tuple[tuple[str, str, str | int, str | int], ...] = (
        ("business_name", "Business name", policy["insured_name"], submission["business_name"]),
        (
            "business_description",
            "Business description",
            policy["business_description"],
            submission["business_description"],
        ),
        ("mailing_address", "Mailing address", policy["mailing_address"], submission["mailing_address"]),
        ("annual_revenue", "Annual revenue", policy["annual_revenue"], submission["annual_revenue"]),
        ("requested_limit", "Requested coverage limit", policy["requested_limit"], submission["requested_limit"]),
    )

    for field, label, existing, submitted in fields:
        if field in {"business_name", "business_description", "mailing_address"}:
            if not isinstance(submitted, str) or not submitted.strip():
                continue
        elif (
            not isinstance(submitted, int)
            or isinstance(submitted, bool)
            or submitted <= 0
        ):
            continue

        if isinstance(existing, str) and isinstance(submitted, str):
            changed = _normalize_text(existing) != _normalize_text(submitted)
        else:
            changed = existing != submitted

        material = False
        explanation = "No change from the existing policy value."
        if changed:
            explanation = "Value differs from the existing policy; refer to an underwriter."
            if field in {"business_name", "business_description", "mailing_address"}:
                material = True
                explanation = "Material change: the submitted text value differs from the policy record."
            elif field == "annual_revenue":
                material = _is_material_change(
                    int(existing),
                    int(submitted),
                    policy["annual_revenue_materiality_percent"],
                )
                if material:
                    explanation = (
                        f"Material change: annual revenue changed by at least "
                        f"{policy['annual_revenue_materiality_percent']}%."
                    )
            elif field == "requested_limit":
                material = _is_material_change(
                    int(existing),
                    int(submitted),
                    policy["requested_limit_materiality_percent"],
                )
                if material:
                    explanation = (
                        f"Material change: requested limit changed by at least "
                        f"{policy['requested_limit_materiality_percent']}%."
                    )

        comparisons.append(
            {
                "field": label,
                "existing_value": existing,
                "submitted_value": submitted,
                "changed": changed,
                "material": material,
                "explanation": explanation,
            }
        )

    return comparisons
