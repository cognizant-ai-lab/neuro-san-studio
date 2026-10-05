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
import tempfile
import time
from pathlib import Path


class ConsultantJobFiles:
    """Resolve and manage files exposed by the active nsflow job, when present."""

    # Match Studio's bounded five-minute timeout for human input in the run and init commands.
    ANSWER_TIMEOUT_SECONDS = 300.0

    @staticmethod
    def identifier() -> str | None:
        """
        Return the active nsflow job identifier.

        :return: The job identifier, or `None` outside an nsflow job.
        """
        return os.environ.get("NSFLOW_JOB_ID") or None

    @staticmethod
    def directory() -> Path | None:
        """
        Return the active nsflow job-file directory.

        :return: The job-file directory, or `None` outside an nsflow job.
        """
        directory = os.environ.get("NSFLOW_JOB_DIR")
        return Path(directory) if directory else None

    @staticmethod
    def active() -> bool:
        """
        Return whether nsflow supplied a complete job-file context.

        :return: Whether both required job environment values are available.
        """
        return bool(ConsultantJobFiles.identifier() and ConsultantJobFiles.directory())

    @staticmethod
    def path(suffix: str) -> Path | None:
        """
        Resolve one output path for the active nsflow job.

        :param suffix: The file suffix appended after the job identifier.
        :return: The resolved path, or `None` outside an nsflow job.
        """
        job_id = ConsultantJobFiles.identifier()
        job_dir = ConsultantJobFiles.directory()
        if not job_id or not job_dir:
            return None
        return job_dir / f"{job_id}.{suffix}"

    @staticmethod
    def _write_atomically(path: Path, content: str) -> None:
        """
        Publish complete text through a temporary file on the target filesystem.

        Job sidecars can contain user answers and diagnostic details. The temporary file intentionally retains
        `mkstemp()`'s restrictive permissions when it replaces the destination instead of adopting the broader
        permissions used for user-authored project files.

        :param path: The destination job-file path.
        :param content: The complete text to persist.
        :raises OSError: If the temporary file cannot be written or published.
        """
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output_file:
                output_file.write(content)
            os.replace(temporary_path, path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

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
        ConsultantJobFiles._write_atomically(path, content)

    @staticmethod
    def ask(
        question: str,
        poll_interval: float,
        timeout: float = ANSWER_TIMEOUT_SECONDS,
    ) -> str:
        """
        Publish a clarification question and wait for the nsflow answer file.

        :param question: The clarification question to publish.
        :param poll_interval: Seconds to wait between answer-file checks.
        :param timeout: Maximum seconds to wait for an answer.
        :return: The stripped answer text.
        :raises RuntimeError: If no nsflow job-file context is active.
        :raises TimeoutError: If nsflow does not supply an answer before the deadline.
        :raises ValueError: If the polling interval or timeout is not positive.
        """
        if poll_interval <= 0:
            raise ValueError("The answer polling interval must be positive.")
        if timeout <= 0:
            raise ValueError("The answer timeout must be positive.")
        question_path = ConsultantJobFiles.path("question.txt")
        answer_path = ConsultantJobFiles.path("answer.txt")
        if question_path is None or answer_path is None:
            raise RuntimeError("Cannot request a headless answer outside an nsflow job.")
        ConsultantJobFiles._write_atomically(question_path, question)
        deadline = time.monotonic() + timeout
        try:
            while True:
                try:
                    answer = answer_path.read_text(encoding="utf-8").strip()
                except FileNotFoundError:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(f"No clarification answer received within {timeout:g} seconds.") from None
                    time.sleep(min(poll_interval, remaining))
                else:
                    answer_path.unlink()
                    return answer
        finally:
            question_path.unlink(missing_ok=True)
