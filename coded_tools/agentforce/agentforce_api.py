# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import json
from typing import Any
from typing import Dict
from typing import Optional

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agentforce.agentforce_adapter import AgentforceAdapter

MOCK_SESSION_ID = "06518755-b897-4311-afea-2aab1df77314"
MOCK_SECRET = "1234567890"
MOCK_RESPONSE_MESSAGE_1 = """
{"messages": [{"type": "Inform", "id": "04d35a5d-6011-4eb9-88a9-2897f49a6bdc", "feedbackId": "7d92a297-dc95-4306-b638-42f6e36ddfab", "planId": "7d92a297-dc95-4306-b638-42f6e36ddfab", "isContentSafe": true, "message": "Sure, I can help with that. Could you please provide Jane Doe's email address to look up her cases?", "result": [], "citedReferences": []}], "_links": {"self": null, "messages": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/sessions/06518755-b897-4311-afea-2aab1df77314/messages"}, "messagesStream": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/sessions/06518755-b897-4311-afea-2aab1df77314/messages/stream"}, "session": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/agents/0XxKc000000kvtXKAQ/sessions"}, "end": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/sessions/06518755-b897-4311-afea-2aab1df77314"}}}
"""  # noqa E501
MOCK_RESPONSE_MESSAGE_2 = """
{"messages": [{"type": "Inform", "id": "caf90c84-a150-4ccd-8430-eb29189696ac", "feedbackId": "e24505db-1edd-4b76-b5f5-908be083fc67", "planId": "e24505db-1edd-4b76-b5f5-908be083fc67", "isContentSafe": true, "message": "It looks like there are no recent cases associated with Jane Doe's email address. Is there anything else I can assist you with?", "result": [], "citedReferences": []}], "_links": {"self": null, "messages": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/sessions/06518755-b897-4311-afea-2aab1df77314/messages"}, "messagesStream": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/sessions/06518755-b897-4311-afea-2aab1df77314/messages/stream"}, "session": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/agents/0XxKc000000kvtXKAQ/sessions"}, "end": {"href": "https://api.salesforce.com/einstein/ai-agent/v1/sessions/06518755-b897-4311-afea-2aab1df77314"}}}
"""  # noqa E501
MOCK_RESPONSE_1 = {
    "session_id": MOCK_SESSION_ID,
    "access_token": MOCK_SECRET,
    "response": json.loads(MOCK_RESPONSE_MESSAGE_1),
}
MOCK_RESPONSE_2 = {
    "session_id": MOCK_SESSION_ID,
    "access_token": MOCK_SECRET,
    "response": json.loads(MOCK_RESPONSE_MESSAGE_2),
}


class AgentforceAPI(CodedTool):
    """
    A tool to interact with Agentforce agents using the Agentforce API.
    Example usage: See tests/coded_tools/agentforce/test_agentforce_api.py
    """

    def __init__(self):
        """
        Constructs an AgentforceAPI object.
        """
        # Construct an AgentforceAdapter object using environment variables
        self.agentforce = AgentforceAdapter()

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Calls the Agentforce API to get a response to the user's inquiry. If no session was provided in the sly_data,
        a new session is created. Otherwise, the existing session is reused to keep the conversation going.
        WARNING: The AgentforceAdapter constructor reads the AGENTFORCE_CLIENT_ID and AGENTFORCE_CLIENT_SECRET
        environment variables. If they are NOT provided, this `invoke` call will return mock responses.

        :param args: A dictionary with the following keys:
                    "inquiry": the user request to the Agentforce API, as a string.


        :param sly_data: A dictionary containing parameters that should be kept out of the chat stream.
                         Keys expected for this implementation are:
                         "session_id": (optional) the ID of the session to reuse to keep the conversation going, if any.
                                       If None, a new session is created which means a new conversation is started.
                         "access_token": (optional) the access token corresponding to the session_id. Can only be None if
                                         session_id is None.

        :return: The response message from Agentforce. Note that sly_data dictionary gets updated
        with the Agentforce session_id and access_token.
        """  # noqa E501
        # Parse the arguments
        print(f"args: {args}")
        inquiry: str = args.get("inquiry")
        # Get the session_id and access_token from the sly_data. Having a session_id means the user has already started
        # a conversation with Agentforce and wants to continue it.
        print(f"sly_data: {sly_data}")
        session_id: Optional[str] = sly_data.get("session_id", None)
        access_token: Optional[str] = sly_data.get("access_token", None)

        tool_name = self.__class__.__name__
        print(f"========== Calling {tool_name} ==========")
        print(f"    Inquiry: {inquiry}")
        print(f"    Session ID: {session_id}")

        if self.agentforce.is_configured:
            print("AgentforceAdapter is configured. Fetching response...")
            response = self.agentforce.post_message(inquiry, session_id, access_token)
        else:
            print("WARNING: AgentforceAdapter is NOT configured. Using a mock response")
            if session_id in (None, "None"):
                # No session yet. This is the first request the user makes
                response = MOCK_RESPONSE_1
            else:
                # The user has a session. This is a follow-up request
                response = MOCK_RESPONSE_2

        # Update the sly_data
        sly_data["session_id"] = response["session_id"]
        sly_data["access_token"] = response["access_token"]
        tool_response = response["response"]["messages"][0]["message"]

        print("-----------------------")
        print(f"{tool_name} tool response: ", tool_response)
        print(f"Updated sly_data: {sly_data}")
        print(f"========== Done with {tool_name} ==========")
        return tool_response

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)


# Example usage: See tests/coded_tools/agentforce/test_agentforce_api.py
