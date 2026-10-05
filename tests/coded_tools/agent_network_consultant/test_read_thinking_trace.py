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

"""Behavioral tests for managed Network Consultant thinking-trace reads."""

import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from coded_tools.agent_network_consultant.read_thinking_trace import ReadThinkingTrace
from middleware.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant import thinking_trace_collector


class TestReadThinkingTrace(IsolatedAsyncioTestCase):
    """Verify managed reads retain fixture and agent selection behavior."""

    def setUp(self) -> None:
        """Create one isolated thinking-trace directory for each test."""
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Remove the isolated thinking-trace directory after each test."""
        shutil.rmtree(self.tmp_path)

    async def test_lists_and_reads_agent_sections(self) -> None:
        """
        Parse managed trace content and record its path in read history.

        """
        trace_path: Path = self.tmp_path / "run-one" / "failure.hocon.txt"
        trace_path.parent.mkdir()
        trace_path.write_text("--- agent_a ---\nfirst trace\n--- agent_b ---\nsecond trace\n", encoding="utf-8")
        sly_data: dict[str, Any] = {ConsultantState.NETWORK_CONSULTANT_RUN_ID: "run-one"}
        tool = ReadThinkingTrace()

        with patch.object(thinking_trace_collector, "IMPROVEMENT_THINKING_DIR", str(self.tmp_path)):
            available: dict[str, Any] = await tool.async_invoke({"fixture_name": "failure.hocon"}, sly_data)
            selected: dict[str, Any] = await tool.async_invoke(
                {"fixture_name": "failure.hocon", "agent_name": "agent_b"}, sly_data
            )

        self.assertEqual(available.get("available_agents"), ["agent_a", "agent_b"])
        self.assertEqual(selected, {"agent_name": "agent_b", "trace": "second trace"})
        self.assertEqual(sly_data.get("read_file_history"), [str(trace_path.resolve())])

    async def test_reports_a_missing_trace(self) -> None:
        """
        Preserve the Consultant-facing missing-trace error contract.

        """
        sly_data: dict[str, Any] = {ConsultantState.NETWORK_CONSULTANT_RUN_ID: "run-one"}
        with patch.object(thinking_trace_collector, "IMPROVEMENT_THINKING_DIR", str(self.tmp_path)):
            result: str = await ReadThinkingTrace().async_invoke({"fixture_name": "missing.hocon"}, sly_data)

        self.assertEqual(result, "Error: No saved thinking trace found for fixture 'missing.hocon'.")

    async def test_rejects_a_read_without_the_current_run_identifier(self) -> None:
        """Avoid reading another run's traces when shared runtime state lacks its run ID."""
        result: str = await ReadThinkingTrace().async_invoke({"fixture_name": "failure.hocon"}, {})

        self.assertEqual(result, "Error: The Consultant run identifier is missing or invalid.")
