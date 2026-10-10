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

"""Session creation and chat transport for the Agent Network Consultant."""

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

from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant.consultant_text import ConsultantText
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor

logger = logging.getLogger(__name__)


class ConsultantSession:
    """Own one direct agent session and its evolving conversation thread."""

    CHAT_FILTER_TYPE = "MAXIMAL"
    # Match the 6,000-second execution bounds of the Designer and Test Generator networks called by Consultant.
    CHAT_TIMEOUT_SECONDS = 6000.0
    FRAMEWORK_ERROR_REQUIRED_KEYS = {"error", "tool"}
    FRAMEWORK_ERROR_ALLOWED_KEYS = {"details", "error", "tool"}

    def __init__(self, agent_name: str, thinking_directory: str | None = None) -> None:
        """
        Open an in-process session against one of this Studio's networks.

        :param agent_name: The agent or network name to use.
        :param thinking_directory: The caller-owned directory for this run's diagnostic output.
        """
        logger.info("Opening direct session: agent=%s", agent_name)
        self._agent_name = agent_name
        # The Agent Network Consultant runs without a server, so external-agent references resolve in-process.
        # A direct session has no authenticated caller, so the OS user provides stable local-session ownership.
        self._session = AgentSessionFactory().create_session(
            session_type="direct",
            agent_name=agent_name,
            use_direct=True,
            metadata={"user_id": os.environ.get("USER", "agent_network_consultant")},
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
            "timeout": self.CHAT_TIMEOUT_SECONDS,
            "num_input": 0,
            "user_input": None,
            "sly_data": {ConsultantState.AGENT_NETWORK_CONSULTANT_RUN_ID: uuid.uuid4().hex},
            "chat_filter": {"chat_filter_type": self.CHAT_FILTER_TYPE},
        }

    def chat(
        self,
        message: str,
        sly_data: dict[str, Any] | None = None,
    ) -> str:
        """
        Send one message and retain the resulting conversation thread.

        :param message: The message sent to the Agent Network Consultant or stored in a verdict.
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
        logger.info("Sending request to agent %s (%d chars)", self._agent_name, len(message))
        started = time.time()
        run_id = self.sly_data_value(ConsultantState.AGENT_NETWORK_CONSULTANT_RUN_ID)
        self._thread = processor.process_once(self._thread)
        returned_sly_data: dict[str, Any] = self._thread.get("sly_data") or {}
        if returned_sly_data.get(ConsultantState.AGENT_NETWORK_CONSULTANT_RUN_ID) is None:
            returned_sly_data.update({ConsultantState.AGENT_NETWORK_CONSULTANT_RUN_ID: run_id})
            self._thread.update({"sly_data": returned_sly_data})
        response_value = self._thread.get("last_chat_response")
        response = ConsultantText.required_text(
            response_value,
            "The Agent Network Consultant session returned a non-text response.",
        )
        framework_error = ConsultantSession._framework_error(response)
        if framework_error is not None:
            tool_name, error_text = framework_error
            safe_tool_name = SensitiveDataRedactor.redact_text(tool_name)
            safe_error_text = SensitiveDataRedactor.redact_text(error_text)
            logger.error(
                "Neuro SAN returned an error response from agent %s: tool=%s error=%s",
                self._agent_name,
                safe_tool_name,
                safe_error_text,
            )
            raise RuntimeError(
                "Neuro SAN returned an error response while running the Agent Network Consultant session "
                f"(tool={safe_tool_name}, error={safe_error_text})."
            )
        logger.info(
            "Received response from agent %s (%.1fs, %d chars)",
            self._agent_name,
            time.time() - started,
            len(response or ""),
        )
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
        Return the identifier that isolates resources owned by this Agent Network Consultant session.

        :return: The unique Agent Network Consultant run identifier.
        """
        return cast(str, self.sly_data_value(ConsultantState.AGENT_NETWORK_CONSULTANT_RUN_ID))

    @staticmethod
    def _framework_error(response: str) -> tuple[str, str] | None:
        """
        Return the tool and error text from a Neuro SAN JSON error envelope.

        The shared structure parser recovers the framework's bare or fenced object and common JSON defects. The
        complete response must be that object, with exactly the formatter's `error` and `tool` fields, so diagnostic
        prose that merely quotes an error-shaped object remains a successful response.

        :param response: The Agent Network Consultant response text.
        :return: The tool and error text, or `None` when the response is not a framework error.
        """
        if not response:
            return None
        stripped_response = response.strip()
        is_bare_object = stripped_response.startswith("{") and stripped_response.endswith("}")
        is_fenced_object = stripped_response.startswith("```json") and stripped_response.endswith("```")
        if not is_bare_object and not is_fenced_object:
            return None
        parsed = JsonStructureParser().parse_structure(stripped_response)
        if isinstance(parsed, Mapping):
            error_text = ConsultantText.text_value(parsed.get("error"))
            tool_name = ConsultantText.text_value(parsed.get("tool"))
            details = parsed.get("details")
            parsed_keys = set(parsed)
            has_required_keys = ConsultantSession.FRAMEWORK_ERROR_REQUIRED_KEYS.issubset(parsed_keys)
            has_only_allowed_keys = parsed_keys.issubset(ConsultantSession.FRAMEWORK_ERROR_ALLOWED_KEYS)
            has_valid_details = details is None or ConsultantText.text_value(details) is not None
            if (
                has_required_keys
                and has_only_allowed_keys
                and error_text is not None
                and tool_name is not None
                and has_valid_details
            ):
                return tool_name, error_text
        return None
