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
"""
Tests that CallAgent calls agents through the ActivationCapsule handed to it in its args.
"""

from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from neuro_san.interfaces.activation_capsule import ActivationCapsule

from neuro_san_studio.coded_tools.call_agent import CallAgent


class TestCallAgent(IsolatedAsyncioTestCase):
    """
    Tests for CallAgent's use of the ActivationCapsule.
    """

    async def test_calls_agent_through_activation_capsule(self):
        """
        The agent is called via the capsule's use_tool(), with the mode merged into the tool args.
        """
        capsule: MagicMock = MagicMock(spec=ActivationCapsule)
        capsule.use_tool = AsyncMock(return_value="the answer")
        sly_data: dict[str, Any] = {"key": "value"}
        args: dict[str, Any] = {
            "tool_args": {"input": "hello"},
            "agent_name": "my_agent",
            "mode": "Fulfill",
            "activation_capsule": capsule,
        }

        result: str = await CallAgent().async_invoke(args, sly_data)

        self.assertEqual("the answer", result)
        capsule.use_tool.assert_awaited_once_with("my_agent", {"input": "hello", "mode": "Fulfill"}, sly_data=sly_data)

    async def test_missing_activation_capsule_raises(self):
        """
        Without an ActivationCapsule there is no way to call the agent, so a ValueError is raised.
        """
        args: dict[str, Any] = {"tool_args": {"input": "hello"}, "agent_name": "my_agent"}

        with self.assertRaises(ValueError):
            await CallAgent().async_invoke(args, {})
