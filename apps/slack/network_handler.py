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

from json import dumps
from typing import Any

from requests.exceptions import RequestException

from apps.slack.api_client import APIClient
from apps.slack.conversation_manager import ConversationManager
from apps.slack.dataclass.message_context import MessageContext
from apps.slack.dataclass.network_command import NetworkCommand


class NetworkHandler:
    """Handle network message processing."""

    def __init__(self, manager: ConversationManager, client: APIClient):
        self.manager = manager
        self.client = client

    def setup_new_network(self, msg_ctx: MessageContext, command: NetworkCommand) -> None:
        """Set up a new network connection."""
        if not command.network_name:
            msg_ctx.say(text="Please provide a network name", thread_ts=msg_ctx.thread_ctx.conversation_thread)
            return

        # Store network and sly_data
        self.manager.set_network(msg_ctx.thread_ctx.thread_key, command.network_name)
        msg_ctx.logger.info(f"Set network '{command.network_name}' for thread {msg_ctx.thread_ctx.thread_key}")

        if command.sly_data:
            self.manager.set_sly_data(msg_ctx.thread_ctx.thread_key, command.sly_data)
            msg_ctx.logger.info(f"Stored sly_data for thread {msg_ctx.thread_ctx.thread_key}")

        # Process or acknowledge
        if command.input_prompt:
            self.process_message(msg_ctx, command.network_name, command.input_prompt)
        else:
            self._acknowledge_connection(msg_ctx, command.network_name, command.sly_data)

    def process_message(self, msg_ctx: MessageContext, network_name: str, user_message: str) -> None:
        """Process a message for a network."""
        conversation_key = f"{msg_ctx.thread_ctx.channel_id}:{msg_ctx.thread_ctx.conversation_thread}:{network_name}"

        # Clear old contexts
        self.manager.clear_old_contexts(msg_ctx.thread_ctx, network_name, msg_ctx.logger)

        # Get existing data
        context = self.manager.get_context(conversation_key)
        sly_data = self.manager.get_sly_data(msg_ctx.thread_ctx.thread_key)

        # Build and send request
        payload = self._build_payload(user_message, context, sly_data, msg_ctx.logger)

        try:
            msg_ctx.logger.info(f"Calling network '{network_name}'")
            data = self.client.call(f"{network_name}/streaming_chat", payload)

            # Extract and send response
            response_text = self._extract_response_text(data, msg_ctx.logger)
            self._store_context(data, conversation_key, msg_ctx.logger)
            self._send_response(response_text, data, msg_ctx)

        except RequestException as e:
            msg_ctx.logger.error(f"API error for '{network_name}': {e}", exc_info=True)
            msg_ctx.say(text=f"Error calling API: {e}", thread_ts=msg_ctx.thread_ctx.conversation_thread)

    def _acknowledge_connection(
        self, msg_ctx: MessageContext, network_name: str, sly_data: dict[str, Any] | None
    ) -> None:
        """Acknowledge new network connection."""
        sly_msg = f" with sly_data: `{dumps(sly_data)}`" if sly_data else ""

        if self.client.test_connection(network_name):
            msg_ctx.say(
                text=f"Connected to *{network_name}*{sly_msg}. Please provide your input.",
                thread_ts=msg_ctx.thread_ctx.conversation_thread,
            )
            msg_ctx.logger.info(f"Connected to network: {network_name}")
        else:
            msg_ctx.say(
                text=f"*{network_name}* is invalid. Please provide a valid agent network to open a new thread.",
                thread_ts=msg_ctx.thread_ctx.conversation_thread,
            )
            msg_ctx.logger.warning(f"Invalid network: {network_name}")

    def _build_payload(
        self, message: str, context: dict[str, Any], sly_data: dict[str, Any] | None, logger: Any
    ) -> dict[str, Any]:
        """Build API request payload."""
        payload = {"user_message": {"text": message}}

        if context:
            payload["chat_context"] = context
            logger.info("Using existing context")

        if sly_data:
            payload["sly_data"] = sly_data
            logger.info(f"Including sly_data: {sly_data}")

        return payload

    def _extract_response_text(self, data: dict[str, Any], logger: Any) -> str:
        """Extract response text from API response."""
        try:
            text = (
                data.get("response", {})
                .get("chat_context", {})
                .get("chat_histories", [{}])[-1]
                .get("messages", [{}])[-1]
                .get("text", "")
            )
            if text:
                logger.info(f"Extracted response (length: {len(text)})")
                return text
        except (AttributeError, TypeError, KeyError, IndexError):
            logger.warning("Failed to extract response text")

        return "No response available."

    def _store_context(self, data: dict[str, Any], conversation_key: str, logger: Any) -> None:
        """Store chat context from response."""
        context = data.get("response", {}).get("chat_context")
        if context:
            self.manager.set_context(conversation_key, context)
            logger.info(f"Stored context for {conversation_key}")

    def _send_response(self, text: str, data: dict[str, Any], msg_ctx: MessageContext) -> None:
        """Send response with optional sly_data."""
        returned_sly = data.get("response", {}).get("sly_data", {})
        sly_text = ""

        if returned_sly:
            sly_text = f"\nReturned sly_data:\n```\n{dumps(returned_sly, indent=2)}\n```"
            msg_ctx.logger.info(f"Received sly_data: {returned_sly}")

        msg_ctx.say(text=text + sly_text, thread_ts=msg_ctx.thread_ctx.conversation_thread)
        msg_ctx.logger.info("Response sent successfully")
