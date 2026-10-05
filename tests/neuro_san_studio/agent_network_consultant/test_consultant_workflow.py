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

"""Tests for Consultant conversations, prompts, and nsflow reporting."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from pyhocon import ConfigFactory

from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow
from neuro_san_studio.agent_network_consultant.stuck_patch_error import StuckPatchError


class TestConsultantWorkflow(TestCase):
    """Verify Consultant prompts and nsflow reporting."""

    FAILURE = {"fixture": "a.hocon", "message": "boom", "path": None}

    def setUp(self) -> None:
        """Create one isolated workflow directory for each test."""
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Remove the isolated workflow directory after each test."""
        shutil.rmtree(self.tmp_path)

    def _failures(self) -> list[dict[str, str | None]]:
        """
        Create one failing fixture report rooted in the temporary directory.

        :return: The collected values.
        """
        fixture = self.tmp_path / "a.hocon"
        fixture.write_text("{}", encoding="utf-8")
        return [{**self.FAILURE, "path": str(fixture)}]

    def test_ungrounded_results_are_written_where_nsflow_can_surface_them(self) -> None:
        """Write ungrounded results into the active nsflow job directory."""
        with patch.dict(
            os.environ,
            {"NSFLOW_JOB_ID": "job1", "NSFLOW_JOB_DIR": str(self.tmp_path)},
        ):
            ConsultantWorkflow.write_ungrounded(["a.hocon: URLProvider: Includes the GSD URL"])
        self.assertIn("URLProvider", (self.tmp_path / "job1.ungrounded.txt").read_text(encoding="utf-8"))

    def test_no_ungrounded_file_is_written_outside_an_nsflow_job(self) -> None:
        """Avoid creating nsflow result files during plain CLI runs."""
        with patch.dict(os.environ, {"NSFLOW_JOB_ID": "", "NSFLOW_JOB_DIR": str(self.tmp_path)}):
            ConsultantWorkflow.write_ungrounded(["x"])
        self.assertFalse(list(self.tmp_path.iterdir()))

    def test_diagnosis_prompt_forbids_calling_ungrounded_an_agent_fix(self) -> None:
        """Keep unavailable external facts separate from agent behavior defects."""
        prompt: str = ConsultantWorkflow.diagnosis_prompt(self._failures(), "keep behavior", 6, False)
        self.assertIn("UNGROUNDED", prompt)
        self.assertIn("do NOT classify it as AGENT FIX", prompt)
        self.assertIn("fabricated answer is worse than a failing test", prompt)

    def test_diagnosis_prompt_carries_the_chosen_ungrounded_policy(self) -> None:
        """Distinguish stopping from removing ungrounded criteria."""
        stop: str = ConsultantWorkflow.diagnosis_prompt(self._failures(), "d", 6, False, "stop")
        keep: str = ConsultantWorkflow.diagnosis_prompt(self._failures(), "d", 6, False, "continue")
        self.assertIn("change neither the network nor the fixture", stop)
        self.assertNotIn("fixture_expectation_fixer", stop)
        self.assertIn("fixture_expectation_fixer", keep)

    def test_consultant_registry_declares_ungrounded_and_the_fixer_exception(self) -> None:
        """Keep the registry contract required by runner-side ungrounded reporting."""
        consultant: str = Path("registries/agent_network_consultant.hocon").read_text(encoding="utf-8")
        self.assertIn("UNGROUNDED:", consultant)
        self.assertIn("`UNGROUNDED: <fixture>: <toolname>:", consultant)
        self.assertIn("read_thinking_trace", consultant)
        self.assertIn("2b. EXCEPTION", consultant)

    def test_consultant_front_man_can_call_the_trace_reader(self) -> None:
        """Expose every diagnostic tool named by the front man's instructions."""
        path = Path("registries/agent_network_consultant.hocon")
        config = ConfigFactory.parse_string(path.read_text(encoding="utf-8"), basedir=".", resolve=True)
        tools: list[Any] = list(config.get("tools", []))
        front_man: Any = tools[0]

        self.assertIn("read_thinking_trace", front_man.get("tools", []))

    def test_consultant_resolves_the_included_instruction_writer_nodes(self) -> None:
        """Resolve each included writer exactly once while preserving Consultant middleware."""
        path = Path("registries/agent_network_consultant.hocon")
        config = ConfigFactory.parse_string(path.read_text(encoding="utf-8"), basedir=".", resolve=True)
        names: list[str] = []
        instructions_writer: Any | None = None
        for tool in config.get("tools", []):
            name = tool.get("name", "")
            names.append(name)
            if name == "instructions_writer":
                instructions_writer = tool

        self.assertEqual(1, names.count("write_all_instructions"))
        self.assertEqual(1, names.count("instructions_writer"))
        self.assertIsNotNone(instructions_writer)
        middleware: list[Any] = list(instructions_writer.get("middleware", []))
        self.assertIn("ConsultantDefinitionMiddleware", middleware[0].get("class", ""))

    def test_all_passing_consult_logs_the_stuck_patch_error_type(self) -> None:
        """Log an actionable exception type when an all-passing consultation cannot apply its patch."""
        error = StuckPatchError("patch stopped")
        with (
            patch.object(ConsultantWorkflow, "consult", side_effect=error),
            patch.object(ConsultantWorkflow, "write_tool_issues") as write_tool_issues,
            self.assertLogs("network_consultant", level="ERROR") as captured,
        ):
            ConsultantWorkflow.consult_all_passing(object(), "reduce tokens", 2, "example.hocon")

        self.assertIn("StuckPatchError: patch stopped", "\n".join(captured.output))
        write_tool_issues.assert_called_once_with(["patch stopped"])
