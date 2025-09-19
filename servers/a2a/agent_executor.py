
"""
crewAI agent executor for an A2A server example
See https://github.com/google/a2a-python/tree/main/examples
"""

# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san SDK Software in commercial settings.
#
# END COPYRIGHT

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
