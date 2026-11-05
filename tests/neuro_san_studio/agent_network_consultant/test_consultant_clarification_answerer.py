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

"""Tests for the Agent Network Consultant clarification-answer boundary."""

from unittest import TestCase
from unittest.mock import Mock

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.headless_clarification_answerer import HeadlessClarificationAnswerer


class TestConsultantClarificationAnswerer(TestCase):
    """Verify the shared answerer behavior applied by every clarification transport."""

    def test_answer_all_preserves_question_order(self) -> None:
        """Return answers in the same order as their corresponding questions."""
        job_files = Mock(spec=ConsultantJobFiles)
        job_files.ask.side_effect = ["first answer", "second answer"]

        answers = HeadlessClarificationAnswerer(job_files).answer_all(["First?", "Second?"])

        self.assertEqual(["first answer", "second answer"], answers)
