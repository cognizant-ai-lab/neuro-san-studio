"""
Example of how to use coded tool as a2a client.

Before running this coded tool
- `pip install a2a-sdk crewai`
- run A2A server (servers/a2a/server.py)
- `python server.py`
"""

# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
# END COPYRIGHT

import logging
from typing import Any
from typing import Dict
from uuid import uuid4

import httpx

# pylint: disable=import-error
from a2a.client import A2ACardResolver
from a2a.client import Client
from a2a.client import ClientConfig
from a2a.client import ClientFactory
from a2a.types import AgentCard
from a2a.types import Message
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

from neuro_san.interfaces.coded_tool import CodedTool

# Make sure that the port here matches the one in the server.
BASE_URL = "http://localhost:9999"


class A2aResearchReport(CodedTool):
    """
    CodedTool as an A2A client that connects to a crewAI agents that write
    a report on a given topic in A2A server.

    Adapted from https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/helloworld/test_client.py
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Write a report on a given topic.

        :param args: Dictionary containing "topic".
        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool implementation
            adding the data is not invoke()-ed more than once.

            Keys expected for this implementation are:
                None
        :return: A report or error message
        """
        logger = logging.getLogger(self.__class__.__name__)

        # Extract arguments from the input dictionary
        topic: str = args.get("topic")

        if not topic:
            return "Error: No topic provided."

        logger.info("Writing report on %s", topic)

        # It could take a long time before remote agents response.
        # Adjust the timeout accordingly.
        async with httpx.AsyncClient(timeout=600.0) as httpx_client:

            # Initialize A2ACardResolver
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=BASE_URL)

            try:
                logger.info("Attempting to fetch public agent card from: %s%s", BASE_URL, AGENT_CARD_WELL_KNOWN_PATH)
                agent_card: AgentCard = await resolver.get_agent_card()
                logger.info("Successfully fetched agent card:")
                logger.info(agent_card.model_dump_json(indent=2, exclude_none=True))
            except RuntimeError as runtime_error:
                logger.error("Critical error fetching public agent card: %s", str(runtime_error))
                return "Failed to the agent card. Cannot continue."

            # Create client
            factory = ClientFactory(config=ClientConfig(httpx_client=httpx_client))
            client: Client = factory.create(agent_card)
            logger.info("A2A Client initialized.")

            # Send message and process responses
            message: Message = {
                "role": "user",
                "parts": [{"kind": "text", "text": topic}],
                "messageId": uuid4().hex,
            }

            responses: list[Message] = []
            async for response in client.send_message(message):
                responses.append(response)

            # Last response is typically the final message
            # Convert to a dictionary
            result: dict[str, Any] = responses[-1].model_dump(mode='json', exclude_none=True)
            logger.info("Got the following response: %s", str(result))

            # Extract text from the response
            return result["parts"][-1]["text"]
