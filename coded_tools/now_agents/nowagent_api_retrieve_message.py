# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import os
import time
from typing import Any
from typing import Dict

import requests
from neuro_san.interfaces.coded_tool import CodedTool


class NowAgentRetrieveMessage(CodedTool):
    """
    A tool to retrieve responses from ServiceNow AI agents.

    This tool polls the ServiceNow external agent execution table to get responses
    from AI agents that were previously sent messages. It implements retry logic
    to handle asynchronous response processing.

    Example usage: See tests in the now_agents module.
    """

    def __init__(self):
        """
        Constructs a NowAgentRetrieveMessage object.

        No initialization parameters required. Configuration is handled through environment variables.
        """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:  # pylint: disable=too-many-locals
        """
        Retrieves responses from a ServiceNow AI agent using the session path.

        This method polls the ServiceNow external agent execution table to get responses
        from an AI agent. It implements retry logic with up to 5 attempts and 5-second
        delays to handle asynchronous processing.

        Args:
            args: Dictionary containing inquiry and agent_id (for logging)
            sly_data: Dictionary containing session_path from previous send_message call

        Returns:
            dict: ServiceNow API response containing the agent's response messages.
                  Response structure includes:
                  - result: List of response records from the external agent execution table
                  - error: Error message if request fails (included only on error)
                  - status_code: HTTP status code if request fails (included only on error)
                  - error_response: Detailed ServiceNow error response for retry logic (included only on error)

        Note:
            Requires session_path in sly_data from a previous NowAgentSendMessage call.

        Raises:
            KeyError: If session_path is missing from sly_data
        """
        # Parse the arguments
        servicenow_url: str = self._get_env_variable("SERVICENOW_INSTANCE_URL")
        servicenow_user: str = self._get_env_variable("SERVICENOW_USER")
        servicenow_pwd: str = self._get_env_variable("SERVICENOW_PWD")
        print(f"ServiceNow URL: {servicenow_url}")
        print(f"user:{servicenow_user}")
        print(f"pwd:{servicenow_pwd}")

        print(f"args: {args}")

        tool_name = self.__class__.__name__
        print(f"========== Calling {tool_name} ==========")

        # Build the ServiceNow external agent execution API URL
        base_url = f"{servicenow_url}api/now/table/sn_aia_external_agent_execution"
        session_path = sly_data["session_path"]
        query_params = f"sysparm_query=direction%3DOUTBOUND%5Esession_path%3D{session_path}"
        url = f"{base_url}?{query_params}"

        # Set proper headers
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        print(f"URL: {url}")

        # Implement polling logic to wait for agent response
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            print(f"Polling attempt {attempt}/{max_attempts}...")

            response = requests.get(url, auth=(servicenow_user, servicenow_pwd), headers=headers, timeout=30)

            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"Status: {response.status_code}, Headers: {response.headers}"
                print(error_msg)
                try:
                    error_response = response.json()
                    print(f"Error Response: {error_response}")
                except (ValueError, TypeError):
                    error_response = response.text
                    print(f"Error Response: {error_response}")

                return {
                    "result": [],
                    "error": f"HTTP {response.status_code}: Failed to retrieve messages",
                    "status_code": response.status_code,
                    "error_response": error_response,
                }

            tool_response = response.json()
            print(f"Response: {tool_response}")

            # Check if we have a valid response with results
            if isinstance(tool_response, dict) and "result" in tool_response:
                if isinstance(tool_response["result"], list) and tool_response["result"]:
                    print("Non-empty result found.")
                    break

            # Wait before next attempt (except on last attempt)
            if attempt < max_attempts:
                print("No response yet, waiting 5 seconds before retry...")
                time.sleep(5)
            else:
                print("Max attempts reached without finding a non-empty result.")

        print("-----------------------")
        print(f"{tool_name} tool response: ", tool_response)
        print(f"========== Done with {tool_name} ==========")

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
        print(f"NowAgent: getting {env_variable_name} from environment variables...")
        env_var = os.getenv(env_variable_name, None)
        if env_var is None:
            print(f"NowAgent: {env_variable_name} is NOT defined")
        else:
            print(f"NowAgent: {env_variable_name} FOUND in environment variables")
        print(env_var)
        return env_var

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Asynchronous version of the invoke method.

        Currently delegates to the synchronous invoke method.

        Args:
            args: Dictionary containing inquiry and agent_id parameters
            sly_data: Dictionary containing session_path from previous send_message call

        Returns:
            dict: ServiceNow API response containing the agent's response messages.
                  Response structure includes:
                  - result: List of response records from the external agent execution table
                  - error: Error message if request fails (included only on error)
                  - status_code: HTTP status code if request fails (included only on error)
                  - error_response: Detailed ServiceNow error response for retry logic (included only on error)
        """
        return self.invoke(args, sly_data)
