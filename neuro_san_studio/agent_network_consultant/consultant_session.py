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
from collections.abc import Mapping
from typing import Any
from typing import cast

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

logger = logging.getLogger("network_consultant")
THINKING_FILE = "/tmp/network_consultant_thinking.txt"
THINKING_DIR = "/tmp/network_consultant_thinking"


class ConsultantSession:
    """Own one direct agent session and its evolving conversation thread."""

    @staticmethod
    def _text_value(value: Any) -> str | None:
        """
        Read a value through its text-encoding interface.

        :param value: The candidate text value.
        :return: The normalized text, or `None` when the text interface is unavailable.
        """
        encode = getattr(value, "encode", None)
        if not callable(encode):
            return None
        return cast(str, value)

    def __init__(self, agent_name: str) -> None:
        """
        Open an in-process session against one of this Studio's networks.

        :param agent_name: The agent or network name to use.
        """
        logger.info("Opening direct session: agent=%s", agent_name)
        # The Consultant runs without a server, so its external-agent references must also resolve in-process.
        self._session = AgentSessionFactory().create_session(
            session_type="direct",
            agent_name=agent_name,
            use_direct=True,
            metadata={"user_id": os.environ.get("USER", "network_consultant")},
        )
        self._thread: dict[str, Any] = {
            "last_chat_response": None,
            "prompt": "",
            "timeout": 6000.0,
            "num_input": 0,
            "user_input": None,
            "sly_data": None,
            "chat_filter": {"chat_filter_type": "MAXIMAL"},
        }

    @staticmethod
    def unwrap_json_error(response: str) -> str:
        """
        This network's own config sets error_formatter=json with error_fragments including "Error:" -- so whenever
        a response's text happens to contain "Error:" (e.g. relaying a sub-agent's tool-error verbatim, which is
        completely normal/expected here), neuro-san wraps the WHOLE response into {"error": "<escaped text>",
        "tool": ...}, often fenced in a ```json block. That JSON-escapes the original newlines into literal \n,
        which breaks every line-based prefix check downstream (TOOL_ISSUE:, STRUCTURAL_CHANGE_REQUIRED:, etc.,
        since none of them are at the start of a physical line anymore). Unwrap it back to plain text with real
        newlines whenever this envelope is detected; return the input unchanged otherwise.

        :param response: The Consultant response text.
        :return: The resulting text.
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
        if isinstance(parsed, Mapping):
            error_text = ConsultantSession._text_value(parsed.get("error"))
            if error_text is not None:
                return error_text
        return response

    def chat(
        self,
        message: str,
        sly_data: dict[str, Any] | None = None,
    ) -> str:
        """
        Send one message and retain the resulting conversation thread.

        :param message: The message sent to the Consultant or stored in a verdict.
        :param sly_data: The shared agent runtime data.
        :return: The response text from the agent session.
        """
        if sly_data:
            self._thread.update({"sly_data": {**(self._thread.get("sly_data") or {}), **sly_data}})
        os.makedirs(THINKING_DIR, exist_ok=True)
        processor = StreamingInputProcessor("DEFAULT", THINKING_FILE, self._session, THINKING_DIR)
        self._thread.update({"user_input": message})
        logger.info("chat -> sending message (%d chars)", len(message))
        started = time.time()
        self._thread = processor.process_once(self._thread)
        response = ConsultantSession.unwrap_json_error(self._thread.get("last_chat_response"))
        logger.info("chat <- response received (%.1fs, %d chars)", time.time() - started, len(response or ""))
        return response

    def sly_data_value(self, key: str) -> Any:
        """
        Return one value from the current thread's shared agent data.

        :param key: The shared-data key to read.
        :return: The current value, or `None` when the key is unavailable.
        """
        sly_data = self._thread.get("sly_data") or {}
        return sly_data.get(key)

    @staticmethod
    def headless_poll_interval() -> float:
        """
        Return the polling interval used for headless clarification answers.

        :return: The polling interval in seconds.
        """
        return ConsultantSession.HEADLESS_POLL_INTERVAL_SECONDS

    HEADLESS_POLL_INTERVAL_SECONDS = 1.0
