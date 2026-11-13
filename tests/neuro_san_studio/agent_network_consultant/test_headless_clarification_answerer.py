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

"""Tests for nsflow-backed Agent Network Consultant clarification answers."""

from unittest import TestCase
from unittest.mock import Mock

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.headless_clarification_answerer import HeadlessClarificationAnswerer


class TestHeadlessClarificationAnswerer(TestCase):
    """Verify headless clarification delegates to one captured job-file context."""

    def test_answer_uses_the_injected_job_files(self) -> None:
        """Publish the exact question and return the answer supplied by nsflow."""
        job_files = Mock(spec=ConsultantJobFiles)
        job_files.ask.return_value = "account 42"

        answer = HeadlessClarificationAnswerer(job_files, timeout_seconds=12.0).answer("Which account?")

        self.assertEqual("account 42", answer)
        job_files.ask.assert_called_once_with("Which account?", timeout=12.0)

    def test_answer_rejects_empty_job_file_content(self) -> None:
        """Reject an empty nsflow response instead of passing it into the model."""
        job_files = Mock(spec=ConsultantJobFiles)
        job_files.ask.return_value = ""

        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            HeadlessClarificationAnswerer(job_files).answer("Which account?")
