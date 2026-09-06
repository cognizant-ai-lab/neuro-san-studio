# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import asyncio
from pathlib import Path
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool


class RunbookSearch(CodedTool):
    """Returns grounded runbook guidance for a classified incident type."""

    RUNBOOKS = {
        "db_timeout": "runbook_db_timeout.md",
        "api_failure": "runbook_api_failure.md",
        "memory_issue": "runbook_memory_issue.md",
        "unknown": "known_error_patterns.md",
    }

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        issue_type = str(args.get("issue_type", "unknown")).strip().lower() or "unknown"
        grounding_dir = Path(__file__).resolve().parent / "grounding"
        runbook_name = self.RUNBOOKS.get(issue_type, "known_error_patterns.md")
        runbook_path = grounding_dir / runbook_name
        template_path = grounding_dir / "incident_update_template.md"

        if not runbook_path.exists():
            return {"error": f"Runbook not found: {runbook_path}"}

        return {
            "issue_type": issue_type,
            "matched_runbook": runbook_name,
            "runbook_text": runbook_path.read_text(encoding="utf-8"),
            "incident_update_template": template_path.read_text(encoding="utf-8") if template_path.exists() else "",
        }

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        return await asyncio.to_thread(self.invoke, args, sly_data)
