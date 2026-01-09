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

from typing import Any

from requests.exceptions import RequestException

# pylint: disable=import-error
from slack_bolt import Ack
from slack_bolt import App

from apps.slack.api_client import APIClient


class CommandHandler:
    """Handle Slack slash commands."""

    def __init__(self, api_client: APIClient):
        self.api_client = api_client

    def list_networks(self, ack: Ack, respond: Any, logger: Any) -> None:
        """
        List available networks.

        :param ack: Slack acknowledgement function
        :param respond: Slack respond function to send response
        :param logger: Logger instance for logging information
        """
        ack()

        try:
            logger.info("Fetching networks")
            data = self.api_client.call("list")
            agents = data.get("agents", [])

            if not agents:
                respond("No networks available.")
                return

            # Format and send
            agents.sort(key=lambda x: x.get("agent_name", ""))
            lines = ["*Available Networks:*\n"]

            for agent in agents:
                name = agent.get("agent_name", "Unknown")
                desc = " ".join(agent.get("description", "No description").split())
                tags = agent.get("tags", [])
                tags_str = f" `{', '.join(tags)}`" if tags else ""

                lines.extend([f"• *{name}*{tags_str}", f"  {desc}", ""])

            respond("\n".join(lines))

        except RequestException as e:
            logger.error(f"Error fetching networks: {e}", exc_info=True)
            respond(f"Error: {e}")

    def neuro_san_help(self, ack: Ack, respond: Any) -> None:
        """
        Provide usage instructions.
        :param ack: Slack acknowledgement function
        :param respond: Slack respond function to send response
        """
        ack()

        respond(
            """*How to use Neuro-SAN slack app:*

*Format:*
- `<network_name>`
- `<network_name> <prompt>`
- `<network_name> --sly_data <json>`
- `<network_name> <prompt> --sly_data <json>`

*Examples:*
- `music_nerd_pro`
- `music_nerd_pro Tell me about jazz`
- `math_guy --sly_data {"x": 7, "y": 6}`

*Note:*
- DMs: Just type the command
- Channels: Mention bot `@BotName <command>`
- Each thread keeps independent context
"""
        )

    def register(self, app: App) -> None:
        """
        Register all command handlers with the app.

        :param app: Slack app function
        """
        app.command("/list_networks")(self.list_networks)
        app.command("/neuro_san_help")(self.neuro_san_help)
