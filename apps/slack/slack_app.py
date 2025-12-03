
# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
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

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from requests import get
from requests import post
from requests.exceptions import HTTPError
from requests.exceptions import RequestException

# pylint: disable=import-error
from slack_bolt import Ack
from slack_bolt import App
from slack_bolt import Say
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Initialize app
load_dotenv()
app: App = App(token=os.environ.get("SLACK_BOT_TOKEN"))
NEURO_SAN_SERVER_HTTP_PORT: str = os.environ.get("NEURO_SAN_SERVER_HTTP_PORT", "8080")


@dataclass
class ThreadContext:
    """Store thread-specific context data."""
    channel_id: str
    thread_ts: str | None
    message_ts: str

    @property
    def thread_key(self) -> str:
        """Generate unique thread key."""
        return f"{self.channel_id}:{self.thread_ts or self.message_ts}"

    @property
    def conversation_thread(self) -> str:
        """Get conversation thread timestamp."""
        return self.thread_ts or self.message_ts


@dataclass
class NetworkCommand:
    """Parsed network command data."""
    network_name: str
    input_prompt: str | None = None
    sly_data: dict[str, Any] | None = None


@dataclass
class MessageContext:
    """Complete message context including thread and Slack functions."""
    thread_ctx: ThreadContext
    say: Say
    logger: Any


class ConversationManager:
    """Manage conversation contexts and thread data."""

    def __init__(self):
        self.contexts: dict[str, Any] = {}
        self.networks: dict[str, str] = {}
        self.sly_data: dict[str, dict[str, Any]] = {}

    def get_network(self, thread_key: str) -> str | None:
        """Get network for a thread."""
        return self.networks.get(thread_key)

    def set_network(self, thread_key: str, network_name: str) -> None:
        """Set network for a thread."""
        self.networks[thread_key] = network_name

    def get_sly_data(self, thread_key: str) -> dict[str, Any] | None:
        """Get sly_data for a thread."""
        return self.sly_data.get(thread_key)

    def set_sly_data(self, thread_key: str, data: dict[str, Any]) -> None:
        """Set sly_data for a thread."""
        self.sly_data[thread_key] = data

    def get_context(self, conversation_key: str) -> dict[str, Any]:
        """Get conversation context."""
        return self.contexts.get(conversation_key, {})

    def set_context(self, conversation_key: str, context: dict[str, Any]) -> None:
        """Set conversation context."""
        self.contexts[conversation_key] = context

    def clear_old_contexts(self, thread_ctx: ThreadContext, network_name: str, logger: Any) -> None:
        """Clear contexts from different networks in the same thread."""
        prefix = f"{thread_ctx.channel_id}:{thread_ctx.conversation_thread}"
        keys_to_delete = [
            k for k in self.contexts
            if k.startswith(prefix) and not k.endswith(f":{network_name}")
        ]

        for key in keys_to_delete:
            del self.contexts[key]
            logger.info(f"Cleared context for different network: {key}")


# Global conversation manager
conversation_manager = ConversationManager()


class CommandParser:
    """Parse network commands."""

    @staticmethod
    def strip_urls(text: str) -> str:
        """Remove angle brackets from Slack URLs."""
        return re.sub(r"<(https?://[^\s>]+)>", r"\1", text)

    @staticmethod
    def strip_bot_mention(text: str) -> str:
        """Remove bot mention from text."""
        return re.sub(r"<@[A-Z0-9]+(?:\|[^>]+)?>", "", text).strip()

    @classmethod
    def parse(cls, text: str, logger: Any) -> NetworkCommand:
        """
        Parse network command.

        Formats:
        - <network_name>
        - <network_name> <input_prompt>
        - <network_name> --sly_data <json>
        - <network_name> <input_prompt> --sly_data <json>
        """
        text = text.strip()
        sly_data = None
        remaining_text = text

        # Extract sly_data if present
        sly_match = re.search(r"--sly_data\s+(\{.*\})", text)
        if sly_match:
            try:
                json_str = sly_match.group(1)
                sly_data = json.loads(cls.strip_urls(json_str))
                logger.info(f"Parsed sly_data: {sly_data}")
                remaining_text = (
                    text[:sly_match.start()].strip() + " " + text[sly_match.end():].strip()
                ).strip()
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse sly_data: {e}")

        # Parse network name and prompt
        parts = remaining_text.split(maxsplit=1)
        network_name = parts[0] if parts else ""
        input_prompt = parts[1] if len(parts) > 1 else None

        return NetworkCommand(network_name, input_prompt, sly_data)


class APIClient:
    """Handle API communication with neuro-san server."""

    def __init__(self, port: str):
        self.port = port
        self.base_url = f"http://localhost:{port}/api/v1"

    def call(self, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make API call to endpoint."""
        url = f"{self.base_url}/{endpoint}"

        if endpoint == "list":
            response = get(url, timeout=30)
        else:
            response = post(url, json=payload, timeout=300)

        response.raise_for_status()
        return response.json()

    def test_connection(self, network_name: str) -> bool:
        """Test if network exists."""
        try:
            self.call(f"{network_name}/streaming_chat", {})
            return True
        except HTTPError:
            return False


# Global API client
api_client = APIClient(NEURO_SAN_SERVER_HTTP_PORT)


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
        self,
        msg_ctx: MessageContext,
        network_name: str,
        sly_data: dict[str, Any] | None
    ) -> None:
        """Acknowledge new network connection."""
        sly_msg = f" with sly_data: `{json.dumps(sly_data)}`" if sly_data else ""

        if self.client.test_connection(network_name):
            msg_ctx.say(
                text=f"Connected to *{network_name}*{sly_msg}. Please provide your input.",
                thread_ts=msg_ctx.thread_ctx.conversation_thread
            )
            msg_ctx.logger.info(f"Connected to network: {network_name}")
        else:
            msg_ctx.say(
                text=f"*{network_name}* is invalid. Please provide a valid agent network to open a new thread.",
                thread_ts=msg_ctx.thread_ctx.conversation_thread
            )
            msg_ctx.logger.warning(f"Invalid network: {network_name}")

    def _build_payload(
        self,
        message: str,
        context: dict[str, Any],
        sly_data: dict[str, Any] | None,
        logger: Any
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
            sly_text = f"\nReturned sly_data:\n```\n{json.dumps(returned_sly, indent=2)}\n```"
            msg_ctx.logger.info(f"Received sly_data: {returned_sly}")

        msg_ctx.say(text=text + sly_text, thread_ts=msg_ctx.thread_ctx.conversation_thread)
        msg_ctx.logger.info("Response sent successfully")


# Global network handler
network_handler = NetworkHandler(conversation_manager, api_client)


@app.event("message")
def handle_message_events(body: dict[str, Any], logger: Any, say: Say) -> None:
    """Handle regular messages - works in DMs without @mention."""
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
            channel_id=event.get("channel"),
            thread_ts=event.get("thread_ts"),
            message_ts=event.get("ts")
        )
        msg_ctx = MessageContext(thread_ctx, say, logger)

        # Strip @mention if present
        message_text = CommandParser.strip_bot_mention(text) if "<@" in text else text
        message_text = message_text.strip()

        if not message_text:
            return

        logger.info(f"Processing message in {thread_ctx.channel_id}, DM: {is_dm}")

        if is_dm:
            existing_network = conversation_manager.get_network(thread_ctx.thread_key)

            if existing_network:
                network_handler.process_message(msg_ctx, existing_network, message_text)
            else:
                command = CommandParser.parse(message_text, logger)
                network_handler.setup_new_network(msg_ctx, command)
        else:
            say(
                text="Please @mention me with a network name",
                thread_ts=thread_ctx.conversation_thread
            )
    # pylint: disable=broad-exception-caught
    except Exception as e:
        logger.error(f"Error in handle_message_events: {e}", exc_info=True)


@app.event("app_mention")
def handle_app_mentions(event: dict[str, Any], say: Say, logger: Any) -> None:
    """Handle @mentions with network name."""
    try:
        logger.info("Received app_mention")

        thread_ctx = ThreadContext(
            channel_id=event.get("channel"),
            thread_ts=event.get("thread_ts"),
            message_ts=event.get("ts")
        )
        msg_ctx = MessageContext(thread_ctx, say, logger)

        raw_text = event.get("text", "").strip()
        if not raw_text:
            say(text="No text in mention!", thread_ts=thread_ctx.conversation_thread)
            return

        cleaned_text = CommandParser.strip_bot_mention(raw_text)
        existing_network = conversation_manager.get_network(thread_ctx.thread_key)

        if existing_network:
            network_handler.process_message(msg_ctx, existing_network, cleaned_text)
        else:
            command = CommandParser.parse(cleaned_text, logger)
            network_handler.setup_new_network(msg_ctx, command)
    # pylint: disable=broad-exception-caught
    except Exception as e:
        logger.error(f"Error in handle_app_mentions: {e}", exc_info=True)
        say(text=f"Error: {e}", thread_ts=event.get("thread_ts") or event.get("ts"))


@app.command("/list_networks")
def list_networks(ack: Ack, respond: Any, logger: Any) -> None:
    """List available networks."""
    ack()

    try:
        logger.info("Fetching networks")
        data = api_client.call("list")
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
            tags_str = f" `{", ".join(tags)}`" if tags else ""

            lines.extend([f"• *{name}*{tags_str}", f"  {desc}", ""])

        respond("\n".join(lines))

    except RequestException as e:
        logger.error(f"Error fetching networks: {e}", exc_info=True)
        respond(f"Error: {e}")


@app.command("/neuro_san_help")
def neuro_san_help(ack: Ack, respond: Any) -> None:
    """Provide usage instructions."""
    ack()

    respond("""*How to use Neuro-SAN:*

*Format:*
• `<network_name>`
• `<network_name> <prompt>`
• `<network_name> --sly_data <json>`
• `<network_name> <prompt> --sly_data <json>`

*Examples:*
• `music_nerd_pro`
• `music_nerd_pro Tell me about jazz`
• `math_guy --sly_data {"x": 7, "y": 6}`

*Note:*
• DMs: Just type the command
• Channels: Mention bot `@BotName <command>`
• Each thread keeps independent context
""")


if __name__ == "__main__":
    if not NEURO_SAN_SERVER_HTTP_PORT:
        raise ValueError("NEURO_SAN_SERVER_HTTP_PORT required")

    print(f"Starting Slack bot on port {NEURO_SAN_SERVER_HTTP_PORT}")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
