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
Tests for DeployableAgentNetworkAssembler: execution timeout, sly_data_schema emission, metadata block and filled-in
template placeholders.
"""

import asyncio
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import TestCase

import pytest

pytest.importorskip("middleware.agent_network_designer.persistence.deployable_agent_network_assembler")

# The import must stay below importorskip so environments whose neuro-san
# predates the assembler's imports skip cleanly.
# pylint: disable=wrong-import-position
from middleware.agent_network_designer.persistence.agent_network_assembler import (  # noqa: E402
    GENERATED_NETWORK_MAX_EXECUTION_SECONDS,
)
from middleware.agent_network_designer.persistence.deployable_agent_network_assembler import (  # noqa: E402
    DeployableAgentNetworkAssembler,
)

REPO_ROOT: Path = Path(__file__).resolve().parents[4]

OAUTH_URL: str = "https://oauth.example.com/mcp"
FILE_AUTH_URL: str = "https://file-auth.example.com/mcp"

# Client-token servers (from the conversation's sly_data http_headers), each
# mapped to the header names it supplied; FILE_AUTH_URL is a file-configured
# server and deliberately not in it.
CLIENT_TOKEN_MCP_HEADERS: dict[str, list[str]] = {OAUTH_URL: ["Authorization"]}

NETWORK_DEF: dict[str, Any] = {
    "front_man": {"description": "top", "instructions": "Coordinate.", "tools": ["helper", OAUTH_URL]},
    "helper": {"description": "helps", "instructions": "Help.", "tools": [FILE_AUTH_URL]},
}

# One agent of each role. The top and regular agents have no text of their own, which leaves their
# "{agent_instructions}" replacement empty, like "{demo_mode}" with demo mode off.
ROLES_DEF: dict[str, Any] = {
    "front": {"description": "top", "instructions": "", "tools": ["router", "search"]},
    "router": {"description": "routes", "instructions": "", "tools": ["weather"]},
    "weather": {"description": "leaf", "instructions": "Report the weather."},
    "search": {"description": "toolbox"},
}

# A template placeholder such as "{demo_mode}". Only a placeholder has a brace, then lowercase letters and
# underscores, then a closing brace, so this matches nothing else in an agent spec dumped to JSON.
PLACEHOLDER: re.Pattern[str] = re.compile(r"\{[a-z_]+\}")

# The start of the demo sentence the demo template puts in each leaf.
DEMO_MARKER: str = "You are part of a demo system"


class TestDeployableAgentNetworkAssembler(TestCase):
    """
    Tests for DeployableAgentNetworkAssembler.

    The deployable config dict carries the generated-network execution timeout, declares the network's MCP
    header needs in the front man's sly_data_schema, and carries the metadata block it is given, stamping
    nothing itself. No template placeholder is left in it.
    """

    @staticmethod
    def _assemble(client_token_mcp_headers: dict[str, list[str]] | None) -> dict[str, Any]:
        """
        Assemble the test network into a deployable config dict (real templates).

        :param client_token_mcp_headers: Client-token MCP servers mapped to their header names, or None for none
        :return: The assembled deployable config dict
        """
        assembler: DeployableAgentNetworkAssembler = DeployableAgentNetworkAssembler(demo_mode=False)
        cwd: str = os.getcwd()
        # Run from the repo root: the wrapper template's include resolves CWD-relatively, so without the
        # chdir these tests error out under any runner whose working directory is not the repo root
        # (IDE test runners, CI steps with a different workdir).
        os.chdir(REPO_ROOT)
        try:
            return asyncio.run(
                assembler.assemble_agent_network(
                    NETWORK_DEF, "front_man", "test_net", ["query one"], client_token_mcp_headers
                )
            )
        finally:
            os.chdir(cwd)

    def test_deployable_assembler_adds_max_execution_seconds(self) -> None:
        """
        Generated deployable networks include the generated-network execution timeout.
        """
        config: dict[str, Any] = self._assemble(None)

        self.assertEqual(config["max_execution_seconds"], GENERATED_NETWORK_MAX_EXECUTION_SECONDS)

    def test_front_man_declares_the_schema(self) -> None:
        """
        The top agent's function block carries the nsflow contract.
        """
        agent_network: dict[str, Any] = self._assemble(CLIENT_TOKEN_MCP_HEADERS)

        front_man: dict[str, Any] = agent_network["tools"][0]
        self.assertEqual(front_man["name"], "front_man")
        http_headers: dict[str, Any] = front_man["function"]["sly_data_schema"]["properties"]["http_headers"]
        self.assertEqual(list(http_headers["properties"]), [OAUTH_URL])
        self.assertEqual(http_headers["required"], [OAUTH_URL])
        # The description injection it sits next to still happened.
        self.assertEqual(front_man["function"]["description"], "top")

    def test_non_top_agents_carry_no_schema(self) -> None:
        """
        Only the front man talks to clients; helpers must not declare one.
        """
        agent_network: dict[str, Any] = self._assemble(CLIENT_TOKEN_MCP_HEADERS)
        for agent in agent_network["tools"][1:]:
            function: dict[str, Any] | None = agent.get("function")
            if isinstance(function, dict):
                self.assertNotIn("sly_data_schema", function)

    def test_no_client_urls_means_no_schema(self) -> None:
        """
        Without client-token servers the function block stays as templated.
        """
        for client_headers in (None, {}):
            with self.subTest(client_headers=client_headers):
                agent_network: dict[str, Any] = self._assemble(client_headers)
                self.assertNotIn("sly_data_schema", agent_network["tools"][0]["function"])

    # Tests for the metadata block (issue #1398): carried whole with the storage-owned keys stripped,
    # fresh queries overlaid, and omitted when there is nothing to say. The assembler stamps nothing
    # itself: a temporary network gets its own stamps from neuro-san's reservation storage.

    @staticmethod
    def _assemble_spec(sample_queries: list[str], metadata: dict[str, Any] | None) -> dict[str, Any]:
        """
        Assemble the test network from the repo root with the given metadata inputs.

        :param sample_queries: The positional sample_queries argument
        :param metadata: The metadata keyword argument, None for the pre-#1398 call shape
        :return: The assembled deployable spec
        """
        assembler: DeployableAgentNetworkAssembler = DeployableAgentNetworkAssembler(demo_mode=False)
        cwd: str = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            return asyncio.run(
                assembler.assemble_agent_network(
                    NETWORK_DEF, "front_man", "test_net", sample_queries, metadata=metadata
                )
            )
        finally:
            os.chdir(cwd)

    def test_no_metadata_and_no_queries_omits_the_metadata_key(self) -> None:
        """
        With neither queries nor a block to carry, whether the keyword is None or an empty dict, the spec
        has no "metadata" key at all: nothing is stamped to fill it.
        """
        for metadata in (None, {}):
            with self.subTest(metadata=metadata):
                spec: dict[str, Any] = self._assemble_spec([], metadata)

                self.assertNotIn("metadata", spec)

    def test_sample_queries_only_writes_just_sample_queries(self) -> None:
        """
        With queries but no block the metadata holds exactly sample_queries, no timestamp or other key.
        """
        spec: dict[str, Any] = self._assemble_spec(["First?", "Second?"], None)

        self.assertEqual(spec["metadata"], {"sample_queries": ["First?", "Second?"]})

    def test_metadata_keyword_is_carried_whole_with_storage_keys_stripped(self) -> None:
        """
        A block passed in is carried whole minus the keys neuro-san's reservation storage owns and minus
        None-valued keys, a non-empty sample_queries argument replaces only its sample_queries, and the
        caller's dict is neither mutated nor aliased by the spec.
        """
        supplied: dict[str, Any] = {
            "description": "A demo",
            "tags": ["generated"],
            "sample_queries": ["Old one?"],
            "date_created": "2026-01-01T00:00:00+00:00",
            "reservation": {"id": "net-1"},
            "stored_at": 1.0,
            "note": None,
        }
        snapshot: dict[str, Any] = deepcopy(supplied)

        spec: dict[str, Any] = self._assemble_spec(["New one?"], supplied)

        self.assertEqual(
            spec["metadata"],
            {
                "description": "A demo",
                "tags": ["generated"],
                "sample_queries": ["New one?"],
                "date_created": "2026-01-01T00:00:00+00:00",
            },
        )
        self.assertEqual(supplied, snapshot)
        # The spec holds a copy: neuro-san's storage writers add keys to it, which must not reach the caller.
        self.assertIsNot(spec["metadata"], supplied)
        self.assertIsNot(spec["metadata"]["tags"], supplied["tags"])

    def test_timestamps_in_the_block_pass_through_unchanged(self) -> None:
        """
        A block carrying date_created and date_modified comes out identical: the assembler neither refreshes
        date_modified nor adds anything, because timestamps belong to the persistence middleware.
        """
        supplied: dict[str, Any] = {
            "date_created": "2026-01-01T00:00:00+00:00",
            "date_modified": "2026-02-01T00:00:00+00:00",
        }

        spec: dict[str, Any] = self._assemble_spec([], supplied)

        self.assertEqual(spec["metadata"], supplied)

    @staticmethod
    def _assemble_roles(definition: dict[str, Any], demo_mode: bool) -> dict[str, Any]:
        """
        Assemble a definition whose top agent is "front", from the repo root.

        :param definition: The definition to assemble
        :param demo_mode: Whether to use the demo template
        :return: The assembled deployable spec
        """
        assembler: DeployableAgentNetworkAssembler = DeployableAgentNetworkAssembler(demo_mode=demo_mode)
        cwd: str = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            return asyncio.run(assembler.assemble_agent_network(definition, "front", "travel", []))
        finally:
            os.chdir(cwd)

    def test_no_placeholder_is_left_in_any_agent(self) -> None:
        """
        Every template placeholder is filled in or removed, for every role and in both demo modes. neuro-san's
        string filter leaves a placeholder as written when its replacement is empty, which is the case for
        "{demo_mode}" with demo mode off and for "{agent_instructions}" of an agent with no text of its own.
        """
        for demo_mode in (True, False):
            with self.subTest(demo_mode=demo_mode):
                spec: dict[str, Any] = self._assemble_roles(ROLES_DEF, demo_mode)
                for agent in spec.get("tools"):
                    with self.subTest(agent=agent.get("name")):
                        self.assertIsNone(PLACEHOLDER.search(json.dumps(agent)))

    def test_only_a_demo_mode_leaf_gets_the_demo_sentence(self) -> None:
        """
        The leaf carries the demo sentence once with demo mode on and not at all with it off, and keeps its own
        text either way.
        """
        for demo_mode in (True, False):
            with self.subTest(demo_mode=demo_mode):
                spec: dict[str, Any] = self._assemble_roles(ROLES_DEF, demo_mode)
                leaf: str = self._instructions(spec, "weather")
                self.assertEqual(leaf.count(DEMO_MARKER), 1 if demo_mode else 0)
                self.assertTrue(leaf.rstrip().endswith("Report the weather."))

    def test_a_placeholder_in_the_agents_own_text_is_kept_once(self) -> None:
        """
        Only the template's placeholders are removed, never the agent's own text: with demo mode off, a
        "{demo_mode}" in a leaf's own text stays exactly once.
        """
        definition: dict[str, Any] = deepcopy(ROLES_DEF)
        definition.get("weather")["instructions"] = "{demo_mode}\n\nReport the weather."

        spec: dict[str, Any] = self._assemble_roles(definition, False)

        self.assertEqual(self._instructions(spec, "weather").count("{demo_mode}"), 1)

    @staticmethod
    def _instructions(spec: dict[str, Any], agent_name: str) -> str:
        """
        Read one agent's instructions from a deployable spec.

        :param spec: The assembled deployable spec
        :param agent_name: The agent's name
        :return: The agent's instructions, or an empty string when the spec has no such agent
        """
        for agent in spec.get("tools"):
            if agent.get("name") == agent_name:
                return agent.get("instructions", "")
        return ""
