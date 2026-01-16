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

from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.activations.branch_activation import BranchActivation

from coded_tools.experimental.mdap_decomposer.coded_tool_agent_caller import CodedToolAgentCaller
from coded_tools.experimental.mdap_decomposer.neuro_san_solver import NeuroSanSolver
from coded_tools.experimental.mdap_decomposer.solver_parsing import SolverParsing


class DecompositionSolver(BranchActivation, CodedTool):
    """
    A CodedTool implementation that uses the NeuroSanSolver to break down
    a problem into smaller subproblems inspired by the MAKER algorithm.

    Note that we are also doubly-inheriting from BranchActivation to get access to
    the ability to call agents from a CodedTool via its use_tool() method.
    This happens inside the CodedToolAgentCaller heavily used by this class.

    Upon activation by the agent hierarchy, a CodedTool will have either its
    async_invoke() (preferred) or synchronous invoke() method called by the system.

    Implementations are expected to clean up after themselves.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        """
        This method is provided as a convenience for an "easy" start to using
        coded-tools.

        Know that any CodedTool is run within the confines of a Python asynchronous
        EventLoop. Any synchronous blocking that happens - like making a call to a
        web service over a socket, or something that inherently sleep()s - *will* also
        block all other agent operations.  This is not so bad in a low-traffic or
        test environment, but when scaling up, you really really want to embrace
        and override the async_invoke() method below instead of this one.

        The idea is to allow easy development of CodedTools and use of invoke() is not so bad in a
        low-traffic or test environment. However, when scaling up, you really really want to embrace
        and override the async_invoke() method below instead of this one if at all possible,
        as it is inherently more efficient.

        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.
        :return: A return value that goes into the chat stream.
        """
        # Do not raise an exception here, but pass instead.
        # This allows for fully asynchronous CodedTools to not have to worry about
        # the synchronous bits.

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
        """
        Called when the coded tool is invoked asynchronously by the agent hierarchy.
        Strongly consider overriding this method instead of the "easier" synchronous
        invoke() version above when the possibility of making any kind of call that could block
        (like sleep() or a socket read/write out to a web service) is within the
        scope of your CodedTool and can be done asynchronously, especially within
        the context of your CodedTool running within a server.

        If you find your CodedTools can't help but synchronously block,
        strongly consider looking into using the asyncio.to_thread() function
        to not block the EventLoop for other requests.
        See: https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread
        Example:
            async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Any:
                return await asyncio.to_thread(self.invoke, args, sly_data)

        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.
        :return: A return value that goes into the chat stream.
        """

        # Create the solver and use some of the arguments to configure it
        solver = NeuroSanSolver(
            winning_vote_count=args.get("winning_vote_count", 2),
            candidate_count=args.get("candidate_count"),
            number_of_votes=args.get("number_of_votes"),
            solution_candidate_count=args.get("solution_candidate_count"),
        )

        tools: Dict[str, str] = {}
        tools = args.get("tools", tools)

        # Set up the AgentCallers to use this CodedTool as a basis for calling the agents.
        parsing = SolverParsing()
        composition_discriminator_caller = CodedToolAgentCaller(
            self, parsing, name=tools.get("composition_discriminator")
        )
        decomposer_caller = CodedToolAgentCaller(self, parsing=None, name=tools.get("decomposer"))
        problem_solver_caller = CodedToolAgentCaller(self, parsing=None, name=tools.get("problem_solver"))
        solution_discriminator_caller = CodedToolAgentCaller(self, parsing, name=tools.get("solution_discriminator"))
        solver.set_callers(
            composition_discriminator_caller,
            decomposer_caller,
            problem_solver_caller,
            solution_discriminator_caller,
        )

        problem: str = args.get("problem")
        max_depth: int = args.get("max_depth", 5)
        if max_depth is None:
            max_depth = 5

        # Call the solver to solve the problem by decomposition
        trace_node: dict[str, Any] = await solver.solve(problem, depth=0, max_depth=max_depth)

        # Publish the trace node to the bulletin board for return.
        # This can be a large dictionary describing the process of decomposition into a solution tree.
        sly_data["trace_node"] = trace_node

        # Return the extracted final answer as the text answer for this tool.
        result: str = trace_node.get("extracted_final")
        return result
