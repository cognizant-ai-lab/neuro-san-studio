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

import logging
import os
import time
import uuid
from collections.abc import Mapping
from typing import Any
from typing import cast

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor
from neuro_san.message.parsers.structure.json_structure_parser import JsonStructureParser

from middleware.agent_network_consultant.consultant_state import ConsultantState

logger = logging.getLogger("network_consultant")


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

    def __init__(self, agent_name: str, thinking_directory: str | None = None) -> None:
        """
        Open an in-process session against one of this Studio's networks.

        :param agent_name: The agent or network name to use.
        :param thinking_directory: The caller-owned directory for this run's diagnostic output.
        """
        logger.info("Opening direct session: agent=%s", agent_name)
        # The Consultant runs without a server, so its external-agent references must also resolve in-process.
        self._session = AgentSessionFactory().create_session(
            session_type="direct",
            agent_name=agent_name,
            use_direct=True,
            metadata={"user_id": os.environ.get("USER", "network_consultant")},
        )
        session_name = agent_name.replace("/", "_").replace("\\", "_")
        session_directory = os.path.join(thinking_directory, session_name) if thinking_directory is not None else None
        self._thinking_file = (
            os.path.join(session_directory, "thinking.txt") if session_directory is not None else None
        )
        self._thinking_directory = os.path.join(session_directory, "agents") if session_directory is not None else None
        self._thread: dict[str, Any] = {
            "last_chat_response": None,
            "prompt": "",
            "timeout": 6000.0,
            "num_input": 0,
            "user_input": None,
            "sly_data": {ConsultantState.NETWORK_CONSULTANT_RUN_ID: uuid.uuid4().hex},
            "chat_filter": {"chat_filter_type": "MAXIMAL"},
        }

    @staticmethod
    def unwrap_json_error(response: str) -> str:
        """
        Unwrap a Neuro SAN JSON error envelope while preserving ordinary responses.

        The shared structure parser recovers JSON from code fences, surrounding prose, and common model-output
        defects. Returning the envelope's text restores physical newlines needed by downstream prefix checks.

        :param response: The Consultant response text.
        :return: The resulting text.
        """
        if not response:
            return response
        parsed = JsonStructureParser().parse_structure(response)
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
        if self._thinking_directory is not None:
            os.makedirs(self._thinking_directory, exist_ok=True)
        processor = StreamingInputProcessor(
            "DEFAULT",
            self._thinking_file,
            self._session,
            self._thinking_directory,
        )
        self._thread.update({"user_input": message})
        logger.info("chat -> sending message (%d chars)", len(message))
        started = time.time()
        run_id = self.sly_data_value(ConsultantState.NETWORK_CONSULTANT_RUN_ID)
        self._thread = processor.process_once(self._thread)
        returned_sly_data: dict[str, Any] = self._thread.get("sly_data") or {}
        if returned_sly_data.get(ConsultantState.NETWORK_CONSULTANT_RUN_ID) is None:
            returned_sly_data.update({ConsultantState.NETWORK_CONSULTANT_RUN_ID: run_id})
            self._thread.update({"sly_data": returned_sly_data})
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

    def run_identifier(self) -> str:
        """
        Return the identifier that isolates resources owned by this Consultant session.

        :return: The unique Consultant run identifier.
        """
        return cast(str, self.sly_data_value(ConsultantState.NETWORK_CONSULTANT_RUN_ID))

    @staticmethod
    def headless_poll_interval() -> float:
        """
        Return the polling interval used for headless clarification answers.

        :return: The polling interval in seconds.
        """
        return ConsultantSession.HEADLESS_POLL_INTERVAL_SECONDS

    HEADLESS_POLL_INTERVAL_SECONDS = 1.0
