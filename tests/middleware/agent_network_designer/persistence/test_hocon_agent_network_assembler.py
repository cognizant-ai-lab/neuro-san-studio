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
Tests for HoconAgentNetworkAssembler: sly_data_schema emission, the generated-network execution timeout and
metadata block rendering.
"""

import asyncio
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import TestCase

from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer
from pyhocon import ConfigFactory

from middleware.agent_network_designer.persistence.agent_network_assembler import (
    GENERATED_NETWORK_MAX_EXECUTION_SECONDS,
)
from middleware.agent_network_designer.persistence.agent_network_metadata_block import AgentNetworkMetadataBlock
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler

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


class TestHoconAgentNetworkAssembler(TestCase):
    """
    Tests for HoconAgentNetworkAssembler, which renders a designed network as HOCON text.

    The generated text declares the network's MCP header needs in the front man's sly_data_schema, carries the
    generated-network execution timeout and renders the metadata block it is given. Until #1422 moves timestamps
    into the persistence middleware, the header still stamps date_created on a block that has none, and nothing
    else.
    """

    @staticmethod
    def _assemble(client_token_mcp_headers: dict[str, list[str]] | None) -> str:
        """
        Assemble the test network into HOCON text.

        :param client_token_mcp_headers: The client-token MCP servers mapped to the header names they supplied,
                                         or None for the call shape without any
        :return: The emitted HOCON text
        """
        assembler: HoconAgentNetworkAssembler = HoconAgentNetworkAssembler(demo_mode=False)
        return asyncio.run(
            assembler.assemble_agent_network(
                NETWORK_DEF, "front_man", "test_net", ["query one"], client_token_mcp_headers
            )
        )

    @staticmethod
    def _parse(hocon_text: str) -> dict[str, Any]:
        """
        Parse assembled HOCON from the repo root so its includes resolve.

        :param hocon_text: The emitted HOCON text
        :return: The parsed configuration, as pyhocon read it back
        """
        cwd: str = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            return ConfigFactory.parse_string(hocon_text)
        finally:
            os.chdir(cwd)

    @staticmethod
    def _unquote(key: str) -> str:
        """
        Strip the quotes pyhocon keeps embedded in quoted keys that contain dots
        (URL keys come back as '"https://..."'). Clients normalize the same way —
        see nsflow's _clean_schema_url — and the neuro-san restorer shows the
        identical artifact for the hand-written you_search.hocon.

        :param key: The key as pyhocon returned it
        :return: The key with its embedded quotes stripped
        """
        return key.strip('"')

    def test_hocon_assembler_adds_max_execution_seconds(self) -> None:
        """
        Generated HOCON networks include the generated-network execution timeout.
        """
        content: str = self._assemble(None)

        self.assertIn(f'"max_execution_seconds": {GENERATED_NETWORK_MAX_EXECUTION_SECONDS}', content)

    def test_front_man_declares_the_schema_and_it_parses(self) -> None:
        """
        The emitted text stays valid HOCON and carries the nsflow contract.
        """
        config: dict[str, Any] = self._parse(self._assemble(CLIENT_TOKEN_MCP_HEADERS))

        front_man: dict[str, Any] = config["tools"][0]
        self.assertEqual(front_man["name"], "front_man")
        http_headers: dict[str, Any] = front_man["function"]["sly_data_schema"]["properties"]["http_headers"]
        # Only the client-token URL is declared, and it is required.
        url_properties: dict[str, Any] = {}
        for url, value in http_headers["properties"].items():
            url_properties[self._unquote(url)] = value
        self.assertEqual(list(url_properties), [OAUTH_URL])
        self.assertEqual(list(http_headers["required"]), [OAUTH_URL])
        self.assertEqual(list(url_properties[OAUTH_URL]["required"]), ["Authorization"])
        # The description substitution still landed alongside the schema.
        self.assertIn("top", front_man["function"]["description"])

    def test_non_top_agents_carry_no_schema(self) -> None:
        """
        Only the front man talks to clients; helpers must not declare one.
        """
        config: dict[str, Any] = self._parse(self._assemble(CLIENT_TOKEN_MCP_HEADERS))
        for agent in config["tools"][1:]:
            self.assertNotIn("sly_data_schema", agent.get("function", {}))

    def test_no_mcp_means_no_schema_and_unchanged_output(self) -> None:
        """
        Without MCP the text is byte-identical to the pre-schema behavior.
        """
        without_client_urls: str = self._assemble(None)
        with_no_client_urls: str = self._assemble({})

        self.assertNotIn("sly_data_schema", without_client_urls)
        # The two renders differ only in the date_created stamp.
        strip_date: re.Pattern[str] = re.compile(r'"date_created": "[^"]*"')
        self.assertEqual(strip_date.sub("", without_client_urls), strip_date.sub("", with_no_client_urls))

        config: dict[str, Any] = self._parse(without_client_urls)
        self.assertNotIn("sly_data_schema", config["tools"][0]["function"])

    def test_a_non_ascii_url_key_round_trips_verbatim(self) -> None:
        """
        ensure_ascii=False keeps a non-ASCII URL key matching the tools list;
        an escaped key would read back as literal text pyhocon never decodes.
        """
        # The non-ASCII character must live in the path, not the host: CI
        # link-checks string literals (lychee) and skips example.com hosts,
        # but a non-ASCII host punycodes to a real, checkable domain.
        unicode_url: str = "https://example.com/mçp"
        network_def: dict[str, Any] = {
            "front_man": {"description": "top", "instructions": "Go.", "tools": [unicode_url]}
        }
        assembler: HoconAgentNetworkAssembler = HoconAgentNetworkAssembler(demo_mode=False)
        text: str = asyncio.run(
            assembler.assemble_agent_network(
                network_def, "front_man", "test_net", ["q"], {unicode_url: ["Authorization"]}
            )
        )

        # The raw character survives in the emitted text, not a \uXXXX escape...
        self.assertIn(unicode_url, text)
        self.assertNotIn("m\\u00e7p", text)

        # ...and parses back to the same key the tools list uses.
        front_man: dict[str, Any] = self._parse(text)["tools"][0]
        http_headers: dict[str, Any] = front_man["function"]["sly_data_schema"]["properties"]["http_headers"]
        unquoted_urls: list[str] = []
        for url in http_headers["properties"]:
            unquoted_urls.append(self._unquote(url))
        self.assertEqual(unquoted_urls, [unicode_url])
        self.assertEqual(list(http_headers["required"]), [unicode_url])

    # Tests for the metadata block (issue #1398). The block is rendered as one JSON object so that any
    # key carries forward: AgentNetworkMetadataBlock builds it from the metadata keyword and the
    # sample_queries argument, and the header adds only a date_created stamp when the block has none.

    # Strings that broke the former triple-quoted rendering or that HOCON could misread: an embedded
    # quote, a newline, three double quotes, substitution syntax, non-ASCII text, a tab and the
    # U+2028 LINE SEPARATOR (written as an escape so it is visible).
    HOSTILE_STRINGS: list[str] = [
        'He said "hi"',
        "line one\nline two",
        'three """ quotes',
        "Price ${PRICE} is $5 ${?OPT}",
        "caf\u00e9 \U0001f600",
        "tab\there",
        "sep\u2028arated",
    ]

    @staticmethod
    def _assemble_text(sample_queries: list[str], metadata: dict[str, Any] | None) -> str:
        """
        Assemble the test network into HOCON text with the given metadata inputs.

        :param sample_queries: The positional sample_queries argument
        :param metadata: The metadata keyword argument, None for the pre-#1398 call shape
        :return: The emitted HOCON text
        """
        assembler: HoconAgentNetworkAssembler = HoconAgentNetworkAssembler(demo_mode=False)
        return asyncio.run(
            assembler.assemble_agent_network(NETWORK_DEF, "front_man", "test_net", sample_queries, metadata=metadata)
        )

    @staticmethod
    def _parse_metadata(hocon_text: str) -> dict[str, Any]:
        """
        Parse emitted HOCON text from the repo root and return its metadata block as plain containers.

        pyhocon reads objects back as ConfigTree instances; converting them to plain dicts keeps the
        assertions literal and their failure output legible.

        :param hocon_text: The emitted HOCON text
        :return: The "metadata" block as pyhocon read it back, as plain dicts and lists
        """
        return TestHoconAgentNetworkAssembler._parse(hocon_text)["metadata"].as_plain_ordered_dict()

    @staticmethod
    def _assemble_metadata(sample_queries: list[str], metadata: dict[str, Any] | None) -> dict[str, Any]:
        """
        Assemble the test network and return the parsed metadata block of the emitted HOCON.

        :param sample_queries: The positional sample_queries argument
        :param metadata: The metadata keyword argument, None for the pre-#1398 call shape
        :return: The "metadata" block as pyhocon read it back, as plain dicts and lists
        """
        text: str = TestHoconAgentNetworkAssembler._assemble_text(sample_queries, metadata)
        return TestHoconAgentNetworkAssembler._parse_metadata(text)

    def test_metadata_keyword_is_written_whole_and_fresh_queries_overlay_only_sample_queries(self) -> None:
        """
        A metadata block passed in is written whole, in its own key order, and a non-empty sample_queries
        argument replaces only the block's sample_queries: every other key, including a nested object and
        the client's date_created, comes back exactly as sent.
        """
        supplied: dict[str, Any] = {
            "description": "A demo",
            "tags": ["generated"],
            "owner": {"team": "platform", "level": 2},
            "sample_queries": ["Old one?"],
            "date_created": "2026-01-01T00:00:00+00:00",
        }
        expected: dict[str, Any] = deepcopy(supplied)
        expected["sample_queries"] = ["New one?"]

        block: dict[str, Any] = self._assemble_metadata(["New one?"], supplied)

        self.assertEqual(block, expected)
        # Key order is preserved so a hand-edited file keeps its shape after a save.
        self.assertEqual(list(block.keys()), list(supplied.keys()))

    def test_no_metadata_and_no_queries_renders_only_date_created(self) -> None:
        """
        The pre-#1398 call shape with neither queries nor a block renders a block holding only the
        date_created stamp, as the header always did; no empty sample_queries list is written any more.
        """
        text: str = self._assemble_text([], None)
        block: dict[str, Any] = self._parse_metadata(text)

        self.assertEqual(list(block.keys()), ["date_created"])
        self.assertNotIn('"sample_queries"', text)
        # The stamp keeps the format the header always used: UTC ISO-8601 with an explicit offset.
        self.assertTrue(block["date_created"].endswith("+00:00"))

    def test_sample_queries_only_renders_sample_queries_and_date_created(self) -> None:
        """
        With queries but no block the parsed block holds exactly sample_queries and the date_created stamp.
        """
        block: dict[str, Any] = self._assemble_metadata(["First?", "Second?"], None)

        self.assertEqual(list(block.keys()), ["sample_queries", "date_created"])
        self.assertEqual(block["sample_queries"], ["First?", "Second?"])

    def test_hostile_strings_round_trip_through_the_json_block(self) -> None:
        """
        Hostile strings parse back verbatim from the JSON-rendered block, both as sample queries and
        inside a client-supplied key, since json.dumps escapes every value the same way.
        """
        block: dict[str, Any] = self._assemble_metadata(
            self.HOSTILE_STRINGS, {"notes": list(self.HOSTILE_STRINGS), "description": self.HOSTILE_STRINGS[3]}
        )

        self.assertEqual(list(block["sample_queries"]), self.HOSTILE_STRINGS)
        self.assertEqual(list(block["notes"]), self.HOSTILE_STRINGS)
        self.assertEqual(block["description"], "Price ${PRICE} is $5 ${?OPT}")

    def test_storage_keys_and_none_values_are_stripped_without_mutating_the_caller(self) -> None:
        """
        The keys neuro-san's reservation storage owns (reservation, stored_at) and None-valued keys are
        dropped from the written block, and the dict the caller passed in is left exactly as it was.
        """
        supplied: dict[str, Any] = {
            "description": "A demo",
            "reservation": {"id": "net-1"},
            "sample_queries": ["Old one?"],
            "stored_at": 1.0,
            "note": None,
        }
        snapshot: dict[str, Any] = deepcopy(supplied)

        text: str = self._assemble_text(["New one?"], supplied)

        block: dict[str, Any] = self._parse_metadata(text)
        # The header stamps date_created on a block without one; the rest must be exactly the kept keys.
        block.pop("date_created")
        self.assertEqual(block, {"description": "A demo", "sample_queries": ["New one?"]})
        # Stripped keys are absent from the text itself, so no "null" is ever written either.
        self.assertNotIn('"reservation"', text)
        self.assertNotIn('"stored_at"', text)
        self.assertNotIn('"note"', text)
        self.assertEqual(supplied, snapshot)

    def test_unstorable_entries_never_reach_the_file_so_it_matches_the_returned_block(self) -> None:
        """
        Entries pyhocon would read back changed are dropped before rendering, at the top level and nested alike:
        keys holding a double quote, a backslash or a newline, string values holding a bell character, empty
        strings inside lists and None-valued keys. The parsed block equals the sanitized block, which is what
        the client receives, and none of the escaped text is in the file.
        """
        supplied: dict[str, Any] = {
            "description": "A demo",
            'we"ird': "top",
            "beep": "a\x07b",
            "tags": ["", "ok", "tab\tfine"],
            "owner": {"team": "platform", "back\\slash": 1, "a\nb": 2, "lead": None},
        }

        with self.assertLogs("AgentNetworkMetadataBlock", level="WARNING"):
            text: str = self._assemble_text([], supplied)
            sanitized: dict[str, Any] = AgentNetworkMetadataBlock(supplied, "test").as_dict()
        block: dict[str, Any] = self._parse_metadata(text)

        block.pop("date_created")
        self.assertEqual(block, {"description": "A demo", "tags": ["ok", "tab\tfine"], "owner": {"team": "platform"}})
        self.assertEqual(block, sanitized)
        self.assertNotIn('we\\"ird', text)
        self.assertNotIn("\\u0007", text)
        self.assertNotIn("null", text.split('"tools"')[0])

    def test_a_non_dict_metadata_value_is_ignored_with_a_warning_naming_the_network(self) -> None:
        """
        A metadata value that is not a dict is not a block: the file is rendered as if none was given,
        so the queries still land, and one WARNING names the offending type and the network being saved
        so the client or file bug can be traced.
        """
        not_a_block: Any = "not a block"

        with self.assertLogs("AgentNetworkMetadataBlock", level="WARNING") as captured:
            block: dict[str, Any] = self._assemble_metadata(["First?"], not_a_block)

        self.assertEqual(list(block.keys()), ["sample_queries", "date_created"])
        self.assertEqual(block["sample_queries"], ["First?"])
        self.assertEqual(len(captured.output), 1)
        self.assertIn("type str (not a dict) from agent network test_net", captured.output[0])

    @staticmethod
    def _restore_with_neuro_san(hocon_text: str) -> dict[str, Any]:
        """
        Write emitted HOCON to a temp file and read its metadata block back with the restorer neuro-san,
        the designer's load path and the fallback read all use, from the repo root so the includes resolve.

        :param hocon_text: The emitted HOCON text
        :return: The "metadata" block exactly as the restorer returns it
        """
        with tempfile.NamedTemporaryFile("w", suffix=".hocon", encoding="utf-8", delete=False) as handle:
            handle.write(hocon_text)
            path: str = handle.name
        cwd: str = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            restorer: AbstractAsyncConfigRestorer = AbstractAsyncConfigRestorer(file_purpose="test", must_exist=True)
            config: dict[str, Any] = asyncio.run(restorer.async_restore(file_reference=path))
        finally:
            os.chdir(cwd)
            os.unlink(path)
        return config["metadata"]

    def test_dotted_and_url_keys_round_trip_verbatim_through_the_restorer(self) -> None:
        """
        Keys holding dots (a URL, "owner.name", "a.b.c") come back exactly as written, top-level and nested,
        through neuro-san's restorer. pyhocon keeps such keys quoted inside its ConfigTree, which is why the
        _unquote() helper on this class exists for raw-tree assertions, but the as_plain_ordered_dict() conversion
        every real reader applies (leaf_common's HoconSerializationFormat) removes the quotes again.
        """
        supplied: dict[str, Any] = {
            "owner.name": "platform",
            "https://x.example.com/z": ["Authorization"],
            "nested": {"a.b.c": 1},
        }
        text: str = self._assemble_text([], supplied)

        block: dict[str, Any] = self._restore_with_neuro_san(text)

        block.pop("date_created")
        self.assertEqual(block, supplied)
        self.assertEqual(list(block.keys()), list(supplied.keys()))

    def test_emitted_text_with_a_metadata_block_still_parses_with_the_repo_root_includes(self) -> None:
        """
        The JSON block sits between the two include statements of the header; with a populated block the
        whole file still parses from the repo root and both includes contribute their keys.
        """
        text: str = self._assemble_text(["Q?"], {"description": "A demo", "tags": ["generated"]})

        config: dict[str, Any] = self._parse(text)

        # registries/aaosa.hocon and config/llm_config.hocon resolved, so the block broke neither include.
        self.assertIn("aaosa_call", config)
        self.assertIn("llm_config", config)
        self.assertEqual(config["max_execution_seconds"], GENERATED_NETWORK_MAX_EXECUTION_SECONDS)
        self.assertEqual(config["tools"][0]["name"], "front_man")
        self.assertEqual(config["metadata"]["description"], "A demo")
