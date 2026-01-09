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

# pylint: disable=import-error
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from apps.slack.api_client import APIClient
from apps.slack.command_handler import CommandHandler
from apps.slack.config import NEURO_SAN_SERVER_HTTP_PORT
from apps.slack.config import SLACK_APP_TOKEN
from apps.slack.config import SLACK_BOT_TOKEN
from apps.slack.conversation_manager import ConversationManager
from apps.slack.event_handler import EventHandler
from apps.slack.network_handler import NetworkHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Initialize app
app = App(token=SLACK_BOT_TOKEN)

# Initialize dependencies
conversation_manager = ConversationManager()
api_client = APIClient(NEURO_SAN_SERVER_HTTP_PORT)
network_handler = NetworkHandler(conversation_manager, api_client)

# Initialize and register handlers
event_handlers = EventHandler(conversation_manager, network_handler)
command_handlers = CommandHandler(api_client)

event_handlers.register(app)
command_handlers.register(app)


def main():
    """Start the Slack bot."""
    if not NEURO_SAN_SERVER_HTTP_PORT:
        raise ValueError("NEURO_SAN_SERVER_HTTP_PORT required")

    print(f"Starting Slack bot on port {NEURO_SAN_SERVER_HTTP_PORT}")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()


if __name__ == "__main__":
    main()
