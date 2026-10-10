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

"""Tests for the Agent Network Consultant registry contract."""

import re
from pathlib import Path
from unittest import TestCase

from pyhocon import ConfigFactory
from pyhocon import ConfigTree


class TestAgentNetworkConsultantRegistry(TestCase):
    """Verify the Consultant network exposes its required agents and diagnostic tools."""

    LLM_AGENT_NAMES = (
        "consultant",
        "network_behavior_fixer",
        "fixture_expectation_fixer",
        "structural_change_assessor",
        "instructions_writer",
    )
    PII_MIDDLEWARE_CLASS = "langchain.agents.middleware.PIIMiddleware"
    REGISTRY_PATH = Path("registries/agent_network_consultant.hocon")

    @staticmethod
    def _configuration() -> ConfigTree:
        """
        Parse and resolve the Consultant registry.

        :return: The resolved Consultant configuration.
        """
        content = TestAgentNetworkConsultantRegistry.REGISTRY_PATH.read_text(encoding="utf-8")
        return ConfigFactory.parse_string(content, basedir=".", resolve=True)

    @staticmethod
    def _tool(configuration: ConfigTree, name: str) -> ConfigTree:
        """
        Return one named tool from the resolved Consultant registry.

        :param configuration: The resolved Consultant configuration.
        :param name: The exact tool name to find.
        :return: The matching tool configuration.
        :raises AssertionError: If the registry does not define the named tool.
        """
        for tool in configuration.get("tools", []):
            if tool.get("name", "") == name:
                return tool
        raise AssertionError(f"Consultant registry does not define tool {name!r}.")

    def test_registry_declares_ungrounded_handling_and_the_fixer_exception(self) -> None:
        """Keep the registry contract required by runner-side ungrounded reporting."""
        configuration = self._configuration()
        consultant = self._tool(configuration, "consultant")
        fixture_fixer = self._tool(configuration, "fixture_expectation_fixer")

        self.assertIn("UNGROUNDED:", consultant.get("instructions", ""))
        self.assertIn("read_thinking_trace", consultant.get("tools", []))
        self.assertIn("2b. EXCEPTION", fixture_fixer.get("instructions", ""))

    def test_metadata_uses_stable_tags_and_a_shipped_sample(self) -> None:
        """Keep Consultant nonexperimental and its sample grounded in files distributed with Studio."""
        configuration = self._configuration()
        metadata: ConfigTree = configuration.get("metadata")
        sample_queries: list[str] = list(metadata.get("sample_queries", []))
        fixture_directory = Path("tests/fixtures/basic/coffee_finder_advanced")
        fixture_files: list[Path] = list(fixture_directory.glob("*.hocon"))

        self.assertEqual(
            ["Fix basic/coffee_finder_advanced based on its failing tests"],
            sample_queries,
        )
        self.assertEqual(["tool"], list(metadata.get("tags", [])))
        self.assertTrue(Path("registries/basic/coffee_finder_advanced.hocon").is_file())
        self.assertTrue(fixture_files)

    def test_front_man_exposes_every_named_diagnostic_tool(self) -> None:
        """Expose both readers and preserve diagnostic control lines without substring rewriting."""
        consultant = self._tool(self._configuration(), "consultant")
        instructions: str = consultant.get("instructions", "")

        self.assertEqual([], consultant.get("error_fragments"))
        self.assertIn("read_thinking_trace", consultant.get("tools", []))
        self.assertIn("read_job_log", consultant.get("tools", []))
        self.assertIn("no nsflow job is", instructions)
        self.assertIn("missing job log is not itself a TOOL ISSUE", instructions)

    def test_every_consultant_llm_agent_redacts_sensitive_message_content(self) -> None:
        """Protect each LLM's input, output, and tool-result message boundaries with one shared policy."""
        configuration = self._configuration()
        shared_arguments: ConfigTree | None = None
        for agent_name in self.LLM_AGENT_NAMES:
            with self.subTest(agent_name=agent_name):
                agent = self._tool(configuration, agent_name)
                middleware_chain: list[ConfigTree] = list(agent.get("middleware", []))
                pii_middleware: list[ConfigTree] = []
                for middleware in middleware_chain:
                    if middleware.get("class") == self.PII_MIDDLEWARE_CLASS:
                        pii_middleware.append(middleware)

                self.assertEqual(1, len(pii_middleware))
                self.assertEqual(self.PII_MIDDLEWARE_CLASS, middleware_chain[-1].get("class"))
                arguments: ConfigTree = pii_middleware[0].get("args")
                if shared_arguments is None:
                    shared_arguments = arguments
                else:
                    self.assertEqual(shared_arguments, arguments)
                self.assertEqual("redact", arguments.get("strategy"))
                self.assertIs(True, arguments.get("apply_to_input"))
                self.assertIs(True, arguments.get("apply_to_output"))
                self.assertIs(True, arguments.get("apply_to_tool_results"))
                detector: str = arguments.get("detector", "")
                pattern: re.Pattern[str] = re.compile(detector)
                self.assertIsNotNone(pattern.search("sk-proj-example-secret"))
                self.assertIsNotNone(pattern.search("Bearer ABCDEFGHIJKLMNOPQRST"))
                # Existing source substitutions must remain editable instead of becoming redaction markers.
                self.assertIsNone(pattern.search("${OPENAI_API_KEY}"))
                self.assertIsNone(pattern.search("max_tokens=2048"))

    def test_registry_resolves_consultant_instruction_writer_nodes(self) -> None:
        """Reuse the existing fan-out code with the Consultant-specific writing contract."""
        configuration = self._configuration()
        write_all_instructions = self._tool(configuration, "write_all_instructions")
        instructions_writer = self._tool(configuration, "instructions_writer")

        self.assertEqual(
            "coded_tools.agent_network_instructions_editor.write_all_instructions.WriteAllInstructions",
            write_all_instructions.get("class", ""),
        )
        instructions: str = instructions_writer.get("instructions", "")
        self.assertIn("Goal:", instructions)
        self.assertIn("ALWAYS edit incrementally", instructions)
        middleware: list[ConfigTree] = list(instructions_writer.get("middleware", []))
        self.assertIn("ConsultantDefinitionMiddleware", middleware[0].get("class", ""))
        content = self.REGISTRY_PATH.read_text(encoding="utf-8")
        self.assertNotIn("agent_network_instruction_improver.hocon", content)
