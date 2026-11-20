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

import asyncio
import os
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from coded_tools.tools.now_agents.nowagent_api_retrieve_message import NowAgentRetrieveMessage

# Mock response data for testing
MOCK_RETRIEVE_RESPONSE = {
    "result": [
        {
            "content": "I can help you troubleshoot your laptop issue. Please describe the problem.",
            "direction": "OUTBOUND",
            "session_path": "test_user_123_session_456",
        }
    ]
}

MOCK_EMPTY_RESPONSE = {"result": []}


class TestNowAgentRetrieveMessage(unittest.TestCase):
    """
    Unit tests for NowAgentRetrieveMessage class.
    """

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.tool = NowAgentRetrieveMessage()
        self.test_args = {
            "inquiry": "Help me with my laptop issue",
            "agent_id": "12345678-1234-1234-1234-123456789abc",
        }
        self.test_sly_data = {"session_path": "test_user_123_session_456"}

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_retrieve_message.requests.get")
    def test_invoke_success_immediate_response(self, mock_get):
        """
        Test successful message retrieval with immediate response.

        This test verifies that the tool correctly retrieves a response from a ServiceNow AI agent
        when the response is available on the first attempt.
        """
        # Mock successful API response on first attempt
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_RETRIEVE_RESPONSE
        mock_get.return_value = mock_response

        # Execute the tool
        result = self.tool.invoke(self.test_args, self.test_sly_data)

        # Verify the result
        self.assertEqual(result, MOCK_RETRIEVE_RESPONSE)
        self.assertIn("result", result)
        self.assertEqual(len(result["result"]), 1)
        self.assertIn("content", result["result"][0])

        # Verify API call was made correctly
        mock_get.assert_called()
        call_args = mock_get.call_args
        self.assertIn("api/now/table/sn_aia_external_agent_execution", call_args[0][0])
        self.assertIn("test_user_123_session_456", call_args[0][0])
        self.assertEqual(call_args[1]["auth"], ("test_user", "test_password"))

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_retrieve_message.requests.get")
    @patch("coded_tools.tools.now_agents.nowagent_api_retrieve_message.time.sleep")
    def test_invoke_success_with_retries(self, mock_sleep, mock_get):
        """
        Test successful message retrieval after retries.

        This test verifies that the tool correctly handles polling with retries
        when the response is not immediately available.
        """
        # Mock empty responses for first few attempts, then success
        empty_response = Mock()
        empty_response.status_code = 200
        empty_response.json.return_value = MOCK_EMPTY_RESPONSE

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = MOCK_RETRIEVE_RESPONSE

        # First 2 polling attempts return empty, 3rd returns data
        mock_get.side_effect = [empty_response, empty_response, success_response]

        # Execute the tool
        result = self.tool.invoke(self.test_args, self.test_sly_data)

        # Verify the result
        self.assertEqual(result, MOCK_RETRIEVE_RESPONSE)

        # Verify retries occurred (3 polling attempts)
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Should sleep twice before the successful attempt

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_retrieve_message.requests.get")
    @patch("coded_tools.tools.now_agents.nowagent_api_retrieve_message.time.sleep")
    def test_invoke_max_retries_reached(self, mock_sleep, mock_get):
        """
        Test behavior when maximum retries are reached without response.

        This test verifies that the tool handles cases where no response is received
        even after all retry attempts.
        """
        # Mock empty responses for all attempts
        empty_response = Mock()
        empty_response.status_code = 200
        empty_response.json.return_value = MOCK_EMPTY_RESPONSE
        mock_get.return_value = empty_response

        # Execute the tool
        result = self.tool.invoke(self.test_args, self.test_sly_data)

        # Verify that empty response is returned after max attempts
        self.assertEqual(result, MOCK_EMPTY_RESPONSE)

        # Verify all 5 polling attempts were made
        self.assertEqual(mock_get.call_count, 5)
        self.assertEqual(mock_sleep.call_count, 4)  # Sleep between attempts 1-4, not after last

    def test_invoke_missing_session_path(self):
        """
        Test handling of missing session_path in sly_data.

        This test verifies that the tool handles missing session information appropriately.
        """
        # Test with missing session_path
        empty_sly_data = {}

        # This should raise a KeyError when trying to access session_path
        with self.assertRaises(KeyError):
            self.tool.invoke(self.test_args, empty_sly_data)

    def test_get_env_variable(self):
        """
        Test environment variable retrieval.

        This test verifies that the _get_env_variable helper method correctly
        retrieves environment variables.
        """
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = self.tool._get_env_variable("TEST_VAR")  # pylint: disable=protected-access
            self.assertEqual(result, "test_value")

        # Test missing environment variable
        result = self.tool._get_env_variable("NONEXISTENT_VAR")  # pylint: disable=protected-access
        self.assertIsNone(result)

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_retrieve_message.requests.get")
    def test_async_invoke(self, mock_get):
        """
        Test asynchronous invoke method.

        This test verifies that the async_invoke method delegates correctly
        to the synchronous invoke method.
        """
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_RETRIEVE_RESPONSE
        mock_get.return_value = mock_response

        # Execute the async tool
        result = asyncio.run(self.tool.async_invoke(self.test_args, self.test_sly_data))

        # Verify the result matches synchronous behavior
        self.assertEqual(result, MOCK_RETRIEVE_RESPONSE)


if __name__ == "__main__":
    unittest.main()
