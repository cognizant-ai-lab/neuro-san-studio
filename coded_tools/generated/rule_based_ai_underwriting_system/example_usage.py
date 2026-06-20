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
    print(json.dumps(orchestrator.summarize_grounding(), indent=2))
    print(json.dumps(orchestrator.run_pipeline("CASE-0001"), indent=2))


if __name__ == "__main__":
    main()
