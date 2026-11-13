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

"""Characterization tests for Agent Network Consultant's surgical HOCON edits."""

import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from pyhocon import ConfigFactory
from pyhocon.exceptions import ConfigException

from middleware.agent_network_consultant.source_preserving_hocon_editor import SourcePreservingHoconEditor


class TestSourcePreservingHoconEditor(TestCase):
    """Prove instruction edits preserve the target network's AAOSA behavior."""

    NON_AAOSA = """{
        "tools": [
            {
                "name": "announcer",
                "function": {"description": "Says hello"},
                "instructions": "Say hello."
            }
        ]
    }
    """
    CHANGE = {"announcer": {"instructions": "Greet the user warmly."}}

    def test_non_aaosa_network_still_resolves(self) -> None:
        """
        Change only the requested value without injecting substitutions or root settings.
        """
        updated = SourcePreservingHoconEditor.update_text(self.NON_AAOSA, self.CHANGE)

        expected = self.NON_AAOSA.replace('"Say hello."', '"Greet the user warmly."')
        self.assertEqual(expected, updated)
        self.assertNotIn("${aaosa_instructions}", updated)
        self.assertNotIn("max_steps", updated)
        self.assertNotIn("max_execution_seconds", updated)
        ConfigFactory.parse_string(updated, resolve=True)

    def test_aaosa_network_keeps_one_substitution(self) -> None:
        """
        Preserve existing instruction substitutions without adding them to descriptions.
        """
        includes: tuple[str, str] = ('include "registries/aaosa.hocon"', 'include "aaosa_basic.hocon"')
        for include in includes:
            with self.subTest(include=include):
                source = self.NON_AAOSA.replace("{\n", "{\n        " + include + "\n", 1)
                source = source.replace('"Say hello."', '${aaosa_instructions} "Say hello."')
                original_fields: dict[str, dict[str, str]] = {
                    "announcer": {"instructions": "Common instructions. Say hello."}
                }
                changes: dict[str, dict[str, str]] = {
                    "announcer": {"instructions": "Common instructions. Greet the user warmly."}
                }

                updated = SourcePreservingHoconEditor.update_text(source, changes, original_fields)

                self.assertEqual(updated.count("${aaosa_instructions}"), 1)
                self.assertIn('"Greet the user warmly."', updated)
        source = self.NON_AAOSA.replace("{\n", '{\n        include "registries/aaosa.hocon",\n', 1)

        updated = SourcePreservingHoconEditor.update_text(
            source, {"announcer": {"description": "Offers a warm greeting."}}
        )

        self.assertIn("Offers a warm greeting.", updated)
        self.assertEqual(updated.count("${aaosa_instructions}"), 0)

    def test_implicit_root_and_function_shorthand_are_editable(self) -> None:
        """Edit both supported fields in the brace-free HOCON shape used by Studio networks."""
        source: str = """metadata.owner.name = "Studio"
tools = [
    {
        name = announcer
        function { description = "Says hello" }
        instructions = "Say hello."
    }
]
"""
        changes: dict[str, dict[str, str]] = {
            "announcer": {
                "description": "Offers a warm greeting.",
                "instructions": "Greet the user warmly.",
            }
        }

        updated = SourcePreservingHoconEditor.update_text(source, changes)

        self.assertIn('metadata.owner.name = "Studio"', updated)
        self.assertIn('function { description = "Offers a warm greeting." }', updated)
        self.assertIn('instructions = "Greet the user warmly."', updated)
        ConfigFactory.parse_string(updated, resolve=True)

    def test_root_tools_assignment_and_append_semantics(self) -> None:
        """Edit additive fragments while ignoring agents removed by a later root assignment."""
        source: str = """tools = [
    {name = announcer, function = {description = "Says hello"}, instructions = "Say hello."}
]
tools += [
    {name = helper, function = {description = "Helps"}, instructions = "Provide help."}
]
"""

        updated = SourcePreservingHoconEditor.update_text(
            source,
            {"helper": {"instructions": "Provide careful help."}},
        )

        self.assertIn('instructions = "Say hello."', updated)
        self.assertIn('instructions = "Provide careful help."', updated)
        ConfigFactory.parse_string(updated, resolve=True)

        replacement_source: str = source.replace("tools +=", "tools =")
        replacement_updated: str = SourcePreservingHoconEditor.update_text(
            replacement_source,
            {"helper": {"instructions": "Provide careful help."}},
        )
        replacement_config: Any = ConfigFactory.parse_string(replacement_updated, resolve=True)
        replacement_tools: list[dict[str, object]] = replacement_config.get("tools", [])
        self.assertEqual("helper", replacement_tools[0].get("name"))
        self.assertEqual("Provide careful help.", replacement_tools[0].get("instructions"))
        with self.assertRaisesRegex(ValueError, "Could not locate agent 'announcer'"):
            SourcePreservingHoconEditor.update_text(replacement_source, self.CHANGE)

    def test_include_inside_tools_does_not_hide_a_local_agent(self) -> None:
        """Ignore an included array fragment while editing a directly declared agent."""
        source: str = """tools = [
    include "shared_agent.hocon"
    {name = announcer, function = {description = "Says hello"}, instructions = "Say hello."}
]
"""

        updated = SourcePreservingHoconEditor.update_text(source, self.CHANGE)

        self.assertIn('include "shared_agent.hocon"', updated)
        self.assertIn('instructions = "Greet the user warmly."', updated)

    def test_include_only_agent_reports_that_it_cannot_be_edited(self) -> None:
        """Reject an agent supplied only by an include because its source is not local."""
        source: str = 'include "shared_network.hocon"\n'

        with self.assertRaisesRegex(ValueError, "supplied only through an include"):
            SourcePreservingHoconEditor.update_text(source, self.CHANGE)

    def test_dotted_root_key_and_unrelated_text_are_preserved_exactly(self) -> None:
        """Leave dotted keys, comments, and spacing untouched around one literal replacement."""
        source: str = """
"tools.archive" = [{ name = announcer, instructions = "Archived." }]
metadata.owner.name = "Studio" # Keep this comment.
tools = [{ name = announcer, function = { description = "Says hello" }, instructions = "Say hello." }]
"""

        updated = SourcePreservingHoconEditor.update_text(source, self.CHANGE)

        expected: str = source.replace('"Say hello."', '"Greet the user warmly."')
        self.assertEqual(expected, updated)

    def test_arbitrary_substitution_keeps_only_its_changed_literal(self) -> None:
        """Retain a source substitution without duplicating its resolved prefix in the replacement."""
        source: str = """shared = "Shared"
tools = [{
    name = announcer
    function = {description = "Says hello"}
    instructions = ${shared} "Custom."
}]
"""
        original_fields: dict[str, dict[str, str]] = {"announcer": {"instructions": "Shared Custom."}}
        changes: dict[str, dict[str, str]] = {"announcer": {"instructions": "Shared Updated."}}

        updated = SourcePreservingHoconEditor.update_text(source, changes, original_fields)

        self.assertIn('instructions = ${shared} "Updated."', updated)
        self.assertNotIn("Shared Shared", updated)
        parsed = ConfigFactory.parse_string(updated, resolve=True)
        tools: list[dict[str, object]] = parsed.get("tools", [])
        self.assertEqual("Shared Updated.", tools[0].get("instructions"))

    def test_substitution_derived_text_cannot_be_rewritten_as_a_literal(self) -> None:
        """Reject a request that would require changing text owned by a substitution."""
        source: str = """shared = "Shared"
tools = [{name = announcer, instructions = ${shared} "Custom."}]
"""
        original_fields: dict[str, dict[str, str]] = {"announcer": {"instructions": "Shared Custom."}}
        changes: dict[str, dict[str, str]] = {"announcer": {"instructions": "Different Updated."}}

        with self.assertRaisesRegex(ValueError, "Cannot change substitution-derived text"):
            SourcePreservingHoconEditor.update_text(source, changes, original_fields)

    def test_ambiguous_composed_values_are_rejected(self) -> None:
        """Fail closed when source-literal and substitution boundaries cannot be isolated safely."""
        cases: list[tuple[str, str, str, str]] = [
            (
                'shared = "Prefix  "\ntools = [{name = announcer, instructions = ${shared} """Source\ntext"""}]\n',
                "Prefix  Source text",
                "Prefix  Updated text",
                "Could not isolate the source literal",
            ),
            (
                'prefix = "a"\ntools = [{name = announcer, instructions = ${prefix} "aaa"}]\n',
                "aaaa",
                "baaa",
                "Could not isolate the source literal",
            ),
            (
                'prefix = "ab"\nsuffix = "bc"\ntools = [{name = announcer, instructions = ${prefix} "X" ${suffix}}]\n',
                "abXbc",
                "abc",
                "Cannot change substitution-derived text",
            ),
        ]
        for source, original, changed, error_message in cases:
            original_fields: dict[str, dict[str, str]] = {"announcer": {"instructions": original}}
            changes: dict[str, dict[str, str]] = {"announcer": {"instructions": changed}}
            with self.subTest(error_message=error_message), self.assertRaisesRegex(ValueError, error_message):
                SourcePreservingHoconEditor.update_text(source, changes, original_fields)

    def test_real_studio_network_preserves_composed_instruction_syntax(self) -> None:
        """Edit a normalized literal in a real implicit-root Studio network without expanding its substitutions."""
        source_path = Path("registries/basic/coffee_finder_advanced.hocon")
        source = source_path.read_text(encoding="utf-8")
        # Studio includes are repository-root-relative, so parse the loaded text from the repository root.
        config: Any = ConfigFactory.parse_string(source, resolve=True)
        original_instructions = ""
        for agent in config.get("tools", []):
            if agent.get("name") == "CoffeeFinder":
                raw_instructions: Any = agent.get("instructions", "")
                original_instructions = " ".join(raw_instructions.split())
                break
        changed_instructions = original_instructions.replace(
            "You are the agent responsible for answering user inquiries about coffee places and taking orders.",
            "You are the agent responsible for answering coffee inquiries and taking orders carefully.",
        )
        original_fields: dict[str, dict[str, str]] = {"CoffeeFinder": {"instructions": original_instructions}}
        changes: dict[str, dict[str, str]] = {"CoffeeFinder": {"instructions": changed_instructions}}

        updated = SourcePreservingHoconEditor.update_text(source, changes, original_fields)

        self.assertNotEqual(original_instructions, changed_instructions)
        self.assertEqual(
            source.count("${expertise_scoping_instructions}"), updated.count("${expertise_scoping_instructions}")
        )
        self.assertEqual(source.count("${this_is_not_a_game}"), updated.count("${this_is_not_a_game}"))
        self.assertEqual(source.count("${aaosa_instructions}"), updated.count("${aaosa_instructions}"))
        updated_config: Any = ConfigFactory.parse_string(updated, resolve=True)
        resolved_updated_instructions = ""
        for agent in updated_config.get("tools", []):
            if agent.get("name") == "CoffeeFinder":
                updated_instructions: Any = agent.get("instructions", "")
                resolved_updated_instructions = " ".join(updated_instructions.split())
                break
        self.assertEqual(changed_instructions, resolved_updated_instructions)

    def test_multiline_instruction_round_trips_exactly(self) -> None:
        """Preserve leading, trailing, and internal whitespace in a multiline replacement."""
        expected: str = "\n  First line.\nSecond line.  \n"

        updated: str = SourcePreservingHoconEditor.update_text(
            self.NON_AAOSA,
            {"announcer": {"instructions": expected}},
        )

        parsed = ConfigFactory.parse_string(updated, resolve=False)
        tools: list[dict[str, object]] = parsed.get("tools", [])
        self.assertEqual(expected, tools[0].get("instructions"))

    def test_triple_quoted_value_ending_in_a_quote_is_scanned_correctly(self) -> None:
        """Read a valid four-quote terminator before editing another field in the same agent."""
        source: str = self.NON_AAOSA.replace('"Say hello."', '"""Say "hello""""')

        updated = SourcePreservingHoconEditor.update_text(
            source,
            {"announcer": {"description": "Offers a warm greeting."}},
        )

        self.assertIn('"""Say "hello""""', updated)
        self.assertIn('"description": "Offers a warm greeting."', updated)
        ConfigFactory.parse_string(updated, resolve=False)

    def test_update_file_preserves_permissions_comments_and_optional_substitutions(self) -> None:
        """Publish an atomic edit without changing permissions or unrelated source syntax."""
        source: str = self.NON_AAOSA.replace(
            '"instructions": "Say hello."',
            '"instructions": ${?OPTIONAL_PREFIX} "Say hello." # Retain this comment',
        )
        with TemporaryDirectory() as temporary_directory:
            path: Path = Path(temporary_directory) / "network.hocon"
            path.write_text(source, encoding="utf-8")
            path.chmod(0o640)

            updated: str = SourcePreservingHoconEditor.update_file(str(path), self.CHANGE)

            self.assertEqual(updated, path.read_text(encoding="utf-8"))
            self.assertEqual(0o640, stat.S_IMODE(path.stat().st_mode))
            self.assertIn("${?OPTIONAL_PREFIX}", updated)
            self.assertIn("# Retain this comment", updated)

            crlf_path: Path = Path(temporary_directory) / "crlf_network.hocon"
            crlf_source: str = self.NON_AAOSA.replace("\n", "\r\n")
            with crlf_path.open("w", encoding="utf-8", newline="") as crlf_file:
                crlf_file.write(crlf_source)

            SourcePreservingHoconEditor.update_file(str(crlf_path), self.CHANGE)

            expected_crlf: str = crlf_source.replace('"Say hello."', '"Greet the user warmly."')
            self.assertEqual(expected_crlf.encode(), crlf_path.read_bytes())

    def test_failed_validation_leaves_the_original_file_untouched(self) -> None:
        """Keep the original source and remove the staged file when HOCON validation fails."""
        with TemporaryDirectory() as temporary_directory:
            path: Path = Path(temporary_directory) / "network.hocon"
            path.write_text(self.NON_AAOSA, encoding="utf-8")
            with (
                patch.object(ConfigFactory, "parse_file", side_effect=ConfigException("invalid staged HOCON")),
                self.assertRaisesRegex(ConfigException, "invalid staged HOCON"),
            ):
                SourcePreservingHoconEditor.update_file(str(path), self.CHANGE)

            self.assertEqual(self.NON_AAOSA, path.read_text(encoding="utf-8"))
            self.assertEqual([path], list(path.parent.iterdir()))

    def test_update_text_rejects_missing_and_ambiguous_targets(self) -> None:
        """Report absent, nested, or duplicated edit targets instead of changing an ineffective value."""
        with self.assertRaisesRegex(ValueError, "Could not locate agent 'missing'"):
            SourcePreservingHoconEditor.update_text(
                self.NON_AAOSA,
                {"missing": {"instructions": "Replacement."}},
            )

        nested_tools: str = """metadata = {
    tools = [{name = announcer, instructions = "Nested."}]
}
"""
        with self.assertRaisesRegex(ValueError, "directly declared root tools array"):
            SourcePreservingHoconEditor.update_text(nested_tools, self.CHANGE)

        duplicate: str = self.NON_AAOSA.replace(
            "\n        ]",
            ',\n            {name: announcer, instructions: "Duplicate."}\n        ]',
        )
        with self.assertRaisesRegex(ValueError, "duplicated"):
            SourcePreservingHoconEditor.update_text(duplicate, self.CHANGE)

        duplicate_instructions: str = self.NON_AAOSA.replace(
            '"instructions": "Say hello."',
            '"instructions": "First.", "instructions": "Second."',
        )
        with self.assertRaisesRegex(ValueError, "property 'instructions' is duplicated"):
            SourcePreservingHoconEditor.update_text(duplicate_instructions, self.CHANGE)

        substitution_only: str = """desc = "Resolved description."
tools = [{
    name = announcer
    function = {
        "description" = ${desc}
        "parameters" = {}
    }
    instructions = "Say hello."
}]
"""
        with self.assertRaisesRegex(ValueError, "Could not locate 'description' string"):
            SourcePreservingHoconEditor.update_text(
                substitution_only,
                {"announcer": {"description": "Changed."}},
                {"announcer": {"description": "Resolved description."}},
            )

    def test_update_text_rejects_unsupported_fields(self) -> None:
        """Reject structural edits outside the two explicitly supported fields."""
        with self.assertRaisesRegex(ValueError, "Unsupported agent field"):
            SourcePreservingHoconEditor.update_text(
                self.NON_AAOSA,
                {"announcer": {"tools": "clock"}},
            )

    def test_update_text_reports_unterminated_source_tokens(self) -> None:
        """Report malformed strings and substitutions rather than attempting partial rewrites."""
        malformed_sources: tuple[tuple[str, str], tuple[str, str]] = (
            (self.NON_AAOSA.replace('"Say hello."', '"Say hello.'), "Unterminated quoted HOCON string"),
            (self.NON_AAOSA + "dangling = ${UNFINISHED", "Unterminated HOCON substitution"),
        )
        for malformed, message in malformed_sources:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                SourcePreservingHoconEditor.update_text(malformed, self.CHANGE)

    def test_update_text_preserves_escaped_strings_and_comments(self) -> None:
        """Ignore HOCON-looking text inside strings and comments while finding the edit target."""
        source: str = self.NON_AAOSA.replace(
            '"function": {"description": "Says hello"}',
            '"function": {"description": "Says \\"hello\\""} # tools = [{name = fake}]',
        )

        updated: str = SourcePreservingHoconEditor.update_text(source, self.CHANGE)

        self.assertIn('"description": "Says \\"hello\\""', updated)
        self.assertIn("# tools = [{name = fake}]", updated)
        self.assertIn('"instructions": "Greet the user warmly."', updated)

    def test_concurrent_file_updates_are_serialized_for_the_same_path(self) -> None:
        """Keep both edits when two threads update different agents in one source file."""
        second_agent: str = (
            ",\n            {\n"
            '                "name": "helper",\n'
            '                "function": {"description": "Helps users"},\n'
            '                "instructions": "Provide help."\n'
            "            }"
        )
        source: str = self.NON_AAOSA.replace("\n        ]", second_agent + "\n        ]")
        with TemporaryDirectory() as temporary_directory:
            path: Path = Path(temporary_directory) / "network.hocon"
            path.write_text(source, encoding="utf-8")
            first = Thread(
                target=SourcePreservingHoconEditor.update_file,
                args=(str(path), {"announcer": {"instructions": "Updated greeting."}}),
            )
            second = Thread(
                target=SourcePreservingHoconEditor.update_file,
                args=(str(path), {"helper": {"instructions": "Updated help."}}),
            )
            first.start()
            second.start()
            first.join()
            second.join()

            parsed = ConfigFactory.parse_file(path, resolve=False)
            tools: list[dict[str, object]] = parsed.get("tools", [])
            self.assertEqual("Updated greeting.", tools[0].get("instructions"))
            self.assertEqual("Updated help.", tools[1].get("instructions"))
