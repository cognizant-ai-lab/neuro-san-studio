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

"""Session creation and chat transport for the Network Consultant."""

import json
import logging
import os
import time
from typing import Any

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

logger = logging.getLogger("network_consultant")
THINKING_FILE = "/tmp/network_consultant_thinking.txt"
THINKING_DIR = "/tmp/network_consultant_thinking"


class ConsultantSession:
    """Open and use one Network Consultant agent session."""

    @staticmethod
    def open_session(agent_name: str, connection: str, host: str, port: int) -> tuple[Any, dict[str, Any]]:
        """Open a session against one of this studio's own networks -- "http" talks to a running
        `ns run` server (visible in nsflow); "direct" runs the network in this process instead."""
        logger.info("Opening session: agent=%s connection=%s host=%s port=%d", agent_name, connection, host, port)
        # use_direct governs how THIS network's own external-agent references (e.g. "/agent_network_editor")
        # get resolved. In "direct" mode there's no real server listening, so those must also resolve
        # in-process (True) -- with use_direct=False they'd try an actual HTTP call to host:port and
        # silently fail, leaving the agent with none of its own sub-tools.
        session = AgentSessionFactory().create_session(
            session_type=connection,
            agent_name=agent_name,
            hostname=host,
            port=port,
            use_direct=(connection == "direct"),
            metadata={"user_id": os.environ.get("USER", "network_consultant")},
        )
        thread = {
            "last_chat_response": None,
            "prompt": "",
            "timeout": 6000.0,
            "num_input": 0,
            "user_input": None,
            "sly_data": None,
            "chat_filter": {"chat_filter_type": "MAXIMAL"},
        }
        return session, thread

    @staticmethod
    def unwrap_json_error(response: str) -> str:
        """This network's own config sets error_formatter=json with error_fragments including
        "Error:" -- so whenever a response's text happens to contain "Error:" (e.g. relaying a
        sub-agent's tool-error verbatim, which is completely normal/expected here), neuro-san
        wraps the WHOLE response into {"error": "<escaped text>", "tool": ...}, often fenced in a
        ```json block. That JSON-escapes the original newlines into literal \\n, which breaks every
        line-based prefix check downstream (TOOL_ISSUE:, STRUCTURAL_CHANGE_REQUIRED:, etc., since
        none of them are at the start of a physical line anymore). Unwrap it back to plain text
        with real newlines whenever this envelope is detected; return the input unchanged otherwise.
        """
        if not response:
            return response
        text = response.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[len("json") :]
            text = text.strip()
        if not text.startswith("{"):
            return response
        try:
            parsed = json.loads(text)
        except ValueError:
            return response
        if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
            return parsed.get("error", response)
        return response

    @staticmethod
    def chat(
        session: Any,
        thread: dict[str, Any],
        message: str,
        sly_data: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Send one message on an existing thread; returns (response_text, updated_thread)."""
        if sly_data:
            thread.update({"sly_data": {**(thread.get("sly_data") or {}), **sly_data}})
        os.makedirs(THINKING_DIR, exist_ok=True)
        processor = StreamingInputProcessor("DEFAULT", THINKING_FILE, session, THINKING_DIR)
        thread.update({"user_input": message})
        logger.info("chat -> sending message (%d chars)", len(message))
        started = time.time()
        thread = processor.process_once(thread)
        response = ConsultantSession.unwrap_json_error(thread.get("last_chat_response"))
        logger.info("chat <- response received (%.1fs, %d chars)", time.time() - started, len(response or ""))
        return response, thread

    HEADLESS_POLL_INTERVAL_SECONDS = 1.0
