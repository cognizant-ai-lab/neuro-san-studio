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

"""Tests for terminal Agent Network Consultant clarification answers."""

from unittest import TestCase
from unittest.mock import Mock

from neuro_san_studio.agent_network_consultant import terminal_clarification_answerer
from neuro_san_studio.agent_network_consultant.terminal_clarification_answerer import TerminalClarificationAnswerer


class TestTerminalClarificationAnswerer(TestCase):
    """Verify bounded terminal input preserves the clarification contract."""

    def test_answer_displays_the_question_and_returns_nonempty_input(self) -> None:
        """Present the exact question and trim the supplied terminal answer."""
        input_reader = Mock(return_value="  account 42  ")
        answerer = TerminalClarificationAnswerer(input_reader=input_reader, timeout_seconds=12.0)

        answer = answerer.answer("Which account?")

        self.assertEqual("account 42", answer)
        input_reader.assert_called_once_with("Which account?\n    your answer: ", timeout=12.0)

    def test_answer_translates_a_terminal_timeout(self) -> None:
        """Expose the timeout through the workflow's standard timeout exception."""
        input_reader = Mock(side_effect=terminal_clarification_answerer.TimeoutOccurred)

        with self.assertRaisesRegex(TimeoutError, "Timed out waiting"):
            TerminalClarificationAnswerer(input_reader=input_reader).answer("Which account?")

    def test_answer_reports_closed_or_empty_terminal_input(self) -> None:
        """Reject both closed input streams and answers containing only whitespace."""
        with self.assertRaisesRegex(RuntimeError, "Terminal input closed"):
            TerminalClarificationAnswerer(input_reader=Mock(side_effect=EOFError)).answer("Which account?")
        with self.assertRaisesRegex(RuntimeError, "No clarification answer"):
            TerminalClarificationAnswerer(input_reader=Mock(return_value="  ")).answer("Which account?")
