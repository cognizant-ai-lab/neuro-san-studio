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

"""Behavioral tests for the Network Consultant's append-only scratchpad."""

import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from coded_tools.agent_network_consultant import network_scratchpad
from coded_tools.agent_network_consultant.network_scratchpad import NetworkScratchpad
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME


class TestNetworkScratchpad(IsolatedAsyncioTestCase):
    """Verify scratchpad history persists within a run and resets between runs."""

    def setUp(self) -> None:
        """Create one isolated scratchpad directory for each test."""
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Remove the isolated scratchpad directory after each test."""
        shutil.rmtree(self.tmp_path)

    @staticmethod
    async def _invoke(tool: NetworkScratchpad, args: dict[str, Any]) -> Any:
        """
        Invoke the scratchpad for the isolated test network.

        :param tool: The scratchpad coded tool.
        :param args: The coded-tool input arguments.
        :return: The coded-tool result.
        """
        sly_data: dict[str, Any] = {AGENT_NETWORK_NAME: "example"}
        return await tool.async_invoke(args, sly_data)

    async def test_read_preserves_history_and_write_appends(self) -> None:
        """
        Preserve prior attempts across reads and append the next turn after them.
        """
        with patch.object(network_scratchpad, "SCRATCHPAD_DIR", self.tmp_path.resolve()):
            tool = NetworkScratchpad()
            first_turn = "CURRENT TURN: agent_a changed routing; AWAITING RETEST"
            second_turn = (
                "PRIOR ATTEMPT OUTCOMES: agent_a WORKED\nCURRENT TURN: agent_b changed wording; AWAITING RETEST"
            )

            self.assertEqual(await self._invoke(tool, {"action": "write", "content": first_turn}), {"saved": True})
            first_read: dict[str, str] = await self._invoke(tool, {"action": "read"})
            repeated_read: dict[str, str] = await self._invoke(tool, {"action": "read"})
            self.assertEqual(first_read.get("content"), f"{first_turn}\n")
            self.assertEqual(repeated_read, first_read)

            self.assertEqual(
                await self._invoke(tool, {"action": "write", "content": second_turn}),
                {"saved": True},
            )
            final_read: dict[str, str] = await self._invoke(tool, {"action": "read"})
            self.assertEqual(final_read.get("content"), f"{first_turn}\n{second_turn}\n")

    async def test_fresh_run_cleanup_removes_existing_history(self) -> None:
        """
        Clear accumulated history only when a fresh Consultant run starts.
        """
        with patch.object(network_scratchpad, "SCRATCHPAD_DIR", self.tmp_path.resolve()):
            tool = NetworkScratchpad()
            await self._invoke(tool, {"action": "write", "content": "CURRENT TURN: pending"})

            NetworkScratchpad.clear_for_hocon_file("example.hocon")

            self.assertEqual(await self._invoke(tool, {"action": "read"}), {"content": ""})
