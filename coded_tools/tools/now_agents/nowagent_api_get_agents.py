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

import logging
import os
from typing import Any
from typing import Dict

import requests
from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)


class NowAgentAPIGetAgents(CodedTool):
    """
    A tool to discover and retrieve available ServiceNow AI agents from a ServiceNow instance.

    This tool queries the sn_aia_agent table in ServiceNow to get a list of active AI agents
    along with their descriptions and system IDs for further interaction.

    Example usage: See tests in the now_agents module.
    """

    def __init__(self):
        """
        Constructs a NowAgentAPIGetAgents object.

        No initialization parameters required. Configuration is handled through environment variables.
        """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:  # pylint: disable=too-many-locals
        """
        Discovers and retrieves available ServiceNow AI agents from the configured instance.

        This method queries the ServiceNow instance's sn_aia_agent table to get a list of
        AI agents that match the configured query criteria (typically active agents).

        Args:
            args: Dictionary containing the inquiry parameters (not used for agent discovery)
            sly_data: Dictionary for session data management (not used for agent discovery)

        Returns:
            dict: ServiceNow API response containing the list of agents with their details.
                  Response structure includes:
                  - result: List of agent dictionaries with 'description', 'name', and 'sys_id' fields
                  - error: Error message if request fails (included only on error)
                  - status_code: HTTP status code if request fails (included only on error)
                  - error_response: Detailed ServiceNow error response for retry logic (included only on error)
        """
        # Parse the arguments
        servicenow_url: str = self._get_env_variable("SERVICENOW_INSTANCE_URL")
        servicenow_get_agents_query: str = self._get_env_variable("SERVICENOW_GET_AGENTS_QUERY")
        servicenow_user: str = self._get_env_variable("SERVICENOW_USER")
        servicenow_pwd: str = self._get_env_variable("SERVICENOW_PWD")
        logger.debug("ServiceNow URL: %s", servicenow_url)
        # NOTE: Never log credentials (user/pwd)

        tool_name = self.__class__.__name__
        logger.debug("========== Calling %s ==========", tool_name)

        # Build the ServiceNow API URL for agent discovery
        base_url = f"{servicenow_url}api/now/table/sn_aia_agent"
        query_params = f"sysparm_query={servicenow_get_agents_query}"
        field_params = "sysparm_fields=description%2Cname%2Csys_id"
        url = f"{base_url}?{query_params}&{field_params}"

        # Set proper headers
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        # Execute the HTTP request
        response = requests.get(url, auth=(servicenow_user, servicenow_pwd), headers=headers, timeout=30)

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
                "result": [],
                "error": f"HTTP {response.status_code}: Failed to retrieve agents",
                "status_code": response.status_code,
                "error_response": error_response,
            }

        # Decode the JSON response into a dictionary and use the data
        tool_response = response.json()

        logger.debug("-----------------------")
        logger.debug("%s tool response: %s", tool_name, tool_response)
        logger.debug("========== Done with %s ==========", tool_name)
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
            args: Dictionary containing the inquiry parameters
            sly_data: Dictionary for session data management

        Returns:
            dict: ServiceNow API response containing the list of agents with their details
        """
        return self.invoke(args, sly_data)
