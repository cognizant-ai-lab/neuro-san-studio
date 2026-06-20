"""Validation runner for the generated rule-based underwriting network."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from coded_tools.generated.rule_based_ai_underwriting_system.orchestrator_agent import (  # noqa: E402
    UWPipelineOrchestrator,
)


def main() -> None:
    orchestrator = UWPipelineOrchestrator()
    validation = orchestrator.validate_workflow_steps()
    print(json.dumps(validation, indent=2, default=str))


if __name__ == "__main__":
    main()
