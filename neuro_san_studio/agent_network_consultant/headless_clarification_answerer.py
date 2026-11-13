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
"""Nsflow job-file clarification input for Agent Network Consultant."""

from typing import override

from neuro_san_studio.agent_network_consultant.consultant_clarification_answerer import ConsultantClarificationAnswerer
from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles


class HeadlessClarificationAnswerer(ConsultantClarificationAnswerer):
    """Exchange clarification questions and answers through one nsflow job directory."""

    def __init__(
        self,
        job_files: ConsultantJobFiles,
        timeout_seconds: float = ConsultantClarificationAnswerer.DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """
        Store the active job-file transport and clarification deadline.

        :param job_files: The active nsflow job-file interface.
        :param timeout_seconds: The maximum number of seconds to wait for one answer.
        """
        self._job_files = job_files
        self._timeout_seconds = timeout_seconds

    @override
    def answer(self, question: str) -> str:
        """
        Publish one question and wait for nsflow to provide its answer.

        :param question: The clarification question to present.
        :return: The nonempty clarification answer.
        :raises RuntimeError: If no nsflow job-file context is active.
        :raises TimeoutError: If nsflow does not supply an answer before the job-file deadline.
        :raises ValueError: If nsflow supplies an empty answer.
        """
        answer = self._job_files.ask(question, timeout=self._timeout_seconds)
        if not answer:
            raise ValueError("The clarification answer cannot be empty.")
        return answer
