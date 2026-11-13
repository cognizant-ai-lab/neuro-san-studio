# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
Tests that DecompositionSolver calls its agents through the ActivationCapsule handed to it in its args.
"""

from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

from neuro_san.interfaces.activation_capsule import ActivationCapsule

from coded_tools.experimental.mdap_decomposer.decomposition_solver import DecompositionSolver
from coded_tools.experimental.mdap_decomposer.neuro_san_solver import NeuroSanSolver

# The agent each of the solver's four callers calls, in set_callers() order.
AGENT_NAMES: list[str] = [
    "my_composition_discriminator",
    "my_decomposer",
    "my_problem_solver",
    "my_solution_discriminator",
]


class TestDecompositionSolver(IsolatedAsyncioTestCase):
    """
    Tests for DecompositionSolver's use of the ActivationCapsule.

    The solver's search is stubbed, so each test checks only how the tool wires its agent callers.
    """

    async def test_agents_are_called_through_the_activation_capsule(self) -> None:
        """
        Each agent caller handed to the solver calls its agent via the capsule's use_tool().
        """
        capsule: MagicMock = MagicMock(spec=ActivationCapsule)
        capsule.use_tool = AsyncMock(return_value="an answer")
        args: dict[str, Any] = {
            "problem": "What is 6 times 7?",
            "tools": {
                "composition_discriminator": AGENT_NAMES[0],
                "decomposer": AGENT_NAMES[1],
                "problem_solver": AGENT_NAMES[2],
                "solution_discriminator": AGENT_NAMES[3],
            },
            "activation_capsule": capsule,
        }
        sly_data: dict[str, Any] = {}
        trace_node: dict[str, Any] = {"extracted_final": "42"}

        with (
            patch.object(NeuroSanSolver, "set_callers", autospec=True) as set_callers,
            patch.object(NeuroSanSolver, "solve", new=AsyncMock(return_value=trace_node)),
        ):
            result: Any = await DecompositionSolver().async_invoke(args, sly_data)

        # The first recorded argument is the solver itself.
        callers: tuple[Any, ...] = set_callers.call_args.args[1:]
        expected_calls: list[Any] = []
        for caller, agent_name in zip(callers, AGENT_NAMES, strict=True):
            await caller.call_agent({"input": "x"})
            expected_calls.append(call(agent_name, {"input": "x"}, sly_data={}))
        self.assertEqual(capsule.use_tool.await_args_list, expected_calls)
        self.assertEqual(result, "42")
        self.assertEqual(sly_data.get("trace_node"), trace_node)

    async def test_missing_activation_capsule_returns_a_message(self) -> None:
        """
        Without an ActivationCapsule no agent can be called, so a message comes back and nothing is solved.
        """
        solve: AsyncMock = AsyncMock()
        sly_data: dict[str, Any] = {}

        with patch.object(NeuroSanSolver, "solve", new=solve), self.assertLogs("DecompositionSolver", level="ERROR"):
            result: Any = await DecompositionSolver().async_invoke({"problem": "What is 6 times 7?"}, sly_data)

        self.assertEqual(result, "No activation_capsule available to call the decomposition agents.")
        self.assertEqual(solve.await_count, 0)
        self.assertEqual(sly_data, {})
