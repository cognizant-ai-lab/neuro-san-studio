"""Run all synthetic scenarios and print their deterministic results as JSON."""

import json
import logging

from apps.broker_submission_readiness.demo_scenarios import DEMO_SCENARIOS
from apps.broker_submission_readiness.service import analyze_submission

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Evaluate the three built-in examples without starting a UI or an LLM."""
    for name, submission in DEMO_SCENARIOS.items():
        report = analyze_submission(submission)
        LOGGER.info(
            "%s\n%s",
            name,
            json.dumps(
                {
                    "policy_number": report["policy"]["policy_number"],
                    "readiness_status": report["readiness_status"],
                    "missing_fields": report["missing_fields"],
                    "missing_documents": report["missing_documents"],
                    "field_errors": report["field_errors"],
                    "material_changes": report["material_changes"],
                },
                indent=2,
            ),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
