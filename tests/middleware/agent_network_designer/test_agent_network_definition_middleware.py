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
Tests for AgentNetworkDefinitionMiddleware: path resolution, the loaded metadata block, failed loads, and the
removal of designer wrapper copies from the definition.
"""

import asyncio
import json
import os
import shutil
import tempfile
from copy import deepcopy
from logging import LogRecord
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from langchain_core.messages import AIMessage
from pyhocon import ConfigFactory
from pyhocon import ConfigTree

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_METADATA
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from middleware.agent_network_designer.agent_network_definition_middleware import AAOSA_FILE
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_HOCON_FILE
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_RESERVATIONS
from middleware.agent_network_designer.agent_network_definition_middleware import RESERVATION_ID
from middleware.agent_network_designer.agent_network_definition_middleware import SKIP_DESIGNER
from middleware.agent_network_designer.agent_network_definition_middleware import AgentNetworkDefinitionMiddleware
from middleware.agent_network_designer.persistence.deployable_agent_network_assembler import (
    DeployableAgentNetworkAssembler,
)
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HOCON_HEADER_START
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler

# A metadata block the way neuro-san's reservation storage writers store it: the user-authored keys, plus
# "reservation" in ReservationDictionaryConverter's shape and "stored_at" as time.time(). Those two describe
# one temporary deployment and must never reach the client (issue #1398).
STORED_METADATA: dict[str, Any] = {
    "description": "d",
    "sample_queries": ["q"],
    "reservation": {
        "id": "net_abc-550e8400-e29b-41d4-a716-446655440000",
        "lifetime_in_seconds": 3600.0,
        "expiration_time_in_seconds": 1758003600.0,
    },
    "stored_at": 1758000000.123,
}
# What the client must receive after loading STORED_METADATA: the storage-owned keys stripped.
STRIPPED_METADATA: dict[str, Any] = {"description": "d", "sample_queries": ["q"]}
# A block the way a client sends it back from a previous save. The designer is stateless, so
# when nothing is loaded this block is the persist step's only source and must pass through
# the hook untouched, server-owned date keys included.
CLIENT_METADATA: dict[str, Any] = {
    "description": "client",
    "sample_queries": ["q1", "q2"],
    "date_created": "2026-01-01T00:00:00+00:00",
}
# The definition the middleware derives from the two-agent "tools" list built by _tools().
EXPECTED_DEFINITION: dict[str, Any] = {
    "front_man": {"instructions": "Do things.", "description": "top", "tools": ["helper"]},
    "helper": {"instructions": "Help.", "description": "h"},
}
# A reservation id the way neuro-san mints them: <prefix>-<uuid4>; the middleware derives the network
# name by stripping the UUID suffix, so the expected name is the prefix alone.
RESERVATION_ID_VALUE: str = "net_abc-550e8400-e29b-41d4-a716-446655440000"
EXPECTED_NETWORK_NAME: str = "net_abc"
S3_BUCKET: str = "bucket"
# The logger name AgentNetworkDefinitionMiddleware builds from its class name.
MIDDLEWARE_LOGGER: str = "AgentNetworkDefinitionMiddleware"
# Generated networks include registries/aaosa.hocon relative to the repository root.
REPO_ROOT: Path = Path(__file__).resolve().parents[3]
# Patched to point the once-per-process read of the AAOSA instructions at another file.
AAOSA_FILE_TARGET: str = "middleware.agent_network_designer.agent_network_definition_middleware.AAOSA_FILE"
# A definition holding only the agents' own text (issue #1458): a front man, an agent with tools and a leaf. The
# texts are one line each because a network loaded from a file still has its whitespace collapsed (issue #1456).
OWN_TEXT_DEFINITION: dict[str, Any] = {
    "front": {"instructions": "Route travel requests.", "tools": ["booker", "weather"]},
    "booker": {"instructions": "Book trips.", "tools": ["weather"]},
    "weather": {"instructions": "Report the weather."},
}
# Words that occur once in the AAOSA instructions and nowhere in OWN_TEXT_DEFINITION, for counting copies.
AAOSA_MARKER: str = "When you receive an inquiry, you will:"


class TestAgentNetworkDefinitionMiddleware(IsolatedAsyncioTestCase):  # pylint: disable=too-many-public-methods
    """
    Tests for AgentNetworkDefinitionMiddleware.

    Covers _resolve_hocon_path (synchronous path resolution) and the abefore_model hook's
    hand-off of a loaded network's metadata block (issue #1398). The designer is stateless:
    the client owns the network's top-level "metadata" block and sends it back under
    AGENT_NETWORK_METADATA. A network the hook loads from a HOCON file or an S3 reservation
    must therefore leave that network's sanitized block under the key, replacing whatever the
    client sent, while a definition passed directly or a failed load must not touch the key.

    A load whose "tools" yields no usable agent is a failed load, not a silent no-op, and the
    S3 path sets AGENT_NETWORK_NAME only when a definition was loaded, like the HOCON path
    always did (issue #1426); the tests for both are here as well.

    Also covers the error each branch of _hocon_to_config reports for a file that cannot be
    loaded (issue #1440): a parse or substitution failure, an unsupported or upper-case
    extension, an unreadable path and a missing file, driven through the real restorer, plus
    the hook's hand-off of that error to the client.

    Finally covers the removal of copies of the designer's instruction wrapper from the definition
    (issue #1458), for a definition sent in sly_data, a network loaded from a generated file and one
    loaded from an S3 reservation, and where the AAOSA instructions to strip come from.
    """

    def setUp(self) -> None:
        """
        Create a scratch directory for the HOCON files the load tests write.
        """
        # mkdtemp + addCleanup(rmtree) rather than TemporaryDirectory(): pylint flags the latter
        # with consider-using-with (R1732), and fail-under=10.0 turns any message into a CI failure.
        self.temp_dir: str = tempfile.mkdtemp(prefix="and_definition_mw_")
        self.addCleanup(shutil.rmtree, self.temp_dir, True)

    # Tests for AGENT_MANIFEST_FILE parsing, mirroring the persistor's parsing tests
    # so loads and saves stay in agreement on file location.

    def test_resolve_splits_manifest_env_var_on_pathsep(self) -> None:
        """
        _resolve_hocon_path derives base_dir from the first entry of an os.pathsep-separated AGENT_MANIFEST_FILE.
        """
        first_manifest: str = os.path.join("first_dir", "manifest.hocon")
        second_manifest: str = os.path.join("second_dir", "manifest.hocon")
        env_value: str = os.pathsep.join([first_manifest, second_manifest])
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": env_value}):
            middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data={})
            # The input must not exist relative to cwd, so resolution falls through to base_dir.
            resolved: str | None = middleware._resolve_hocon_path(  # pylint: disable=protected-access
                "generated/does_not_exist.hocon"
            )
        self.assertEqual(resolved, "first_dir/generated/does_not_exist.hocon")

    def test_resolve_skips_empty_leading_entry(self) -> None:
        """
        _resolve_hocon_path uses the first non-empty entry when AGENT_MANIFEST_FILE has a leading separator.
        """
        env_value: str = os.pathsep + os.path.join("first_dir", "manifest.hocon")
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": env_value}):
            middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data={})
            resolved: str | None = middleware._resolve_hocon_path(  # pylint: disable=protected-access
                "generated/does_not_exist.hocon"
            )
        self.assertEqual(resolved, "first_dir/generated/does_not_exist.hocon")

    def test_resolve_defaults_when_manifest_env_var_empty(self) -> None:
        """
        _resolve_hocon_path falls back to the default registries dir when AGENT_MANIFEST_FILE is empty.
        """
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": ""}):
            middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data={})
            resolved: str | None = middleware._resolve_hocon_path(  # pylint: disable=protected-access
                "generated/does_not_exist.hocon"
            )
        self.assertEqual(resolved, "registries/generated/does_not_exist.hocon")

    # Tests for the error branches of _hocon_to_config (issue #1440). Every message here is what the
    # client sees: abefore_model puts self.error_message straight into the AIMessage it jumps to end with.

    def _write_config_file(self, name: str, contents: str) -> str:
        """
        Write raw text to a file in the scratch directory, bypassing the JSON writer so the
        test can produce content no serializer would emit.

        :param name: File name including extension; the extension is what the screen under test reads
        :param contents: Exact bytes to write, malformed on purpose in most of these tests
        :return: The absolute path, which _resolve_hocon_path uses as-is
        """
        path: str = os.path.join(self.temp_dir, name)
        with open(path, "w", encoding="utf-8") as config_file:
            config_file.write(contents)
        return path

    async def _assert_load_error(
        self, name: str, contents: str | None, expected: str, details: tuple[str, ...] = ()
    ) -> AgentNetworkDefinitionMiddleware:
        """
        Load a config file through _hocon_to_config and check the error it reports.

        :param name: File name to load from the scratch directory
        :param contents: Text to write first, or None to write nothing, for a path that is absent or a
                directory the test created
        :param expected: Substring the reported message and the logged ERROR line must both contain
        :param details: Additional substrings required in the reported message
        :return: Middleware instance that reported the error
        """
        path: str = (
            self._write_config_file(name, contents) if contents is not None else os.path.join(self.temp_dir, name)
        )
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data={})

        with self.assertLogs(MIDDLEWARE_LOGGER, level="ERROR") as captured:
            config: dict[str, Any] | None = await middleware._hocon_to_config(path)  # pylint: disable=protected-access

        self.assertIsNone(config)
        self.assertIn(expected, middleware.error_message)
        self.assertIn(path, middleware.error_message)
        self.assertIn(expected, captured.output[0])
        for detail in details:
            self.assertIn(detail, middleware.error_message)
        return middleware

    async def test_abefore_model_routes_config_load_error_to_end(self) -> None:
        """
        A config load failure is returned to the client through abefore_model as one AIMessage carrying
        the error text and an end jump, is logged once at ERROR, and sets neither the name nor the
        definition nor the metadata block, so nothing is left behind for a network that did not load.
        """
        path: str = self._write_config_file("malformed.hocon", '{"tools": [{"name": "a")')
        sly_data: dict[str, Any] = {AGENT_NETWORK_HOCON_FILE: path}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        with self.assertLogs(MIDDLEWARE_LOGGER, level="WARNING") as captured:
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("jump_to"), "end")
        messages: list[Any] = result.get("messages")
        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], AIMessage)
        self.assertEqual(messages[0].content, middleware.error_message)
        self.assertIn("Failed to parse agent network config file", middleware.error_message)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)
        self.assertNotIn(AGENT_NETWORK_DEFINITION, sly_data)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        # Exactly one record at WARNING or above, and it is the ERROR carrying the error text.
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(self._messages_at_level(captured.records, "ERROR"), [middleware.error_message])

    async def test_hocon_to_config_reports_parse_failure_for_malformed_hocon(self) -> None:
        """
        A .hocon file with a syntax error is reported as a parse failure, not an unsupported file.

        The restorer re-raises pyparsing's ParseSyntaxException as ValueError, which used to land in
        the "Unsupported" branch and tell a user with a typo that the file type was wrong.
        """
        await self._assert_load_error(
            "malformed.hocon",
            '{"tools": [{"name": "a")',
            "Failed to parse agent network config file",
            ("ParseSyntaxException",),
        )

    async def test_hocon_to_config_reports_parse_failure_for_unresolved_substitution(self) -> None:
        """
        A .hocon file with an unresolved ${...} reference is reported as a parse failure.

        pyhocon raises ConfigSubstitutionException after parsing succeeds; the restorer folds it into
        the same ValueError, so it must surface the same way.
        """
        await self._assert_load_error(
            "missing_sub.hocon",
            "tools = [${nope}]",
            "Failed to parse agent network config file",
            ("ConfigSubstitutionException", "nope"),
        )

    async def test_hocon_to_config_reports_parse_failure_for_malformed_json(self) -> None:
        """
        A .json file that is not valid JSON is reported as a parse failure: the restorer accepts
        .json as readily as .hocon, and its JSONDecodeError arrives as the same ValueError.
        """
        await self._assert_load_error(
            "bad.json", '{"tools": [}', "Failed to parse agent network config file", ("JSONDecodeError",)
        )

    async def test_hocon_to_config_reports_unsupported_extension_and_names_the_accepted_ones(self) -> None:
        """
        A file whose extension is neither .hocon nor .json is the one genuinely unsupported case, and
        the message names the extensions that would work.
        """
        middleware: AgentNetworkDefinitionMiddleware = await self._assert_load_error(
            "wrong.txt", "tools = []", "Unsupported agent network config file"
        )
        self.assertIn(".hocon", middleware.error_message)
        self.assertIn(".json", middleware.error_message)

    async def test_hocon_to_config_reports_unsupported_extension_before_checking_existence(self) -> None:
        """
        A path that does not exist and ends in an unsupported extension is reported as unsupported, not
        as not found: the extension check runs before the restorer reads anything, so a typo'd path with
        the wrong suffix gets the more actionable message.
        """
        await self._assert_load_error("absent.txt", None, "Unsupported agent network config file")

    async def test_hocon_to_config_rejects_an_upper_case_extension(self) -> None:
        """
        The extension check is case-sensitive, like the restorer's own, so network.HOCON is unsupported.
        Were the check ever relaxed, the restorer would still reject the file with its ValueError and the
        parse handler would report it as "Failed to parse": the #1440 mix-up in reverse.
        """
        await self._assert_load_error("network.HOCON", "tools = []", "Unsupported agent network config file")

    async def test_hocon_to_config_reports_read_failure_for_a_directory(self) -> None:
        """
        A directory whose name ends in .hocon passes the extension check and then fails to open, which
        the OSError handler reports as a read failure rather than a parse failure or a missing file.
        """
        os.mkdir(os.path.join(self.temp_dir, "directory.hocon"))
        await self._assert_load_error("directory.hocon", None, "Failed to read agent network config file")

    async def test_hocon_to_config_reports_missing_file(self) -> None:
        """
        A supported extension that does not exist is reported as missing, not as a parse failure:
        the extension screen passes it through to the restorer, which raises FileNotFoundError.
        """
        await self._assert_load_error("absent.hocon", None, "Agent network config file not found")

    # Tests for the metadata block abefore_model returns in sly_data after a load (issue #1398).

    @staticmethod
    def _tools() -> list[dict[str, Any]]:
        """
        Build the "tools" list of a two-agent network config: a front man delegating to one helper.

        :return: A fresh list of agent specs in the HOCON "tools" shape, so a test may mutate it freely
        """
        return [
            {
                "name": "front_man",
                "instructions": "Do things.",
                "function": {"description": "top"},
                "tools": ["helper"],
            },
            {"name": "helper", "instructions": "Help.", "function": {"description": "h"}},
        ]

    def _sly_data_for_file(self, stem: str, config: dict[str, Any]) -> dict[str, Any]:
        """
        Write a network config to an include-free .hocon file (JSON syntax) and point sly_data at it.

        :param stem: File name without extension; the middleware adopts it as the network name
        :param config: The config dict to serialize
        :return: A sly_data dict holding only the AGENT_NETWORK_HOCON_FILE entry
        """
        # The file lives under the scratch directory with an absolute path, which _resolve_hocon_path
        # uses as-is, so AGENT_MANIFEST_FILE plays no part in the tests that call this helper.
        path: str = os.path.join(self.temp_dir, f"{stem}.hocon")
        with open(path, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file)
        return {AGENT_NETWORK_HOCON_FILE: path}

    async def _abefore_model_from_s3(
        self, middleware: AgentNetworkDefinitionMiddleware, config: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Run abefore_model with the S3 round trip replaced by a stand-in that returns the given config.

        :param middleware: The middleware under test, built over sly_data that names a reservation
        :param config: The config dict the patched fetch_reservation_from_s3 returns
        :return: Whatever abefore_model returned
        """
        # Same stand-in as the happy-path S3 test: fetch_reservation_from_s3 is a @staticmethod the hook
        # runs through asyncio.to_thread, so a synchronous mock with a return_value is enough.
        with (
            patch.dict(os.environ, {"AGENT_RESERVATIONS_S3_BUCKET": S3_BUCKET}),
            patch.object(AgentNetworkDefinitionMiddleware, "fetch_reservation_from_s3", return_value=config),
        ):
            return await middleware.abefore_model({}, None)

    @staticmethod
    def _messages_at_level(records: list[LogRecord], level_name: str) -> list[str]:
        """
        Collect the formatted messages of the captured records emitted at one level.

        :param records: The records an assertLogs context captured
        :param level_name: The level name to keep, for example "WARNING"
        :return: The messages of the records at that level, in emission order
        """
        messages: list[str] = []
        for record in records:
            if record.levelname == level_name:
                messages.append(record.getMessage())
        return messages

    async def test_abefore_model_returns_stripped_metadata_from_hocon_file(self) -> None:
        """
        Loading a HOCON file returns its metadata block minus the storage-owned keys, and still
        derives the network name from the file stem and the definition from the "tools" list.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": self._tools()}
        sly_data: dict[str, Any] = self._sly_data_for_file("my_network", config)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        self.assertEqual(sly_data[AGENT_NETWORK_METADATA], STRIPPED_METADATA)
        self.assertEqual(sly_data[AGENT_NETWORK_NAME], "my_network")
        self.assertEqual(sly_data[AGENT_NETWORK_DEFINITION], EXPECTED_DEFINITION)

    async def test_abefore_model_returns_empty_metadata_when_config_has_none(self) -> None:
        """
        Loading a HOCON file without a "metadata" key returns an empty dict, replacing the block
        the client sent: the loaded network's state is authoritative for the persist step, so a
        block that belongs to a different network cannot leak into this one.
        """
        sly_data: dict[str, Any] = self._sly_data_for_file("bare_network", {"tools": self._tools()})
        # A block from an earlier turn about another network; the load must not keep it.
        sly_data[AGENT_NETWORK_METADATA] = dict(CLIENT_METADATA)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        # A file without the key is ordinary: no warning from the hook or the block class.
        with (
            self.assertNoLogs(MIDDLEWARE_LOGGER, level="WARNING"),
            self.assertNoLogs("AgentNetworkMetadataBlock", level="WARNING"),
        ):
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        self.assertEqual(sly_data[AGENT_NETWORK_METADATA], {})
        self.assertEqual(sly_data[AGENT_NETWORK_NAME], "bare_network")

    async def test_abefore_model_returns_empty_metadata_and_warns_for_null_metadata(self) -> None:
        """
        A file whose "metadata" is an explicit null (never something the assemblers write) is treated like
        any other non-dict block, with one WARNING from the hook naming the file, unlike a file without the
        key, which is quiet: the client receives an empty block and the load itself still succeeds.
        """
        config: dict[str, Any] = {"metadata": None, "tools": self._tools()}
        sly_data: dict[str, Any] = self._sly_data_for_file("nully_network", config)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        with self.assertLogs(MIDDLEWARE_LOGGER, level="WARNING") as captured:
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        self.assertEqual(sly_data[AGENT_NETWORK_METADATA], {})
        self.assertEqual(sly_data[AGENT_NETWORK_NAME], "nully_network")
        self.assertEqual(len(captured.records), 1)
        self.assertIn("null 'metadata'", captured.output[0])
        self.assertIn(sly_data[AGENT_NETWORK_HOCON_FILE], captured.output[0])

    async def test_abefore_model_returns_empty_metadata_and_warns_for_list_metadata(self) -> None:
        """
        A "metadata" value that is not a dict is ignored with a WARNING naming the file, the
        returned block is an empty dict, and the load itself still succeeds.
        """
        config: dict[str, Any] = {"metadata": ["d"], "tools": self._tools()}
        sly_data: dict[str, Any] = self._sly_data_for_file("listy_network", config)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        with self.assertLogs("AgentNetworkMetadataBlock", level="WARNING") as captured:
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        self.assertEqual(sly_data[AGENT_NETWORK_METADATA], {})
        self.assertEqual(sly_data[AGENT_NETWORK_NAME], "listy_network")
        self.assertEqual(len(captured.records), 1)
        # The warning must say what was found and where, so an operator can fix the file.
        self.assertIn("Ignoring metadata block of type list (not a dict) from", captured.output[0])
        self.assertIn(sly_data[AGENT_NETWORK_HOCON_FILE], captured.output[0])

    async def test_abefore_model_returns_stripped_metadata_from_s3_reservation(self) -> None:
        """
        Loading an S3 reservation returns the stored metadata block minus the storage-owned keys
        and derives the network name from the reservation id.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": self._tools()}
        sly_data: dict[str, Any] = {AGENT_RESERVATIONS: [{RESERVATION_ID: RESERVATION_ID_VALUE}]}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        # fetch_reservation_from_s3 is a @staticmethod the hook runs through asyncio.to_thread, so a
        # plain synchronous mock with a return_value stands in for the boto3 round trip.
        with (
            patch.dict(os.environ, {"AGENT_RESERVATIONS_S3_BUCKET": S3_BUCKET}),
            patch.object(AgentNetworkDefinitionMiddleware, "fetch_reservation_from_s3", return_value=config) as fetch,
        ):
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        fetch.assert_called_once_with(S3_BUCKET, RESERVATION_ID_VALUE)
        self.assertEqual(sly_data[AGENT_NETWORK_METADATA], STRIPPED_METADATA)
        self.assertEqual(sly_data[AGENT_NETWORK_NAME], EXPECTED_NETWORK_NAME)
        self.assertEqual(sly_data[AGENT_NETWORK_DEFINITION], EXPECTED_DEFINITION)

    async def test_abefore_model_leaves_metadata_absent_for_direct_definition(self) -> None:
        """
        A definition passed directly in sly_data loads nothing, so no metadata is returned: the
        key stays absent and the persist step starts from an empty block, because the stateless
        designer never reads an existing file for it.
        """
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: dict(EXPECTED_DEFINITION),
            # The name is required whenever the definition is passed directly; without it the hook
            # takes its error path, which is not what this test is about.
            AGENT_NETWORK_NAME: "direct_network",
        }
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        self.assertEqual(sly_data[AGENT_NETWORK_DEFINITION], EXPECTED_DEFINITION)

    async def test_abefore_model_keeps_client_metadata_for_direct_definition(self) -> None:
        """
        A definition passed directly alongside the client's metadata block leaves that block exactly
        as sent, same object and same content: sanitizing and stamping it is the persist step's job.
        """
        client_block: dict[str, Any] = dict(CLIENT_METADATA)
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: dict(EXPECTED_DEFINITION),
            AGENT_NETWORK_NAME: "direct_network",
            AGENT_NETWORK_METADATA: client_block,
        }
        # Snapshot before the call so an in-place mutation would also be caught, not only a rebind.
        sent: dict[str, Any] = deepcopy(client_block)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        self.assertIs(sly_data[AGENT_NETWORK_METADATA], client_block)
        self.assertEqual(sly_data[AGENT_NETWORK_METADATA], sent)

    async def test_abefore_model_reports_error_and_returns_no_metadata_when_tools_not_list(self) -> None:
        """
        A config whose "tools" is not a list fails the load before any metadata is returned: the
        hook reports the error and jumps to end, and neither the block nor the name is set.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": "front_man"}
        sly_data: dict[str, Any] = self._sly_data_for_file("broken_network", config)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["jump_to"], "end")
        self.assertIn("not a list", result["messages"][0].content)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)
        self.assertNotIn(AGENT_NETWORK_DEFINITION, sly_data)

    async def test_abefore_model_failed_load_leaves_client_metadata_untouched(self) -> None:
        """
        A failed load must not disturb a block the client sent with the same request: after the jump to end
        the client's block is still there, unchanged, so the client keeps the state it holds for the network
        it was working on.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": "front_man"}
        sly_data: dict[str, Any] = self._sly_data_for_file("broken_network", config)
        sly_data[AGENT_NETWORK_METADATA] = deepcopy(CLIENT_METADATA)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["jump_to"], "end")
        self.assertEqual(sly_data[AGENT_NETWORK_METADATA], CLIENT_METADATA)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)

    async def test_abefore_model_reports_error_and_returns_no_metadata_when_tools_yield_no_agents(self) -> None:
        """
        A config whose "tools" list parses but yields no agents (every entry lacks a "name") is a failed
        load, not a silent no-op (issue #1426): the hook reports an error naming the file and saying no
        usable agent was found, jumps to end, still warns once per skipped entry, and sets neither the
        block nor the name nor the definition.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": [{"instructions": "Nameless."}]}
        sly_data: dict[str, Any] = self._sly_data_for_file("nameless_network", config)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        with self.assertLogs(MIDDLEWARE_LOGGER, level="WARNING") as captured:
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("jump_to"), "end")
        message: str = result.get("messages")[0].content
        self.assertIn("No usable agent found", message)
        self.assertIn(sly_data.get(AGENT_NETWORK_HOCON_FILE), message)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)
        self.assertNotIn(AGENT_NETWORK_DEFINITION, sly_data)
        # Still one skip warning per unusable entry, naming the file so an operator can fix it, and the
        # error the client received logged once at ERROR: nothing else.
        warnings: list[str] = self._messages_at_level(captured.records, "WARNING")
        self.assertEqual(len(warnings), 1)
        self.assertIn("missing/invalid 'name'", warnings[0])
        self.assertIn(sly_data.get(AGENT_NETWORK_HOCON_FILE), warnings[0])
        self.assertEqual(self._messages_at_level(captured.records, "ERROR"), [message])
        self.assertEqual(len(captured.records), 2)

    async def test_abefore_model_reports_error_when_tools_list_is_empty(self) -> None:
        """
        An empty "tools" list is the same failed load as a list whose entries are all skipped (issue #1426):
        the hook reports that no usable agent was found, naming the file, jumps to end, logs that once at
        ERROR with no skip warning (there was no entry to skip), and sets neither the block nor the name
        nor the definition.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": []}
        sly_data: dict[str, Any] = self._sly_data_for_file("empty_network", config)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        with self.assertLogs(MIDDLEWARE_LOGGER, level="WARNING") as captured:
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("jump_to"), "end")
        message: str = result.get("messages")[0].content
        self.assertIn("No usable agent found", message)
        self.assertIn(sly_data.get(AGENT_NETWORK_HOCON_FILE), message)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)
        self.assertNotIn(AGENT_NETWORK_DEFINITION, sly_data)
        self.assertEqual(self._messages_at_level(captured.records, "WARNING"), [])
        self.assertEqual(self._messages_at_level(captured.records, "ERROR"), [message])

    async def test_abefore_model_leaves_name_unset_when_s3_tools_not_list(self) -> None:
        """
        An S3 reservation whose spec has a "tools" that is not a list fails the load the same way a HOCON
        file does, and leaves AGENT_NETWORK_NAME unset (issue #1426): before the fix the S3 path derived
        the name from the reservation id before loading, so the request ended with a name and no definition.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": "front_man"}
        sly_data: dict[str, Any] = {AGENT_RESERVATIONS: [{RESERVATION_ID: RESERVATION_ID_VALUE}]}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await self._abefore_model_from_s3(middleware, config)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("jump_to"), "end")
        self.assertIn("not a list", result.get("messages")[0].content)
        self.assertIn(RESERVATION_ID_VALUE, result.get("messages")[0].content)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        self.assertNotIn(AGENT_NETWORK_DEFINITION, sly_data)

    async def test_abefore_model_reports_error_and_leaves_name_unset_when_s3_tools_yield_no_agents(self) -> None:
        """
        An S3 reservation whose "tools" list yields no usable agent reports the same error as the HOCON
        path, naming the reservation, and leaves AGENT_NETWORK_NAME unset along with the block and the
        definition (issue #1426); the per-entry skip warning still names the reservation.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": [{"instructions": "Nameless."}]}
        sly_data: dict[str, Any] = {AGENT_RESERVATIONS: [{RESERVATION_ID: RESERVATION_ID_VALUE}]}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        with self.assertLogs(MIDDLEWARE_LOGGER, level="WARNING") as captured:
            result: dict[str, Any] | None = await self._abefore_model_from_s3(middleware, config)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("jump_to"), "end")
        message: str = result.get("messages")[0].content
        self.assertIn("No usable agent found", message)
        self.assertIn(RESERVATION_ID_VALUE, message)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        self.assertNotIn(AGENT_NETWORK_DEFINITION, sly_data)
        warnings: list[str] = self._messages_at_level(captured.records, "WARNING")
        self.assertEqual(len(warnings), 1)
        self.assertIn("missing/invalid 'name'", warnings[0])
        self.assertIn(RESERVATION_ID_VALUE, warnings[0])
        self.assertEqual(self._messages_at_level(captured.records, "ERROR"), [message])

    # Tests for the removal of designer wrapper copies from the definition (issue #1458). The rules per role are
    # tested with DesignerInstructionUnwrapper itself; these check that the hook applies them to every source
    # before anything reads the definition.

    @staticmethod
    async def _resolved_definition(definition: dict[str, Any], network_name: str) -> dict[str, Any]:
        """
        Save a definition as HOCON and read it back as nsflow's editor does, with the substitutions resolved.

        :param definition: The definition to save
        :param network_name: The network name to save it under
        :return: Agent name to the resolved instructions and, when present, the tools
        """
        text: str = await HoconAgentNetworkAssembler(True).assemble_agent_network(
            definition, "front", network_name, []
        )
        config: ConfigTree = ConfigFactory.parse_string(text, basedir=str(REPO_ROOT))
        resolved: dict[str, Any] = {}
        for agent in config.get("tools"):
            entry: dict[str, Any] = {"instructions": agent.get("instructions")}
            tools: list[str] | None = agent.get("tools", None)
            if tools:
                entry["tools"] = list(tools)
            resolved[agent.get("name")] = entry
        return resolved

    async def test_abefore_model_unwraps_a_resolved_definition_before_a_skip_designer_save(self) -> None:
        """
        A skip_designer save of instructions that hold the wrapper twice, resolved from saves under other network
        names, leaves only the own text in sly_data, where the persistence middleware validates, saves and returns
        the definition.
        """
        resolved: dict[str, Any] = await self._resolved_definition(OWN_TEXT_DEFINITION, "old_name")
        resolved = await self._resolved_definition(resolved, "generated/old_name")
        self.assertEqual(resolved.get("front").get("instructions").count(AAOSA_MARKER), 2)
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: resolved,
            AGENT_NETWORK_NAME: "new_name",
            SKIP_DESIGNER: True,
        }
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertEqual(result.get("jump_to"), "end")
        self.assertEqual(sly_data.get(AGENT_NETWORK_DEFINITION), OWN_TEXT_DEFINITION)
        self.assertEqual(middleware.network_def, OWN_TEXT_DEFINITION)

    async def test_abefore_model_strips_the_aaosa_instructions_from_a_hand_written_leaf(self) -> None:
        """
        A hand-written network that gives a leaf the AAOSA instructions, as registries/basic/smart_home.hocon does,
        loads with them removed from that leaf too: the designer never writes them for a leaf, so after the next
        save the leaf works like the ones the designer writes.
        """
        text: str = (
            "{\n"
            '  include "registries/aaosa.hocon"\n'
            '  "tools": [\n'
            '    {"name": "house", "instructions": "Control the house." ${aaosa_instructions}, "tools": ["Book"]},\n'
            '    {"name": "Book", "instructions": "Your name is Book. You are a book." ${aaosa_instructions}}\n'
            "  ]\n"
            "}\n"
        )
        path: str = self._write_config_file("smart_house.hocon", text)
        sly_data: dict[str, Any] = {AGENT_NETWORK_HOCON_FILE: path}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        loaded: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        self.assertEqual(loaded.get("house").get("instructions"), "Control the house.")
        self.assertEqual(loaded.get("Book").get("instructions"), "Your name is Book. You are a book.")

    async def test_abefore_model_keeps_a_definition_without_wrapper_copies_as_sent(self) -> None:
        """
        A definition holding only own text is neither copied nor changed: sly_data keeps the very dict the client
        sent.
        """
        sent: dict[str, Any] = deepcopy(OWN_TEXT_DEFINITION)
        sly_data: dict[str, Any] = {AGENT_NETWORK_DEFINITION: sent, AGENT_NETWORK_NAME: "travel", SKIP_DESIGNER: True}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        await middleware.abefore_model({}, None)

        self.assertIs(sly_data.get(AGENT_NETWORK_DEFINITION), sent)
        self.assertEqual(sent, OWN_TEXT_DEFINITION)

    async def test_abefore_model_unwraps_a_network_loaded_from_a_generated_hocon_file(self) -> None:
        """
        A network the designer saved and then loads again through agent_network_hocon_file comes back as the own
        text, instead of the resolved wrapper the next save would add to.
        """
        text: str = await HoconAgentNetworkAssembler(True).assemble_agent_network(
            OWN_TEXT_DEFINITION, "front", "travel", []
        )
        path: str = self._write_config_file("travel.hocon", text)
        sly_data: dict[str, Any] = {AGENT_NETWORK_HOCON_FILE: path}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNone(result)
        loaded: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        for agent_name, agent in OWN_TEXT_DEFINITION.items():
            with self.subTest(agent_name=agent_name):
                self.assertEqual(loaded.get(agent_name).get("instructions"), agent.get("instructions"))

    async def test_abefore_model_unwraps_a_network_loaded_from_an_s3_reservation(self) -> None:
        """
        A network deployed in reservations mode and loaded again from its S3 copy comes back as the own text.
        """
        spec: dict[str, Any] = await DeployableAgentNetworkAssembler(True).assemble_agent_network(
            OWN_TEXT_DEFINITION, "front", "travel", []
        )
        sly_data: dict[str, Any] = {AGENT_RESERVATIONS: [{RESERVATION_ID: RESERVATION_ID_VALUE}]}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await self._abefore_model_from_s3(middleware, spec)

        self.assertIsNone(result)
        loaded: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        for agent_name, agent in OWN_TEXT_DEFINITION.items():
            with self.subTest(agent_name=agent_name):
                self.assertEqual(loaded.get(agent_name).get("instructions"), agent.get("instructions"))

    async def test_abefore_model_ignores_aaosa_instructions_sent_in_sly_data(self) -> None:
        """
        The AAOSA instructions to strip come from registries/aaosa.hocon, never from sly_data, which the client
        writes: a value planted under the key the load path caches it in changes nothing.
        """
        resolved: dict[str, Any] = await self._resolved_definition(OWN_TEXT_DEFINITION, "travel")
        sly_data: dict[str, Any] = {
            AGENT_NETWORK_DEFINITION: resolved,
            AGENT_NETWORK_NAME: "travel",
            "aaosa_instructions": "Not the AAOSA instructions.",
        }
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        await middleware.abefore_model({}, None)

        self.assertEqual(sly_data.get(AGENT_NETWORK_DEFINITION), OWN_TEXT_DEFINITION)

    async def test_abefore_model_warns_once_and_keeps_aaosa_copies_when_the_aaosa_file_is_missing(self) -> None:
        """
        Without registries/aaosa.hocon the AAOSA copies cannot be recognized: the other pieces are still stripped,
        the AAOSA text stays, and the missing file is reported once for the process, not on every model call, even
        when the first calls run at the same time and all read the file.
        """
        resolved: dict[str, Any] = await self._resolved_definition(OWN_TEXT_DEFINITION, "travel")
        missing: str = os.path.join(self.temp_dir, "no_aaosa.hocon")
        sly_datas: list[dict[str, Any]] = []
        for _ in range(3):
            sly_datas.append({AGENT_NETWORK_DEFINITION: deepcopy(resolved), AGENT_NETWORK_NAME: "travel"})
        warnings: list[str] = []
        with (
            patch(AAOSA_FILE_TARGET, missing),
            patch.object(AgentNetworkDefinitionMiddleware, "_wrapper_aaosa_instructions", None),
            self.assertLogs(MIDDLEWARE_LOGGER, level="WARNING") as captured,
        ):
            # The first two start together, as concurrent first requests do: the file read awaits, so both miss the
            # cache and read it. The third comes after them and gets the cached value.
            await asyncio.gather(
                AgentNetworkDefinitionMiddleware(sly_data=sly_datas[0]).abefore_model({}, None),
                AgentNetworkDefinitionMiddleware(sly_data=sly_datas[1]).abefore_model({}, None),
            )
            await AgentNetworkDefinitionMiddleware(sly_data=sly_datas[2]).abefore_model({}, None)
            warnings = self._messages_at_level(captured.records, "WARNING")

        for index, sly_data in enumerate(sly_datas):
            with self.subTest(call=index):
                front: str = sly_data.get(AGENT_NETWORK_DEFINITION).get("front").get("instructions")
                self.assertTrue(front.startswith("Route travel requests."))
                self.assertEqual(front.count(AAOSA_MARKER), 1)
        self.assertEqual(len(warnings), 1)
        self.assertIn(missing, warnings[0])

    def test_the_aaosa_file_read_is_the_one_generated_networks_include(self) -> None:
        """
        The AAOSA instructions stripped are those of the file every generated network includes, so what the save
        adds is what gets recognized.
        """
        self.assertIn(f'include "{AAOSA_FILE}"', HOCON_HEADER_START)
