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
"""Clarification input boundary for Agent Network Consultant workflows."""

from abc import ABC
from abc import abstractmethod


class ConsultantClarificationAnswerer(ABC):
    """Supply one user answer without coupling the workflow to a transport."""

    # Match Studio's bounded five-minute timeout for human input in the run and init commands.
    DEFAULT_TIMEOUT_SECONDS = 300.0

    def answer_all(self, questions: list[str]) -> list[str]:
        """
        Answer a sequence of clarification questions through one transport.

        :param questions: The clarification questions to present in order.
        :return: The corresponding nonempty answers in the same order.
        """
        answers: list[str] = []
        for question in questions:
            answers.append(self.answer(question))
        return answers

    @abstractmethod
    def answer(self, question: str) -> str:
        """
        Return the user's answer to one Agent Network Consultant clarification question.

        :param question: The clarification question to present.
        :return: The nonempty clarification answer.
        :raises RuntimeError: If the selected transport cannot provide an answer.
        :raises TimeoutError: If the selected transport does not answer before its deadline.
        """
        raise NotImplementedError
