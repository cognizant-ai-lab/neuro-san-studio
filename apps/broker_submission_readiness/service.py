"""Application service joining synthetic retrieval and deterministic rules."""

from apps.broker_submission_readiness.models import ReadinessReport
from apps.broker_submission_readiness.models import Submission
from apps.broker_submission_readiness.policy_repository import get_policy
from apps.broker_submission_readiness.readiness import build_report
from apps.broker_submission_readiness.validation import validate_submission


def analyze_submission(submission: Submission) -> ReadinessReport:
    """Retrieve the current mock policy and produce a deterministic report."""
    policy = get_policy(submission["policy_number"])
    validation = validate_submission(policy, submission)
    return build_report(policy, submission, validation)
