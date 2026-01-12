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
crewAI agent executor for an A2A server example
See https://github.com/google/a2a-python/tree/main/examples
"""

from typing_extensions import override

# pylint: disable=import-error
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from agent import CrewAiResearchReport


class CrewAiAgentExecutor(AgentExecutor):
    """Agent executor for crewAI agents

    adapted from https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/helloworld/agent_executor.py
    """

    def __init__(self):
        self.agent = CrewAiResearchReport()

    @override
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        """
        Handles incoming requests that expect a response or a stream of events.
        It processes the user's input (available via context) and uses the event_queue to send back Message
        """
        # Get query from the context
        query: str = context.get_user_input()
        if not context.message:
            raise ValueError("No message provided")

        # Invoke the underlying agent
        result = await self.agent.ainvoke(query)
        await event_queue.enqueue_event(new_agent_text_message(result))

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        """
        Handles requests to cancel an ongoing task. Cancellation is not supported for this example.
        """
        raise NotImplementedError
