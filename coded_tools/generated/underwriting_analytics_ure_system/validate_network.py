"""
Validation runner for the grounded underwriting analytics network.
Executes each workflow phase sequentially and records where execution degrades.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from coded_tools.generated.underwriting_analytics_ure_system.orchestrator_agent import OrchestratorAgent


def main() -> None:
    orchestrator = OrchestratorAgent()
    validation = orchestrator.validate_workflow_steps()
    print(json.dumps(validation, indent=2, default=str))


if __name__ == "__main__":
    main()
