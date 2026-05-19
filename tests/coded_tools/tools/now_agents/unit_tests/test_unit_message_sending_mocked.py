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
import json
import os
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from coded_tools.tools.now_agents.nowagent_api_send_message import NowAgentSendMessage

# Mock response data for testing
MOCK_SEND_RESPONSE = {"metadata": {"user_id": "test_user_123", "session_id": "session_456"}, "status": "message_sent"}


class TestNowAgentSendMessage(unittest.TestCase):
    """
    Unit tests for NowAgentSendMessage class.
    """

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.tool = NowAgentSendMessage()
        self.test_args = {
            "inquiry": "Help me with my laptop issue",
            "agent_id": "12345678-1234-1234-1234-123456789abc",
        }
        self.test_sly_data = {}

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_CALLER_EMAIL": "test@example.com",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_send_message.requests.post")
    def test_invoke_success(self, mock_post):
        """
        Test successful message sending to ServiceNow agent.

        This test verifies that the tool correctly sends a message to a ServiceNow AI agent
        and properly manages session data.
        """
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_SEND_RESPONSE
        mock_post.return_value = mock_response

        # Execute the tool
        result = self.tool.invoke(self.test_args, self.test_sly_data)

        # Verify the result
        self.assertEqual(result, MOCK_SEND_RESPONSE)
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"]["user_id"], "test_user_123")

        # Verify session_path was set in sly_data
        expected_session_path = "test_user_123_session_456"
        self.assertEqual(self.test_sly_data["session_path"], expected_session_path)

        # Verify API call was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        expected_url = (
            "https://test.service-now.com/api/sn_aia/agenticai/v1/agent/id/12345678-1234-1234-1234-123456789abc"
        )
        self.assertEqual(call_args[0][0], expected_url)
        self.assertEqual(call_args[1]["auth"], ("test_user", "test_password"))

        # Verify request payload structure

        payload = json.loads(call_args[1]["data"])
        self.assertEqual(payload["metadata"]["email_id"], "test@example.com")
        self.assertEqual(payload["inputs"][0]["content"], "Help me with my laptop issue")

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_CALLER_EMAIL": "test@example.com",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_send_message.requests.post")
    @patch("coded_tools.tools.now_agents.nowagent_api_send_message.logger")
    def test_invoke_authentication_failure(self, mock_logger, mock_post):
        """
        Test handling of authentication failure.

        This test verifies that the tool properly handles 401 authentication errors
        from the ServiceNow API and logs error information.
        """
        # Mock 401 authentication error
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"error": {"message": "User Not Authenticated"}}
        mock_post.return_value = mock_response

        # Execute the tool and expect error response instead of SystemExit
        result = self.tool.invoke(self.test_args, self.test_sly_data)

        # Verify error response structure
        self.assertIn("error", result)
        self.assertIn("status_code", result)
        self.assertIn("error_response", result)
        self.assertEqual(result["status_code"], 401)
        self.assertIsNone(result["result"])

        # Verify error information was logged
        error_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "Status: 401" in str(call) or "Error Response:" in str(call)
        ]
        self.assertTrue(len(error_calls) >= 2, "Error messages should be logged")

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_CALLER_EMAIL": "test@example.com",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_send_message.requests.post")
    def test_invoke_missing_agent_id(self, mock_post):
        """
        Test handling of missing agent_id parameter.

        This test verifies that the tool handles missing required parameters gracefully.
        """
        # Test with missing agent_id
        args_missing_agent = {"inquiry": "Help me"}

        # The tool should still attempt the call but with None agent_id
        # This will result in an invalid URL, but we're testing parameter handling
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not Found"}
        mock_post.return_value = mock_response

        # Execute the tool and expect error response instead of SystemExit
        result = self.tool.invoke(args_missing_agent, self.test_sly_data)

        # Verify error response structure
        self.assertIn("error", result)
        self.assertIn("status_code", result)
        self.assertIn("error_response", result)
        self.assertEqual(result["status_code"], 404)

    @patch("coded_tools.tools.now_agents.nowagent_api_send_message.logger")
    def test_get_env_variable(self, mock_logger):
        """
        Test environment variable retrieval.

        This test verifies that the _get_env_variable helper method correctly
        retrieves environment variables.
        """
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = self.tool._get_env_variable("TEST_VAR")  # pylint: disable=protected-access
            self.assertEqual(result, "test_value")

        # Test missing environment variable - should log NOT defined message
        result = self.tool._get_env_variable("NONEXISTENT_VAR")  # pylint: disable=protected-access
        self.assertIsNone(result)

        # Verify the "NOT defined" message was logged
        not_defined_calls = [
            call
            for call in mock_logger.debug.call_args_list
            if "is NOT defined" in str(call) and "NONEXISTENT_VAR" in str(call)
        ]
        self.assertTrue(len(not_defined_calls) >= 1, "NOT defined message should be logged")

    @patch.dict(
        os.environ,
        {
            "SERVICENOW_INSTANCE_URL": "https://test.service-now.com/",
            "SERVICENOW_CALLER_EMAIL": "test@example.com",
            "SERVICENOW_USER": "test_user",
            "SERVICENOW_PWD": "test_password",
        },
    )
    @patch("coded_tools.tools.now_agents.nowagent_api_send_message.requests.post")
    def test_async_invoke(self, mock_post):
        """
        Test asynchronous invoke method.

        This test verifies that the async_invoke method delegates correctly
        to the synchronous invoke method.
        """
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_SEND_RESPONSE
        mock_post.return_value = mock_response

        # Execute the async tool
        result = asyncio.run(self.tool.async_invoke(self.test_args, self.test_sly_data))

        # Verify the result matches synchronous behavior
        self.assertEqual(result, MOCK_SEND_RESPONSE)


if __name__ == "__main__":
    unittest.main()
