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
"""
Policy tests for WriteAllInstructions' non-LLM half: how the dispatch list is
deduplicated, how a writer's JSON answer is extracted and written into the
agent_network_definition, and which malformed answers degrade to per-agent
errors. The LLM fan-out half needs a live framework and is exercised by the
network itself.

Skipped (not failed) in environments whose neuro-san predates the imports
write_all_instructions needs, so the suite still collects everywhere.
"""

from typing import Any
from unittest import TestCase

import pytest

pytest.importorskip("coded_tools.agent_network_instructions_editor.write_all_instructions")

# The import must stay below importorskip so old environments skip cleanly,
# and the tests reach the class's protected helpers by design.
# pylint: disable=wrong-import-position,protected-access
from coded_tools.agent_network_instructions_editor.write_all_instructions import WriteAllInstructions  # noqa: E402

AGENT_NETWORK_DEFINITION = "agent_network_definition"


class TestParseWriterFields(TestCase):
    """Extraction of the JSON object from a writer's answer."""

    def test_bare_json_object(self):
        """The instructed format — a bare JSON object — parses directly."""
        fields = WriteAllInstructions._parse_writer_fields('{"instructions": "do x", "description": "does x"}')
        self.assertEqual(fields, {"instructions": "do x", "description": "does x"})

    def test_fenced_and_prose_wrapped_objects_are_recovered(self):
        """Code fences or a sentence of prose around the object still parse."""
        fenced = '```json\n{"instructions": "do x"}\n```'
        prose = 'Here is the result:\n{"description": "does x"}\nDone.'
        self.assertEqual(WriteAllInstructions._parse_writer_fields(fenced), {"instructions": "do x"})
        self.assertEqual(WriteAllInstructions._parse_writer_fields(prose), {"description": "does x"})

    def test_non_object_answers_are_rejected(self):
        """Garbage, bare strings, and JSON non-objects all yield None."""
        for bad in ("no json here", '"just a string"', "[1, 2]", "{broken", None):
            self.assertIsNone(WriteAllInstructions._parse_writer_fields(bad))

    def test_near_json_answers_are_repaired(self):
        """json_repair recovers the near-JSON shapes models actually emit."""
        literal_newline = '{"instructions": "line one\nline two", "description": "does x"}'
        self.assertEqual(
            WriteAllInstructions._parse_writer_fields(literal_newline),
            {"instructions": "line one\nline two", "description": "does x"},
        )
        trailing_comma = WriteAllInstructions._parse_writer_fields('{"instructions": "do x",}')
        self.assertEqual(trailing_comma, {"instructions": "do x"})
        single_quotes = WriteAllInstructions._parse_writer_fields("{'description': 'does x'}")
        self.assertEqual(single_quotes, {"description": "does x"})

    def test_empty_object_parses_to_empty_dict_not_none(self):
        """The writer's documented no-op answer stays distinguishable from garbage."""
        self.assertEqual(WriteAllInstructions._parse_writer_fields("{}"), {})


class TestApplyWriterResponse(TestCase):
    """Application of parsed fields to the shared network definition."""

    def setUp(self):
        self.sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: {
                "store_manager": {"instructions": "", "description": "", "tools": ["ddgs_search"]},
                "ddgs_search": {},
            }
        }

    def test_both_fields_are_applied_to_the_named_agent(self):
        """The create-mode answer shape writes both fields, nothing else."""
        error = WriteAllInstructions._apply_writer_response(
            "store_manager", '{"instructions": "run the store", "description": "manages the store"}', self.sly_data
        )
        self.assertEqual(error, "")
        agent = self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]
        self.assertEqual(agent["instructions"], "run the store")
        self.assertEqual(agent["description"], "manages the store")
        # Untouched keys survive the apply.
        self.assertEqual(agent["tools"], ["ddgs_search"])

    def test_an_omitted_field_keeps_its_current_value(self):
        """A single-field answer (scoped change_request) leaves the other field alone."""
        self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]["description"] = "current description"
        error = WriteAllInstructions._apply_writer_response(
            "store_manager", '{"instructions": "only this changed"}', self.sly_data
        )
        self.assertEqual(error, "")
        agent = self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]
        self.assertEqual(agent["instructions"], "only this changed")
        self.assertEqual(agent["description"], "current description")

    def test_unknown_agent_is_an_error(self):
        """A writer answer for an agent absent from the definition is rejected."""
        error = WriteAllInstructions._apply_writer_response("nobody", '{"instructions": "x"}', self.sly_data)
        self.assertEqual(error, "Error: Agent not found: nobody")

    def test_function_agent_is_an_error(self):
        """Agents without an instructions field (function agents) are rejected."""
        error = WriteAllInstructions._apply_writer_response("ddgs_search", '{"instructions": "x"}', self.sly_data)
        self.assertEqual(error, "Error: Agent has no instructions field: ddgs_search. It is a function agent.")

    def test_unparseable_answer_is_an_error_and_applies_nothing(self):
        """A non-JSON answer degrades to a per-agent error, leaving fields untouched."""
        error = WriteAllInstructions._apply_writer_response("store_manager", "not json at all", self.sly_data)
        self.assertTrue(error.startswith("Error: Writer response was not a JSON object"))
        self.assertEqual(self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]["instructions"], "")

    def test_empty_object_is_a_no_op_success(self):
        """The writer's documented no-op ({} = "no change needed") succeeds without writing."""
        self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]["instructions"] = "keep me"
        error = WriteAllInstructions._apply_writer_response("store_manager", "{}", self.sly_data)
        self.assertEqual(error, "")
        self.assertEqual(self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]["instructions"], "keep me")

    def test_invalid_field_values_are_an_error(self):
        """Present-but-unusable values (empty, blank, non-string) fail loudly instead of silently skipping."""
        for bad in ('{"instructions": "", "description": ""}', '{"instructions": 42}', '{"description": "  "}'):
            error = WriteAllInstructions._apply_writer_response("store_manager", bad, self.sly_data)
            self.assertTrue(error.startswith("Error: Writer returned non-text or empty value"), error)

    def test_mixed_valid_and_invalid_values_apply_nothing(self):
        """Validation happens before any write, so a bad field cannot leave the agent half-updated."""
        error = WriteAllInstructions._apply_writer_response(
            "store_manager", '{"instructions": "good text", "description": 42}', self.sly_data
        )
        self.assertTrue(error.startswith("Error: Writer returned non-text or empty value"), error)
        self.assertEqual(self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]["instructions"], "")

    def test_neither_field_in_a_non_empty_object_is_an_error(self):
        """A contract-violating object (keys, but none of ours) must not count as a success."""
        error = WriteAllInstructions._apply_writer_response("store_manager", '{"unexpected": "x"}', self.sly_data)
        self.assertEqual(error, "Error: Writer response contained neither 'instructions' nor 'description'.")

    def test_framework_error_body_is_surfaced_as_the_writer_failure(self):
        """The json error_formatter's {"error", "tool"} body becomes this agent's error, and nothing is applied."""
        response = '```json\n{"error": "something broke", "tool": "instructions_writer"}\n```'
        error = WriteAllInstructions._apply_writer_response("store_manager", response, self.sly_data)
        self.assertEqual(error, "Error: Writer failed: something broke")
        self.assertEqual(self.sly_data[AGENT_NETWORK_DEFINITION]["store_manager"]["instructions"], "")

    def test_missing_network_definition_is_an_error(self):
        """No definition in sly_data means nothing to write into."""
        error = WriteAllInstructions._apply_writer_response("store_manager", '{"instructions": "x"}', {})
        self.assertEqual(error, "Error: No network in sly data!")


class TestDedupAgents(TestCase):
    """Normalization of the agents list before the writer fan-out."""

    def test_duplicate_agent_names_collapse_to_the_last_entry(self):
        """Duplicates would race two writers on one agent; the last change_request wins, in first-seen order."""
        agents = [
            {"agent_name": "a", "change_request": "first"},
            {"agent_name": "b"},
            {"agent_name": "a", "change_request": "second"},
        ]
        self.assertEqual(
            WriteAllInstructions._dedup_agents(agents),
            [{"agent_name": "a", "change_request": "second"}, {"agent_name": "b"}],
        )

    def test_malformed_entries_survive_dedup(self):
        """Malformed entries are kept (uniquely keyed) so each fails per-entry downstream, not vanish here."""
        agents = ["oops", {"agent_name": "a"}, "oops", {"change_request": "no name"}, {}]
        self.assertEqual(WriteAllInstructions._dedup_agents(agents), agents)
