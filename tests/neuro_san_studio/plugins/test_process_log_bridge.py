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


class TestProcessLogBridge:
    """
    Covers level-word detection, #915 JSON-guard regression, _ERROR_CUE patterns,
    _ERROR_SIGNATURE patterns, and sticky-level activation.
    """

    @patch.object(ProcessLogBridge, "__init__", lambda self, **kw: None)
    def _make_bridge(self) -> ProcessLogBridge:
        bridge = ProcessLogBridge.__new__(ProcessLogBridge)
        return bridge

    # ---- baseline behaviour ----

    def test_empty_line_returns_default(self):
        """Empty string falls back to default."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("", logging.INFO) == logging.INFO  # pylint: disable=protected-access

    def test_none_returns_default(self):
        """None input falls back to default."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text(None, logging.INFO) == logging.INFO  # pylint: disable=protected-access

    def test_plain_error_prefix(self):
        """Explicit ERROR level word is detected."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("ERROR: something went wrong") == logging.ERROR  # pylint: disable=protected-access

    def test_fatal_maps_to_critical(self):
        """FATAL maps to CRITICAL."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("FATAL: out of memory") == logging.CRITICAL  # pylint: disable=protected-access

    # ---- #915 regression: error inside JSON must NOT match ----

    def test_error_word_inside_json_payload(self):
        """'error' after '{' must not trigger false ERROR (#915)."""
        bridge = self._make_bridge()
        line = (
            '{"message": "Received a StreamingChat request for '
            "'handle error messages and error text from users'\""
            ', "message_type": "Other"}'
        )
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    def test_error_cue_inside_json_no_match(self):
        """'failed' inside JSON payload must NOT match (#915 guard)."""
        bridge = self._make_bridge()
        line = 'NeuroSan - {"message": "The upload failed gracefully"}'
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    # ---- _ERROR_CUE: each pattern family ----

    def test_cue_validation_error(self):
        """'validation error' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("2 validation errors for Config") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_failed(self):
        """'failed' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("failed to connect to host") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_cannot_connect(self):
        """'cannot connect' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("cannot connect to database") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_unable_to(self):
        """'unable to' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("unable to load configuration") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_internal_server_error(self):
        """'internal server error' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("500 internal server error") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_api_key_error(self):
        """'api key error' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("api key error: invalid token") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_is_not_set(self):
        """'is not set' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("OPENAI_API_KEY is not set") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_malformed(self):
        """'malformed' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("malformed JSON in request body") == logging.ERROR  # pylint: disable=protected-access

    def test_cue_checkbox_marker(self):
        """'[x]' nsflow failure marker triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("[x] Agent failed to respond") == logging.ERROR  # pylint: disable=protected-access

    # ---- _ERROR_SIGNATURE: each pattern ----

    def test_signature_traceback(self):
        """'Traceback (most recent call last)' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("Traceback (most recent call last):") == logging.ERROR  # pylint: disable=protected-access

    def test_signature_exception_with_colon(self):
        """'ImportError:' triggers ERROR (case-sensitive [A-Z] + colon)."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("ImportError: No module named 'langchain_openai'") == logging.ERROR  # pylint: disable=protected-access

    def test_signature_no_llm_found(self):
        """'No fully-specified LLM found' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("No fully-specified LLM found for agent") == logging.ERROR  # pylint: disable=protected-access

    def test_signature_construction_errors(self):
        """'errors occurred while constructing' triggers ERROR."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("errors occurred while constructing the agent network") == logging.ERROR  # pylint: disable=protected-access

    # ---- no false positive on benign text ----

    def test_plain_text_no_level_returns_default(self):
        """Normal text with no error markers returns INFO."""
        bridge = self._make_bridge()
        assert bridge._infer_level_from_text("Server started successfully on port 8080") == logging.INFO  # pylint: disable=protected-access
