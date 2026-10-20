"""Neuro-SAN adapters for tested broker-submission business rules."""

import logging
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from apps.broker_submission_readiness.consistency import compare_submission
from apps.broker_submission_readiness.models import Submission
from apps.broker_submission_readiness.policy_repository import PolicyNotFoundError
from apps.broker_submission_readiness.policy_repository import get_policy
from apps.broker_submission_readiness.readiness import decide_readiness
from apps.broker_submission_readiness.validation import validate_submission

LOGGER = logging.getLogger(__name__)


def _submission_from_args(args: dict[str, Any]) -> Submission | None:
    raw_submission = args.get("submission")
    if not isinstance(raw_submission, dict):
        return None
    required_strings = (
        "policy_number",
        "business_name",
        "business_description",
        "mailing_address",
        "broker_name",
        "broker_email",
    )
    if any(not isinstance(raw_submission.get(field), str) for field in required_strings):
        return None
    if not isinstance(raw_submission.get("annual_revenue"), int) or isinstance(
        raw_submission.get("annual_revenue"), bool
    ):
        return None
    if not isinstance(raw_submission.get("requested_limit"), int) or isinstance(
        raw_submission.get("requested_limit"), bool
    ):
        return None
    if not isinstance(raw_submission.get("documents"), list) or not all(
        isinstance(document, str) for document in raw_submission["documents"]
    ):
        return None
    return {
        "policy_number": raw_submission["policy_number"],
        "business_name": raw_submission["business_name"],
        "business_description": raw_submission["business_description"],
        "mailing_address": raw_submission["mailing_address"],
        "annual_revenue": raw_submission["annual_revenue"],
        "requested_limit": raw_submission["requested_limit"],
        "broker_name": raw_submission["broker_name"],
        "broker_email": raw_submission["broker_email"],
        "documents": list(raw_submission["documents"]),
    }


class PolicyLookupTool(CodedTool):
    """Retrieve one synthetic policy record instead of contacting a live IBM i."""

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        policy_number = args.get("policy_number")
        if not isinstance(policy_number, str) or not policy_number.strip():
            return {"error": "policy_number must be a non-empty string."}
        try:
            return {"policy": get_policy(policy_number.strip())}
        except PolicyNotFoundError as error:
            return {"error": str(error)}

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """Return the synchronous local lookup result."""
        return self.invoke(args, sly_data)


class SubmissionValidationTool(CodedTool):
    """Check policy-required submission fields and documents."""

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        submission = _submission_from_args(args)
        policy_number = args.get("policy_number")
        if (
            submission is None
            or not isinstance(policy_number, str)
            or not policy_number.strip()
            or submission["policy_number"] != policy_number.strip()
        ):
            return {"error": "policy_number and a correctly shaped submission object are required."}
        policy_number = policy_number.strip()
        try:
            policy = get_policy(policy_number)
        except PolicyNotFoundError as error:
            return {"error": str(error)}
        result = validate_submission(policy, submission)
        LOGGER.info("Validated submission completeness for %s", policy_number)
        return result

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """Return the synchronous deterministic validation result."""
        return self.invoke(args, sly_data)


class ConsistencyCheckTool(CodedTool):
    """Compare business values with the existing synthetic policy record."""

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        submission = _submission_from_args(args)
        policy_number = args.get("policy_number")
        if (
            submission is None
            or not isinstance(policy_number, str)
            or not policy_number.strip()
            or submission["policy_number"] != policy_number.strip()
        ):
            return {"error": "policy_number and a correctly shaped submission object are required."}
        policy_number = policy_number.strip()
        try:
            policy = get_policy(policy_number)
        except PolicyNotFoundError as error:
            return {"error": str(error)}
        return {"comparisons": compare_submission(policy, submission)}

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """Return the synchronous deterministic comparison result."""
        return self.invoke(args, sly_data)


class ReadinessDecisionTool(CodedTool):
    """Apply the deterministic intake-completeness status rules."""

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        fields = args.get("missing_fields")
        documents = args.get("missing_documents")
        errors = args.get("field_errors")
        if not all(
            isinstance(values, list) and all(isinstance(value, str) for value in values)
            for values in (fields, documents, errors)
        ):
            return {"error": "missing_fields, missing_documents, and field_errors must be string lists."}
        status, rules = decide_readiness(fields, documents, errors)
        return {
            "readiness_status": status,
            "triggered_rules": rules,
            "readiness_source": "deterministic_python_business_rules",
            "underwriting_decision_made": False,
        }

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """Return the synchronous deterministic readiness result."""
        return self.invoke(args, sly_data)
