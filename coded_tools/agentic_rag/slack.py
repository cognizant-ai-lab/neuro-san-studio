"""Tool module for reading messages from a slack channel"""

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

import ast
from typing import Any
from typing import Dict
from typing import Literal

from langchain_community.tools.slack.get_channel import SlackGetChannel
from langchain_community.tools.slack.get_message import SlackGetMessage
from neuro_san.interfaces.coded_tool import CodedTool
from pydantic import PydanticUserError

EMPTY: Literal[""] = ""


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

        # SlackGetChannel requires no inputs and returns a str in the
        # following format:
        # '[{"id": "CE", "name": "gen", "created": 15, "num_members": 3}, ...]'
        # SlackGetMessage requires channel_id as an input and returns a str in
        # a following format:
        # '[{"user": "WU0JH", "text": "Yes", "ts": "1744677036.155459"}, ...]'
        try:
            # Get a str of channel ids and names
            channel_id_name_str: str = await SlackGetChannel().ainvoke(input=EMPTY)
            # Convert the str to list
            channel_id_name_list: list = ast.literal_eval(channel_id_name_str)
            # Make a lookup table with channel names as keys and ids as values
            channel_id_name_dict: dict = {channel["name"]: channel["id"] for channel in channel_id_name_list}

            # Get channel id and return the messages if possible.
            channel_id: str = channel_id_name_dict.get(channel_name)
            if channel_id:
                return await SlackGetMessage().ainvoke(channel_id)
            return f"The {channel_name} channel not found."

        # If slack-sdk is not installed, PydanticUserError is triggered
        # Return a mock message depending on the channel_name
        except PydanticUserError:
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
