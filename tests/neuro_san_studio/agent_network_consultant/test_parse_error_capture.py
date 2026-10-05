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

"""Tests for repeated source-preserving parse-error detection."""

import logging
from unittest import TestCase

from neuro_san_studio.agent_network_consultant.parse_error_capture import ParseErrorCapture


class TestParseErrorCapture(TestCase):
    """Verify only repeated supported parse failures trigger the safe-stop signal."""

    @staticmethod
    def _record(message: str) -> logging.LogRecord:
        """
        Build one warning record for the capture handler.

        :param message: The record message.
        :return: The resulting log record.
        """
        return logging.LogRecord("test", logging.WARNING, __file__, 1, message, (), None)

    def test_unrelated_messages_are_ignored(self) -> None:
        """Ignore warnings that do not identify a supported patch failure."""
        capture = ParseErrorCapture()

        capture.emit(self._record("ordinary warning"))

        self.assertEqual([], capture.messages)
        self.assertFalse(capture.is_stuck())

    def test_supported_error_reaches_threshold(self) -> None:
        """Report a stuck patch after the configured number of matching errors."""
        capture = ParseErrorCapture()

        for _index in range(ParseErrorCapture.REPEAT_THRESHOLD):
            capture.emit(self._record("network could not be parsed"))

        self.assertEqual(ParseErrorCapture.REPEAT_THRESHOLD, len(capture.messages))
        self.assertTrue(capture.is_stuck())

    def test_each_supported_marker_is_recorded(self) -> None:
        """Recognize every parse-error signature used by the source-preserving editor."""
        capture = ParseErrorCapture()

        for marker in ParseErrorCapture.ERROR_MARKERS:
            capture.emit(self._record(f"prefix {marker} suffix"))

        self.assertEqual(len(ParseErrorCapture.ERROR_MARKERS), len(capture.messages))
