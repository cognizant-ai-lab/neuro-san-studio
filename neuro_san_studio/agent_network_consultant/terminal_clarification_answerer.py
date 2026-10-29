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
"""Terminal clarification input for Agent Network Consultant."""

from collections.abc import Callable
from typing import override

from timedinput import TimeoutOccurred
from timedinput import timedinput

from neuro_san_studio.agent_network_consultant.consultant_clarification_answerer import ConsultantClarificationAnswerer


class TerminalClarificationAnswerer(ConsultantClarificationAnswerer):
    """Read bounded clarification answers from an interactive terminal."""

    def __init__(
        self,
        input_reader: Callable[..., str] = timedinput,
        timeout_seconds: float = ConsultantClarificationAnswerer.DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Store the terminal input boundary used for one answer.

        :param input_reader: The timeout-aware terminal input function.
        :param timeout_seconds: The maximum number of seconds to wait for one answer.
        """
        self._input_reader = input_reader
        self._timeout_seconds = timeout_seconds

    @override
    def answer(self, question: str) -> str:
        """
        Read one nonempty terminal answer before the configured deadline.

        :param question: The clarification question to present.
        :return: The nonempty clarification answer.
        :raises RuntimeError: If terminal input closes or supplies an empty answer.
        :raises TimeoutError: If no answer arrives before the configured deadline.
        """
        try:
            answer = self._input_reader(
                f"{question}\n    your answer: ",
                timeout=self._timeout_seconds,
            ).strip()
        except TimeoutOccurred as exc:
            raise TimeoutError("Timed out waiting for an Agent Network Consultant clarification answer.") from exc
        except EOFError as exc:
            raise RuntimeError("Terminal input closed before a clarification answer was provided.") from exc
        if not answer:
            raise RuntimeError("No clarification answer was provided.")
        return answer
