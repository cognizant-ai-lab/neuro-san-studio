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

from json import JSONDecodeError
from json import loads
from re import search
from re import sub
from typing import Any

from apps.slack.dataclass.network_command import NetworkCommand


class CommandParser:
    """Parse network commands."""

    @staticmethod
    def strip_urls(text: str) -> str:
        """
        Remove angle brackets from Slack URLs.

        :param text: Input text from sly_data flag

        :return: cleaned string
        """
        return sub(r"<(https?://[^\s>]+)>", r"\1", text)

    @staticmethod
    def strip_bot_mention(text: str) -> str:
        """
        Remove bot mention from text.

        :param text: Input text from app mentions

        :return: cleaned string
        """
        return sub(r"<@[A-Z0-9]+(?:\|[^>]+)?>", "", text).strip()

    @classmethod
    def parse(cls, text: str, logger: Any) -> NetworkCommand:
        """
        Parse network command.

        Formats:
        - <network_name>
        - <network_name> <input_prompt>
        - <network_name> --sly_data <json>
        - <network_name> <input_prompt> --sly_data <json>

        :param text: Input text for parsing
        :param logger: Logger instance for logging information

        :return: Dataclass containing network name, input prompt, and sly data
        """
        text = text.strip()
        sly_data = None
        remaining_text = text

        # Extract sly_data if present
        sly_match = search(r"--sly_data\s+(\{.*\})", text)
        if sly_match:
            try:
                json_str = sly_match.group(1)
                sly_data = loads(cls.strip_urls(json_str))
                logger.info(f"Parsed sly_data: {sly_data}")
                remaining_text = (text[: sly_match.start()].strip() + " " + text[sly_match.end() :].strip()).strip()
            except JSONDecodeError as e:
                logger.warning(f"Failed to parse sly_data: {e}")

        # Parse network name and prompt
        parts = remaining_text.split(maxsplit=1)
        network_name = parts[0] if parts else ""
        input_prompt = parts[1] if len(parts) > 1 else None

        return NetworkCommand(network_name, input_prompt, sly_data)
