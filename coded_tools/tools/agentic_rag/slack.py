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

"""Tool module for reading messages from a Slack channel."""

import json
import os
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

try:
    from slack_sdk.web.async_client import AsyncWebClient
except ImportError:  # pragma: no cover - exercised in environments without the optional dependency
    AsyncWebClient = None


class Slack(CodedTool):
    """
    CodedTool implementation which provides a way to query a slack channel
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]):
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for
                them by the calling agent.  This dictionary is to be treated as
                read-only.

        :param sly_data: A dictionary whose keys are defined by the agent
                hierarchy, but whose values are meant to be kept out of the
                chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool
                implementation adding the data is not invoke()-ed more than
                once.
        """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Get messages on the provided slack channel.

        :param args: Dictionary containing 'channel_name'
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
        :return: Text result from the slack channel,
                    or error message
        """
        # Extract arguments from the input dictionary
        channel_name: str = args.get("channel_name")

        # Validate presence of required inputs
        if not channel_name:
            return "Error: No slack channel name provided."

        slack_token = os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_USER_TOKEN")
        if AsyncWebClient is None or not slack_token:
            return self._mock_response(channel_name)

        client = AsyncWebClient(token=slack_token)
        channel_id = None
        cursor = None
        while channel_id is None:
            channel_response = await client.conversations_list(
                types="public_channel,private_channel", limit=200, cursor=cursor
            )
            channel_id_name_dict = {channel["name"]: channel["id"] for channel in channel_response["channels"]}
            channel_id = channel_id_name_dict.get(channel_name)
            cursor = channel_response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        if not channel_id:
            return f"The {channel_name} channel not found."

        message_response = await client.conversations_history(channel=channel_id)
        messages = [
            {key: message[key] for key in ("user", "text", "ts")}
            for message in message_response["messages"]
            if all(key in message for key in ("user", "text", "ts"))
        ]
        return json.dumps(messages)

    @staticmethod
    def _mock_response(channel_name: str) -> str:
        """Return demo data when Slack is unavailable or not configured."""
        if channel_name == "higher_education":
            return """Opportunity Areas:

Adaptive learning and AI-powered personalization

Migration tools for digital-first course content

Analytics for student engagement and success

Microcredentials aligned with workforce skills

Accessibility innovations for inclusive learning

Ideal Partners: EdTech startups, AI developers, instructional design firms"""

        if channel_name == "retail":
            return """Opportunity Areas:

AI-driven demand forecasting and inventory optimization

Personalized shopping experiences via customer data insights

Seamless omnichannel integration (in-store, mobile, online)

Sustainable packaging and supply chain solutions

Retail media and monetization of customer engagement

Ideal Partners: SaaS providers, AI/ML startups, logistics tech firms,
CX platforms"""

        return """Opportunity Areas:

Process automation and workflow optimization

Data analytics for strategic decision-making

Employee experience and engagement platforms

ESG tracking and sustainability reporting tools

Cybersecurity and compliance automation

Ideal Partners: B2B SaaS companies, AI/analytics startups, HR tech,

fintech solutions"""
