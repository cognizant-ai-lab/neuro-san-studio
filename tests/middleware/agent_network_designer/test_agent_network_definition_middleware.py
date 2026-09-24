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

"""Tests for AgentNetworkDefinitionMiddleware path resolution and the loaded metadata block it returns."""

import json
import os
import shutil
import tempfile
from copy import deepcopy
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_METADATA
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_HOCON_FILE
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_RESERVATIONS
from middleware.agent_network_designer.agent_network_definition_middleware import RESERVATION_ID
from middleware.agent_network_designer.agent_network_definition_middleware import AgentNetworkDefinitionMiddleware

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


class TestAgentNetworkDefinitionMiddleware(IsolatedAsyncioTestCase):
    """
    Tests for AgentNetworkDefinitionMiddleware.

    Covers _resolve_hocon_path (synchronous path resolution) and the abefore_model hook's
    hand-off of a loaded network's metadata block (issue #1398). The designer is stateless:
    the client owns the network's top-level "metadata" block and sends it back under
    AGENT_NETWORK_METADATA. A network the hook loads from a HOCON file or an S3 reservation
    must therefore leave that network's sanitized block under the key, replacing whatever the
    client sent, while a definition passed directly, a failed load, or a load that yields no
    agents must not touch the key.
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
        :param contents: Text to write first, or None to leave the file absent
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
        A config load failure is returned to the client through abefore_model as an AIMessage and an end jump.
        """
        path: str = self._write_config_file("malformed.hocon", '{"tools": [{"name": "a")')
        sly_data: dict[str, Any] = {AGENT_NETWORK_HOCON_FILE: path}
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        self.assertIsNotNone(result)
        self.assertEqual(result["jump_to"], "end")
        self.assertEqual(result["messages"][0].content, middleware.error_message)

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

    async def test_hocon_to_config_reports_extension_and_read_errors(self) -> None:
        """
        A file whose extension is neither .hocon nor .json is the one genuinely unsupported case, and
        the message names the extensions that would work.
        """
        middleware: AgentNetworkDefinitionMiddleware = await self._assert_load_error(
            "wrong.txt", "tools = []", "Unsupported agent network config file"
        )
        self.assertIn(".hocon", middleware.error_message)
        self.assertIn(".json", middleware.error_message)

        await self._assert_load_error("absent.txt", None, "Unsupported agent network config file")
        await self._assert_load_error("network.HOCON", "tools = []", "Unsupported agent network config file")
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

    async def test_abefore_model_returns_neither_metadata_nor_name_when_tools_yield_no_agents(self) -> None:
        """
        A config whose "tools" list parses but yields no agents (every entry lacks a "name") is not
        an error, yet nothing is loaded: the hook proceeds normally, warns about the skipped entry,
        and sets neither the block nor the name nor the definition, so the config's block cannot
        become a stale block for whatever network the designer builds next.
        """
        config: dict[str, Any] = {"metadata": dict(STORED_METADATA), "tools": [{"instructions": "Nameless."}]}
        sly_data: dict[str, Any] = self._sly_data_for_file("nameless_network", config)
        middleware: AgentNetworkDefinitionMiddleware = AgentNetworkDefinitionMiddleware(sly_data=sly_data)

        with self.assertLogs(MIDDLEWARE_LOGGER, level="WARNING") as captured:
            result: dict[str, Any] | None = await middleware.abefore_model({}, None)

        # An empty definition is falsy, so the hook neither errors nor jumps: it proceeds to the model.
        self.assertIsNone(result)
        self.assertNotIn(AGENT_NETWORK_METADATA, sly_data)
        self.assertNotIn(AGENT_NETWORK_NAME, sly_data)
        self.assertNotIn(AGENT_NETWORK_DEFINITION, sly_data)
        # One skip warning per unusable entry, naming the file so an operator can fix it.
        self.assertEqual(len(captured.records), 1)
        self.assertIn("missing/invalid 'name'", captured.output[0])
        self.assertIn(sly_data[AGENT_NETWORK_HOCON_FILE], captured.output[0])
