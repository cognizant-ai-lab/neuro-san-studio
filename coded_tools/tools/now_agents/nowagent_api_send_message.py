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

import json
import logging
import os
from typing import Any
from typing import Dict

import requests
from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)


class NowAgentSendMessage(CodedTool):
    """
    A tool to send messages/inquiries to ServiceNow AI agents.

    This tool submits user inquiries to specific ServiceNow AI agents identified by their
    system ID. It handles session management and creates the initial interaction.

    Example usage: See tests in the now_agents module.
    """

    def __init__(self):
        """
        Constructs a NowAgentSendMessage object.

        No initialization parameters required. Configuration is handled through environment variables.
        """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:  # pylint: disable=too-many-locals
        """
        Sends a message/inquiry to a specific ServiceNow AI agent.

        This method submits a user inquiry to a ServiceNow AI agent using the ServiceNow
        Agentic AI API. It creates a new session and stores the session path for response retrieval.

        Args:
            args: Dictionary containing:
                - inquiry (str): The user's question or request
                - agent_id (str): The system ID of the ServiceNow AI agent
            sly_data: Dictionary for session data management (updated with session_path)

        Returns:
            dict: ServiceNow API response containing session and metadata information.
                  Response structure includes:
                  - metadata: Dict with user_id, session_id, and other session details
                  - request_id: ID of the submitted request
                  - error: Error message if request fails (included only on error)
                  - status_code: HTTP status code if request fails (included only on error)
                  - error_response: Detailed ServiceNow error response for retry logic (included only on error)

        Side Effects:
            Updates sly_data with session_path for use in NowAgentRetrieveMessage
        """
        # Parse the arguments
        servicenow_url: str = self._get_env_variable("SERVICENOW_INSTANCE_URL")
        servicenow_caller_email: str = self._get_env_variable("SERVICENOW_CALLER_EMAIL")
        servicenow_user: str = self._get_env_variable("SERVICENOW_USER")
        servicenow_pwd: str = self._get_env_variable("SERVICENOW_PWD")
        logger.debug("ServiceNow URL: %s", servicenow_url)
        # NOTE: Never log credentials (user/pwd)

        logger.debug("args: %s", args)
        inquiry: str = args.get("inquiry")
        agent_id: str = args.get("agent_id")

        tool_name = self.__class__.__name__
        logger.debug("========== Calling %s ==========", tool_name)

        # Build the ServiceNow Agentic AI API URL
        url = f"{servicenow_url}api/sn_aia/agenticai/v1/agent/id/{agent_id}"

        # Set proper headers
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        # Prepare the request payload
        request_payload = {
            "request_id": "56789",
            "metadata": {"email_id": servicenow_caller_email},
            "inputs": [{"content_type": "text", "content": inquiry}],
        }

        # Execute the HTTP POST request
        response = requests.post(
            url, auth=(servicenow_user, servicenow_pwd), headers=headers, data=json.dumps(request_payload), timeout=30
        )

        # Check for HTTP codes other than 200
        if response.status_code != 200:
            error_msg = f"Status: {response.status_code}, Headers: {response.headers}"
            logger.warning(error_msg)
            try:
                error_response = response.json()
                logger.warning("Error Response: %s", error_response)
            except (ValueError, TypeError):
                error_response = response.text
                logger.warning("Error Response: %s", error_response)

            return {
                "result": None,
                "error": f"HTTP {response.status_code}: Failed to send message",
                "status_code": response.status_code,
                "error_response": error_response,
            }

        # Decode the JSON response into a dictionary and use the data
        tool_response = response.json()

        logger.debug("-----------------------")
        logger.debug("%s tool response: %s", tool_name, tool_response)
        logger.debug("========== Done with %s ==========", tool_name)

        # Store session information for response retrieval
        user_id = tool_response["metadata"]["user_id"]
        session_id = tool_response["metadata"]["session_id"]
        sly_data["session_path"] = f"{user_id}_{session_id}"
        # NOTE: sly_data may contain secrets - never log it

        return tool_response

    @staticmethod
    def _get_env_variable(env_variable_name: str) -> str:
        """
        Retrieves an environment variable value with debug logging.

        Args:
            env_variable_name: Name of the environment variable to retrieve

        Returns:
            str: Value of the environment variable, or None if not found
        """
        logger.debug("NowAgent: getting %s from environment variables...", env_variable_name)
        env_var = os.getenv(env_variable_name, None)
        if env_var is None:
            logger.debug("NowAgent: %s is NOT defined", env_variable_name)
        else:
            logger.debug("NowAgent: %s FOUND in environment variables", env_variable_name)
        # NOTE: Never log the actual env var value - it may contain secrets
        return env_var

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Asynchronous version of the invoke method.

        Currently delegates to the synchronous invoke method.

        Args:
            args: Dictionary containing the inquiry and agent_id parameters
            sly_data: Dictionary for session data management

        Returns:
            dict: ServiceNow API response containing session and metadata information.
                  Response structure includes:
                  - metadata: Dict with user_id, session_id, and other session details
                  - request_id: ID of the submitted request
        """
        return self.invoke(args, sly_data)
