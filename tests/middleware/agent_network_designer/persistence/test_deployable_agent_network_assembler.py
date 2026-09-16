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

"""Tests for DeployableAgentNetworkAssembler's sly_data_schema emission and metadata block."""

import asyncio
import os
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

REPO_ROOT = Path(__file__).resolve().parents[4]

OAUTH_URL = "https://oauth.example.com/mcp"
FILE_AUTH_URL = "https://file-auth.example.com/mcp"

# Client-token servers (from the conversation's sly_data http_headers), each
# mapped to the header names it supplied; FILE_AUTH_URL is a file-configured
# server and deliberately not in it.
CLIENT_TOKEN_MCP_HEADERS: dict[str, list[str]] = {OAUTH_URL: ["Authorization"]}

NETWORK_DEF: dict = {
    "front_man": {"description": "top", "instructions": "Coordinate.", "tools": ["helper", OAUTH_URL]},
    "helper": {"description": "helps", "instructions": "Help.", "tools": [FILE_AUTH_URL]},
}


def assemble(client_token_mcp_headers: dict[str, list[str]] | None) -> dict:
    """
    Assemble the test network into a deployable config dict (real templates).

    Runs from the repo root: the wrapper template's include resolves
    CWD-relatively, so without the chdir these tests error out under any
    runner whose working directory is not the repo root (IDE test runners,
    CI steps with a different workdir).
    """
    assembler = DeployableAgentNetworkAssembler(demo_mode=False)
    cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        return asyncio.run(
            assembler.assemble_agent_network(
                NETWORK_DEF, "front_man", "test_net", ["query one"], client_token_mcp_headers
            )
        )
    finally:
        os.chdir(cwd)


def test_deployable_assembler_adds_max_execution_seconds():
    """Generated deployable networks include the generated-network execution timeout."""
    config = assemble(None)

    assert config["max_execution_seconds"] == GENERATED_NETWORK_MAX_EXECUTION_SECONDS


class TestDeployableAssemblerSlyDataSchema(TestCase):
    """
    The deployable config dict declares the network's MCP header needs and carries the metadata block
    it is given, stamping nothing itself.
    """

    def test_front_man_declares_the_schema(self):
        """The top agent's function block carries the nsflow contract."""
        agent_network = assemble(CLIENT_TOKEN_MCP_HEADERS)

        front_man = agent_network["tools"][0]
        assert front_man["name"] == "front_man"
        http_headers = front_man["function"]["sly_data_schema"]["properties"]["http_headers"]
        assert list(http_headers["properties"]) == [OAUTH_URL]
        assert http_headers["required"] == [OAUTH_URL]
        # The description injection it sits next to still happened.
        assert front_man["function"]["description"] == "top"

    def test_non_top_agents_carry_no_schema(self):
        """Only the front man talks to clients; helpers must not declare one."""
        agent_network = assemble(CLIENT_TOKEN_MCP_HEADERS)
        for agent in agent_network["tools"][1:]:
            function = agent.get("function")
            if isinstance(function, dict):
                assert "sly_data_schema" not in function

    def test_no_client_urls_means_no_schema(self):
        """Without client-token servers the function block stays as templated."""
        for client_headers in (None, {}):
            agent_network = assemble(client_headers)
            assert "sly_data_schema" not in agent_network["tools"][0]["function"]

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
