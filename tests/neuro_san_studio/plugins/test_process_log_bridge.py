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

"""Tests for ProcessLogBridge error-highlighting and level inference."""

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

    # ---- _ERROR_CUE detection in prefix ----

    def test_error_cue_validation_error_in_prefix(self):
        """Bare 'validation error' text should be escalated to ERROR."""
        bridge = self._make_bridge()
        line = "1 validation error for AgentConfig"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_cue_failed_in_prefix(self):
        """Bare 'failed' text should be escalated to ERROR."""
        bridge = self._make_bridge()
        line = "failed to connect to host localhost:8080"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_cue_cannot_find_in_prefix(self):
        """Bare 'cannot find' text should be escalated to ERROR."""
        bridge = self._make_bridge()
        line = "cannot find module 'neuro_san.coded_tools.foo'"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_cue_not_set_in_prefix(self):
        """Bare 'is not set' text should be escalated to ERROR."""
        bridge = self._make_bridge()
        line = "OPENAI_API_KEY is not set"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_cue_inside_json_does_not_match(self):
        """'failed' inside JSON payload (after '{') must NOT match (#915 guard)."""
        bridge = self._make_bridge()
        line = 'NeuroSan - {"message": "The upload failed gracefully"}'
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    # ---- _ERROR_SIGNATURE detection ----

    def test_error_signature_traceback(self):
        """Traceback header is detected as ERROR."""
        bridge = self._make_bridge()
        line = "Traceback (most recent call last)"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_signature_import_error(self):
        """ImportError: pattern is detected as ERROR."""
        bridge = self._make_bridge()
        line = "ImportError: No module named 'langchain_openai'"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_signature_value_error(self):
        """ValueError: pattern is detected as ERROR."""
        bridge = self._make_bridge()
        line = "ValueError: invalid literal for int() with base 10: 'hello'"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_signature_no_llm_found(self):
        """Framework message 'No fully-specified LLM found' is ERROR."""
        bridge = self._make_bridge()
        line = "No fully-specified LLM found for agent 'frontman'"
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_error_signature_requires_colon(self):
        """Exception name without colon does NOT match _ERROR_SIGNATURE."""
        bridge = self._make_bridge()
        line = "KeyError means the key is missing from the dict"
        assert bridge._infer_level_from_text(line) == logging.INFO  # pylint: disable=protected-access

    # ---- message_type fallback in text ----

    def test_message_type_token_error_in_text(self):
        """Unparsed JSON with 'message_type: Error' should infer ERROR."""
        bridge = self._make_bridge()
        line = 'broken json prefix "message_type": "Error", "message": "oops"'
        assert bridge._infer_level_from_text(line) == logging.ERROR  # pylint: disable=protected-access

    def test_message_type_token_debug_in_text(self):
        """Unparsed JSON with 'message_type: Debug' should infer DEBUG."""
        bridge = self._make_bridge()
        line = 'prefix "message_type": "Debug", "message": "verbose trace"'
        assert bridge._infer_level_from_text(line) == logging.DEBUG  # pylint: disable=protected-access


class TestCountDelimsOutsideQuotes:
    """Tests for the generalized _count_delims_outside_quotes helper."""

    @patch.object(ProcessLogBridge, "__init__", lambda self, **kw: None)
    def _make_bridge(self) -> ProcessLogBridge:
        bridge = ProcessLogBridge.__new__(ProcessLogBridge)
        return bridge

    def test_curly_braces_default(self):
        """Default parameters count curly brace balance."""
        bridge = self._make_bridge()
        assert bridge._count_delims_outside_quotes('{"a": {"b": 1}}') == 0  # pylint: disable=protected-access

    def test_curly_braces_open(self):
        """Unclosed brace returns positive balance."""
        bridge = self._make_bridge()
        assert bridge._count_delims_outside_quotes('{"a": {"b": 1}') == 1  # pylint: disable=protected-access

    def test_square_brackets(self):
        """Passing '['/']' counts bracket balance."""
        bridge = self._make_bridge()
        line = '  ["item1", "item2"'
        assert bridge._count_delims_outside_quotes(line, "[", "]") == 1  # pylint: disable=protected-access

    def test_square_brackets_balanced(self):
        """Closed bracket list returns zero."""
        bridge = self._make_bridge()
        line = '["a", "b", "c"]'
        assert bridge._count_delims_outside_quotes(line, "[", "]") == 0  # pylint: disable=protected-access

    def test_delims_inside_quotes_ignored(self):
        """Delimiters inside double-quoted strings are not counted."""
        bridge = self._make_bridge()
        line = '"contains { and } inside"'
        assert bridge._count_delims_outside_quotes(line) == 0  # pylint: disable=protected-access

    def test_escaped_quote_handling(self):
        """Escaped quotes do not flip the in-string state."""
        bridge = self._make_bridge()
        line = r'{"key": "val with \" escaped"}'
        assert bridge._count_delims_outside_quotes(line) == 0  # pylint: disable=protected-access


class TestApplyStickyLevel:
    """Tests for the sticky-level mechanism in _apply_sticky_level."""

    @patch.object(ProcessLogBridge, "__init__", lambda self, **kw: None)
    def _make_bridge(self) -> ProcessLogBridge:
        bridge = ProcessLogBridge.__new__(ProcessLogBridge)
        return bridge

    def _make_state(self, **overrides):
        """Create a minimal state dict for sticky-level testing."""
        state = {
            "sticky_level": None,
            "sticky_balance": 0,
            "sticky_lines": 0,
            "raw_line": "",
        }
        state.update(overrides)
        return state

    def test_no_sticky_passthrough(self):
        """When no sticky is active and line doesn't open a bracket, level passes through."""
        bridge = self._make_bridge()
        state = self._make_state(raw_line="just a normal line")
        result = bridge._apply_sticky_level(state, logging.INFO)  # pylint: disable=protected-access
        assert result == logging.INFO
        assert state["sticky_level"] is None

    def test_error_line_opening_bracket_starts_sticky(self):
        """An ERROR line ending with '[' activates sticky."""
        bridge = self._make_bridge()
        state = self._make_state(raw_line="2 validation errors for Config [")
        result = bridge._apply_sticky_level(state, logging.ERROR)  # pylint: disable=protected-access
        assert result == logging.ERROR
        assert state["sticky_level"] == logging.ERROR
        assert state["sticky_balance"] == 1

    def test_sticky_escalates_subsequent_lines(self):
        """Once sticky is active, INFO lines are escalated to the sticky level."""
        bridge = self._make_bridge()
        state = self._make_state(
            sticky_level=logging.ERROR,
            sticky_balance=1,
            raw_line='  {"loc": ["field1"], "msg": "required"},',
        )
        result = bridge._apply_sticky_level(state, logging.INFO)  # pylint: disable=protected-access
        assert result == logging.ERROR

    def test_sticky_ends_on_bracket_close(self):
        """Sticky terminates when bracket balance reaches zero."""
        bridge = self._make_bridge()
        state = self._make_state(
            sticky_level=logging.ERROR,
            sticky_balance=1,
            raw_line="]",
        )
        result = bridge._apply_sticky_level(state, logging.INFO)  # pylint: disable=protected-access
        assert result == logging.ERROR  # this line is still escalated
        # but sticky is cleared for the next line
        assert state["sticky_level"] is None
        assert state["sticky_balance"] == 0

    def test_non_error_line_with_bracket_does_not_start_sticky(self):
        """A WARNING line ending with '[' does NOT start sticky (requires ERROR)."""
        bridge = self._make_bridge()
        state = self._make_state(raw_line="some warning list [")
        result = bridge._apply_sticky_level(state, logging.WARNING)  # pylint: disable=protected-access
        assert result == logging.WARNING
        assert state["sticky_level"] is None

    def test_sticky_caps_at_max_lines(self):
        """Sticky terminates after _STICKY_MAX_LINES even without bracket close."""
        bridge = self._make_bridge()
        state = self._make_state(
            sticky_level=logging.ERROR,
            sticky_balance=1,
            sticky_lines=9,
            raw_line="still no closing bracket",
        )
        result = bridge._apply_sticky_level(state, logging.INFO)  # pylint: disable=protected-access
        assert result == logging.ERROR  # last escalated line
        assert state["sticky_level"] is None  # cap reached, cleared
