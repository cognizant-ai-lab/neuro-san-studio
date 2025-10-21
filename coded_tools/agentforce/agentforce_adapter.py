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
import os
import uuid
from typing import Any
from typing import Dict

import requests

# Salesforce API URLs
BASE_URL = "https://api.salesforce.com/einstein/ai-agent/v1"
SESSIONS_URL = f"{BASE_URL}/sessions"
TIMEOUT_SECONDS = 10


class AgentforceAdapter:
    """
    Adapter for the Agentforce API.
    This adapter allows interacting with the Agentforce API: create a session, post a message, close a session.
    See https://developer.salesforce.com/docs/einstein/genai/guide/agent-api-get-started.html for more details.
    """

    def __init__(
        self,
        my_domain_url: str = None,
        agent_id: str = None,
        client_id: str = None,
        client_secret: str = None,
    ):
        """
        Constructs a Salesforce Agentforce Adapter.
        Uses the passed parameters, if any, or the corresponding environment variables:
        - AGENTFORCE_MY_DOMAIN_URL
        - AGENTFORCE_AGENT_ID
        - AGENTFORCE_CLIENT_ID
        - AGENTFORCE_CLIENT_SECRET

        :param my_domain_url: The URL of the Agentforce domain or None to get it from the environment variables.
        :param agent_id: The ID of the Agentforce agent or None to get it from the environment variables.
        :param client_id: The ID of the Agentforce client or None to get it from the environment variables.
        :param client_secret: The secret of the Agentforce client or None to get it from the environment variables.
        """
        # Get the domain_url and agent_id from the environment variables if not provided
        if my_domain_url is None:
            my_domain_url = AgentforceAdapter._get_env_variable("AGENTFORCE_MY_DOMAIN_URL")
        if agent_id is None:
            agent_id = AgentforceAdapter._get_env_variable("AGENTFORCE_AGENT_ID")

        # Get the client_id and client_secret from the environment variables if not provided
        if client_id is None:
            client_id = AgentforceAdapter._get_env_variable("AGENTFORCE_CLIENT_ID")
        if client_secret is None:
            client_secret = AgentforceAdapter._get_env_variable("AGENTFORCE_CLIENT_SECRET")

        if my_domain_url is None or agent_id is None or client_id is None or client_secret is None:
            print("ERROR: AgentforceAdapter is NOT configured. Please check your parameters or environment variables.")
            # The service is not configured. We cannot query the API, but we can still use mock responses.
            self.is_configured = False
        else:
            # The service is configured. We can query the API.
            self.is_configured = True
            # Keep track of the params
            self.my_domain_url = my_domain_url
            self.agent_id = agent_id
            self.client_id = client_id
            self.client_secret = client_secret

    @staticmethod
    def _get_env_variable(env_variable_name: str) -> str:
        print(f"AgentforceAdapter: getting {env_variable_name} from environment variables...")
        env_var = os.getenv(env_variable_name, None)
        if env_var is None:
            print(f"AgentforceAdapter: {env_variable_name} is NOT defined")
        else:
            print(f"AgentforceAdapter: {env_variable_name} FOUND in environment variables")
        return env_var

    def create_session(self) -> (str, str):
        """
        Creates an Agentforce session.
        :return: A session id and an access token, as strings.
        """
        print("AgentforceAdapter: create_session called")
        # Get an access token
        access_token = self._get_access_token()
        session_id = self._get_session(access_token)
        print(f"    Session id: {session_id}")
        return session_id, access_token

    def _get_access_token(self) -> str:
        """
        Calls the Salesforce API to get an access token.
        :return: An access token, as a string.
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        access_token_url = f"{self.my_domain_url}/services/oauth2/token"
        response = requests.post(access_token_url, headers=headers, data=data, timeout=TIMEOUT_SECONDS)
        access_token = response.json()["access_token"]
        return access_token

    def _get_session(self, access_token: str) -> str:
        """
        Calls the Salesforce API to get a session ID.
        :param access_token: An access token.
        :return: A session ID, as a string.
        """
        uuid_str = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        # print("----Session headers:")
        # print(headers)
        data = {
            "externalSessionKey": uuid_str,
            "instanceConfig": {
                "endpoint": self.my_domain_url,
            },
            "streamingCapabilities": {"chunkTypes": ["Text"]},
            "bypassUser": "true",
        }
        # print("----Session data:")
        # print(data)
        # Convert data to json
        data_json = json.dumps(data)
        open_session_url = f"{BASE_URL}/agents/{self.agent_id}/sessions"
        response = requests.post(open_session_url, headers=headers, data=data_json, timeout=TIMEOUT_SECONDS)
        # print("---- Session:")
        # print(response.json())
        session_id = response.json()["sessionId"]
        return session_id

    @staticmethod
    def close_session(session_id: str, access_token: str):
        """
        Closes an Agentforce session.
        :param session_id: The ID of the session to close.
        :param access_token: The corresponding access token.
        :return: Nothing
        """
        print("AgentforceAdapter: close_session called")
        session_url = f"{SESSIONS_URL}/{session_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-session-end-reason": "UserRequest",
        }
        requests.delete(session_url, headers=headers, timeout=TIMEOUT_SECONDS)
        print(f"    Session {session_id} closed:")

    def post_message(self, message: str, session_id: str = None, access_token: str = None) -> Dict[str, Any]:
        """
        Posts a message to the Agentforce API.
        Creates a new session if none is provided, along with its access_token.
        The session is what allows the Agentforce API to identify the conversation context and keep a conversation
        going.
        :param message: The message to post.
        :param session_id: The ID of the session to use to keep the conversation's context, if any. If None,
        a new session will be created.
        :param access_token:The access token corresponding to the session_id. Can only be None if session_id is None.
        Creating a new session will also create a new access token.
        :return: A dictionary containing:
        - session_id: the session id to use to continue the conversation,
        - access_token: the corresponding access_token
        - response: the response message from Agentforce.
        """
        if session_id in (None, "None"):
            session_id, access_token = self.create_session()
        message_url = f"{SESSIONS_URL}/{session_id}/messages"
        print(f"---- Message URL: {message_url}")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        timestamp = 42
        data = {
            "message": {
                "sequenceId": timestamp,
                "type": "Text",
                "text": message,
            },
            "variables": [],
        }
        # Convert data to json
        data_json = json.dumps(data)
        print(f"---- Data JSON: {data_json}")
        response = requests.post(message_url, headers=headers, data=data_json, timeout=TIMEOUT_SECONDS)
        print(f"---- Response: {response}")
        print("---- Response JSON:")
        print(response.json())
        response_dict = {
            "session_id": session_id,
            "access_token": access_token,
            "response": response.json(),
        }
        return response_dict
