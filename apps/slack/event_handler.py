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

# pylint: disable=import-error
from slack_bolt import App
from slack_bolt import Say

from apps.slack.command_parser import CommandParser
from apps.slack.conversation_manager import ConversationManager
from apps.slack.dataclass.message_context import MessageContext
from apps.slack.dataclass.thread_context import ThreadContext
from apps.slack.network_handler import NetworkHandler


class EventHandler:
    """Handle Slack events."""

    def __init__(self, conversation_manager: ConversationManager, network_handler: NetworkHandler):
        self.conversation_manager = conversation_manager
        self.network_handler = network_handler

    def handle_message(self, body: dict[str, Any], logger: Any, say: Say) -> None:
        """
        Handle regular messages - works in DMs without @mention.
        :param body: The event body from Slack containing event details
        :param logger: Logger instance for logging information
        :param say: Slack say function to send messages
        """
        try:
            event = body.get("event", {})

            # Skip bot messages and app_mention subtypes
            if event.get("bot_id") or event.get("subtype") == "app_mention":
                return

            text = event.get("text", "")
            channel_type = event.get("channel_type", "")
            is_dm = channel_type in ["im", "mpim"]

            # Skip channel messages with @mentions
            if "<@" in text and not is_dm:
                return

            # Create contexts
            thread_ctx = ThreadContext(
                channel_id=event.get("channel"), thread_ts=event.get("thread_ts"), message_ts=event.get("ts")
            )
            msg_ctx = MessageContext(thread_ctx, say, logger)

            # Strip @mention if present
            message_text = CommandParser.strip_bot_mention(text) if "<@" in text else text
            message_text = message_text.strip()

            if not message_text:
                return

            logger.info(f"Processing message in {thread_ctx.channel_id}, DM: {is_dm}")

            if is_dm:
                existing_network = self.conversation_manager.get_network(thread_ctx.thread_key)

                if existing_network:
                    self.network_handler.process_message(msg_ctx, existing_network, message_text)
                else:
                    command = CommandParser.parse(message_text, logger)
                    self.network_handler.setup_new_network(msg_ctx, command)
            else:
                say(text="Please @mention me with a network name", thread_ts=thread_ctx.conversation_thread)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            logger.error(f"Error in handle_message: {e}", exc_info=True)

    def handle_app_mention(self, event: dict[str, Any], say: Say, logger: Any) -> None:
        """
        Handle @mentions with network name.
        :param event: The event data from Slack containing mention details
        :param say: Slack say function to send messages
        :param logger: Logger instance for logging information
        """
        try:
            logger.info("Received app_mention")

            thread_ctx = ThreadContext(
                channel_id=event.get("channel"), thread_ts=event.get("thread_ts"), message_ts=event.get("ts")
            )
            msg_ctx = MessageContext(thread_ctx, say, logger)

            raw_text = event.get("text", "").strip()
            if not raw_text:
                say(text="No text in mention!", thread_ts=thread_ctx.conversation_thread)
                return

            cleaned_text = CommandParser.strip_bot_mention(raw_text)
            existing_network = self.conversation_manager.get_network(thread_ctx.thread_key)

            if existing_network:
                self.network_handler.process_message(msg_ctx, existing_network, cleaned_text)
            else:
                command = CommandParser.parse(cleaned_text, logger)
                self.network_handler.setup_new_network(msg_ctx, command)
        # pylint: disable=broad-exception-caught
        except Exception as e:
            logger.error(f"Error in handle_app_mention: {e}", exc_info=True)
            say(text=f"Error: {e}", thread_ts=event.get("thread_ts") or event.get("ts"))

    def register(self, app: App) -> None:
        """Register all event handlers with the app."""
        app.event("message")(self.handle_message)
        app.event("app_mention")(self.handle_app_mention)
