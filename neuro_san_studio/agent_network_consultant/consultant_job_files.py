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

"""File exchange between a headless Consultant process and its nsflow job."""

import os
import time


class ConsultantJobFiles:
    """Resolve and manage files exposed by the active nsflow job, when present."""

    @staticmethod
    def active() -> bool:
        """
        Return whether nsflow supplied a complete job-file context.

        :return: Whether both required job environment values are available.
        """
        return bool(os.environ.get("NSFLOW_JOB_ID") and os.environ.get("NSFLOW_JOB_DIR"))

    @staticmethod
    def path(suffix: str) -> str | None:
        """
        Resolve one output path for the active nsflow job.

        :param suffix: The file suffix appended after the job identifier.
        :return: The resolved path, or `None` outside an nsflow job.
        """
        job_id = os.environ.get("NSFLOW_JOB_ID")
        job_dir = os.environ.get("NSFLOW_JOB_DIR")
        if not job_id or not job_dir:
            return None
        return os.path.join(job_dir, f"{job_id}.{suffix}")

    @staticmethod
    def write(suffix: str, content: str) -> None:
        """
        Write one nsflow job result when a job-file context is active.

        :param suffix: The file suffix appended after the job identifier.
        :param content: The complete text to persist.
        """
        path = ConsultantJobFiles.path(suffix)
        if path is None:
            return
        with open(path, "w", encoding="utf-8") as output_file:
            output_file.write(content)

    @staticmethod
    def ask(question: str, poll_interval: float) -> str:
        """
        Publish a clarification question and wait for the nsflow answer file.

        :param question: The clarification question to publish.
        :param poll_interval: Seconds to wait between answer-file checks.
        :return: The stripped answer text.
        :raises RuntimeError: If no nsflow job-file context is active.
        """
        question_path = ConsultantJobFiles.path("question.txt")
        answer_path = ConsultantJobFiles.path("answer.txt")
        if question_path is None or answer_path is None:
            raise RuntimeError("Cannot request a headless answer outside an nsflow job.")
        with open(question_path, "w", encoding="utf-8") as question_file:
            question_file.write(question)
        try:
            while not os.path.exists(answer_path):
                time.sleep(poll_interval)
            with open(answer_path, encoding="utf-8") as answer_file:
                answer = answer_file.read().strip()
            os.remove(answer_path)
            return answer
        finally:
            if os.path.exists(question_path):
                os.remove(question_path)
