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

from unittest import TestCase

from coded_tools.tools.agentforce.agentforce_api import MOCK_RESPONSE_1
from coded_tools.tools.agentforce.agentforce_api import MOCK_RESPONSE_2
from coded_tools.tools.agentforce.agentforce_api import MOCK_SECRET
from coded_tools.tools.agentforce.agentforce_api import MOCK_SESSION_ID
from coded_tools.tools.agentforce.agentforce_api import AgentforceAPI


class TestAgentforceAPI(TestCase):
    """
    Unit tests for AgentforceAPI class.
    """

    def test_invoke(self):
        """
        Tests the invoke method of the AgentforceAPI CodedTool.
        The AgentforceAPI CodedTool should query the Agentforce agent and return a response.
        Environment variables are NOT set for this test, so we expect the responses to be mocked.
        """
        agentforce_tool = AgentforceAPI()
        # Ask a first question
        inquiry_1 = "Can you give me a list of Jane Doe's most recent cases?"
        sly_data = {}
        # Get the response
        response_1 = agentforce_tool.invoke(args={"inquiry": inquiry_1}, sly_data=sly_data)
        # Check the response contains the expected string.
        self.assertEqual(MOCK_RESPONSE_1["response"]["messages"][0]["message"], response_1)
        # Check the sly_data dictionary has been updated and now contains the session_id and access_token
        self.assertEqual(MOCK_SESSION_ID, sly_data.get("session_id", None))
        self.assertEqual(MOCK_SECRET, sly_data.get("access_token", None))

        # Follow up with what Agentforce asked for. Session exists now, reuse it to continue the conversation instead
        # of starting a new one
        inquiry_2 = "jdoe@example.com"
        params = {"inquiry": inquiry_2}
        response_2 = agentforce_tool.invoke(args=params, sly_data=sly_data)
        # Check the response contains the expected string.
        self.assertEqual(MOCK_RESPONSE_2["response"]["messages"][0]["message"], response_2)
        # Check the session is still the same
        self.assertEqual(MOCK_SESSION_ID, sly_data.get("session_id", None))
        self.assertEqual(MOCK_SECRET, sly_data.get("access_token", None))

        # Close the session
        agentforce_tool.agentforce.close_session(sly_data.get("session_id", None), sly_data.get("access_token", None))
