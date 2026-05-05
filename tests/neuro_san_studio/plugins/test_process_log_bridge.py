# Copyright (C) 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

"""Tests for ProcessLogBridge._infer_level_from_text (regression for #915)."""

import logging
from unittest.mock import patch

from neuro_san_studio.plugins.log_bridge.process_log_bridge import ProcessLogBridge


class TestInferLevelFromText:
    """Regression tests for _infer_level_from_text severity inference."""

    @patch.object(ProcessLogBridge, "__init__", lambda self, **kw: None)
    def _make_bridge(self) -> ProcessLogBridge:
        bridge = ProcessLogBridge.__new__(ProcessLogBridge)
        return bridge

    def test_empty_line_returns_default(self):
        """Verify empty string falls back to the provided default level."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("", logging.INFO) == logging.INFO  # pylint: disable=protected-access

    def test_none_returns_default(self):
        """Verify None input falls back to the provided default level."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text(None, logging.INFO) == logging.INFO  # pylint: disable=protected-access

    def test_plain_error_prefix(self):
        """Verify plain ERROR prefix is detected."""
        bridge = self._make_bridge()
        line = "ERROR: something went wrong"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_plain_info_prefix(self):
        """Verify plain INFO prefix is detected."""
        bridge = self._make_bridge()
        line = "INFO starting server on port 8080"
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    def test_plain_warning_prefix(self):
        """Verify plain WARNING prefix is detected."""
        bridge = self._make_bridge()
        line = "WARNING deprecated config key"
        assert bridge._infer_level_from_text(line) == logging.WARNING  # pylint: disable=protected-access

    def test_bracketed_timestamp_with_level(self):
        """Verify level detection in bracketed timestamp format."""
        bridge = self._make_bridge()
        line = "[2026-04-18 12:17:41 UTC] ERROR    NeuroSan - some message"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_pipe_delimited_with_level(self):
        """Verify level detection in pipe-delimited log format."""
        bridge = self._make_bridge()
        line = "2026-04-18 12:17:41 | WARNING  | module:func:42 - msg"
        assert bridge._infer_level_from_text(line) == logging.WARNING  # pylint: disable=protected-access

    # ---- #915 regression: "error" inside JSON payload must NOT match ----

    def test_error_word_inside_json_payload_returns_default(self):
        """Exact scenario from #915: malformed JSON with 'error' in agent description."""
        bridge = self._make_bridge()
        line = (
            '{"message": "Received a StreamingChat request for '
            "'handle error messages and error text from users'\""
            ', "message_type": "Other"}'
        )
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    def test_error_word_in_hocon_description_payload(self):
        """Agent description containing 'error' after a '{' character."""
        bridge = self._make_bridge()
        line = (
            'NeuroSan - {"agent_network_description": "Set instructions for '
            'the basic_helpdesk agent network to handle error messages"}'
        )
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    def test_level_in_prefix_before_json_payload(self):
        """Level word in prefix before '{' should still be detected."""
        bridge = self._make_bridge()
        line = 'ERROR NeuroSan - {"message": "some info message"}'
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_warning_in_prefix_before_json_payload(self):
        """Verify WARNING in prefix before JSON payload is detected."""
        bridge = self._make_bridge()
        line = 'WARNING server - {"status": "degraded"}'
        assert bridge._infer_level_from_text(line) == logging.WARNING  # pylint: disable=protected-access

    # ---- traceback detection still works ----

    def test_traceback_returns_error(self):
        """Verify Traceback line is classified as ERROR."""
        bridge = self._make_bridge()
        line = "Traceback (most recent call last):"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_traceback_in_payload_returns_error(self):
        """Verify Traceback inside a payload is still classified as ERROR."""
        bridge = self._make_bridge()
        line = 'some prefix {"traceback": "Traceback (most recent call last):"}'
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    # ---- no false positives on normal text ----

    def test_plain_text_no_level_returns_default(self):
        """Verify plain text with no level keyword returns default INFO."""
        bridge = self._make_bridge()
        line = "Server started successfully on port 8080"
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    def test_fatal_maps_to_critical(self):
        """Verify FATAL prefix maps to CRITICAL level."""
        bridge = self._make_bridge()
        line = "FATAL: out of memory"
        assert bridge._infer_level_from_text(line) == logging.CRITICAL  # pylint: disable=protected-access

    def test_debug_level(self):
        """Verify DEBUG prefix is detected."""
        bridge = self._make_bridge()
        line = "DEBUG entering function foo"
        assert bridge._infer_level_from_text(line) == logging.DEBUG  # pylint: disable=protected-access

    def test_line_with_only_brace_no_prefix_level(self):
        """Line starting with '{' and no level word should return default."""
        bridge = self._make_bridge()
        line = '{"error": "something broke", "level": "info"}'
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access
