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
Tests for AgentNetworkPersistenceMiddleware.aafter_agent: validation gating and the stateless
handling of the persisted metadata block (issue #1398) in both file mode and reservations mode,
including the compatibility fallback that reads the block of the network about to be overwritten
when the client sent no agent_network_metadata key at all.
"""

import json
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest import mock
from unittest.mock import AsyncMock

from langchain.messages import HumanMessage
from neuro_san.interfaces.reservation import Reservation
from neuro_san.interfaces.reservationist import Reservationist
from neuro_san.internals.reservations.reservation_util import ReservationUtil
from pyhocon import ConfigFactory

from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox
from coded_tools.agent_network_editor.globals import ProcessGlobals
from coded_tools.agent_network_editor.mcp_servers_load import McpServersLoad
from middleware.agent_network_designer.persistence import agent_network_persistence_middleware as persistence_module
from middleware.agent_network_designer.persistence.agent_network_persistence_middleware import (
    AgentNetworkPersistenceMiddleware,
)
from middleware.agent_network_designer.persistence.agent_network_persistor import AgentNetworkPersistor
from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import (
    FileSystemAgentNetworkPersistor,
)
from middleware.agent_network_designer.persistence.reservations_agent_network_persistor import (
    ReservationsAgentNetworkPersistor,
)

# Generated HOCON files include registries/aaosa.hocon and config/llm_config.hocon relative to the
# CWD, so parsing one back requires the repo root (four directories above this test module).
REPO_ROOT: Path = Path(__file__).resolve().parents[4]
NETWORK_NAME: str = "probe_net"
# Marker for _request's client_block meaning "leave agent_network_metadata out of sly_data". It is
# distinct from None, which _request sends as an explicit null: the middleware treats both alike
# (fallback read), and the tests must be able to show that for each of them separately.
NO_BLOCK: object = object()
# Logger names the persistor and the metadata block warn on; both are built from the class name.
PERSISTOR_LOGGER: str = "FileSystemAgentNetworkPersistor"
METADATA_LOGGER: str = "AgentNetworkMetadataBlock"
SAMPLE_QUERIES: list[str] = ["What can you do?", "Help me with X"]
FRESH_QUERIES: list[str] = ["Show me the newest report", "Book a meeting for Monday"]
# Fixed stamps handed out by the frozen clock, so blocks with server timestamps compare exactly.
NOW_STAMP: str = "2026-09-16T10:11:12+00:00"
LATER_STAMP: str = "2026-09-16T10:20:30+00:00"
# Every value the HOCON header used to hand-render, plus one (export_user) it never knew about,
# so a save proves the block is carried forward whole rather than field by field. This is the
# block a client sends back under sly_data["agent_network_metadata"] after an earlier save.
CLIENT_METADATA: dict[str, Any] = {
    "description": "A network the client sent back.",
    "tags": ["finance", "demo"],
    "sample_queries": list(SAMPLE_QUERIES),
    "date_created": "2025-01-02T03:04:05.000006+00:00",
    "export_user": "designer-bot",
}
# Each of these broke, or could break, a rendering that is not JSON: an embedded quote, a newline,
# three consecutive quotes (the old triple-quoted list terminator), HOCON substitution syntax,
# non-ASCII text, a tab, and the U+2028 line separator that str.splitlines() would split on.
AWKWARD_QUERIES: list[str] = [
    'He said "hi" to me',
    "line one\nline two",
    'three """ quotes',
    "${PRICE} $5 ${?OPT}",
    "café ☕",
    "tab\there",
    "sep\u2028arated",  # U+2028 LINE SEPARATOR, written as an escape so it is visible
]
# What the fake Reservation reports, echoed by the persistor into sly_data["agent_reservations"].
RESERVATION_ID: str = "probe_net-0123abcd"
LIFETIME_SECONDS: float = 3600.0
EXPIRATION_SECONDS: float = 1_800_000_000.0


class TestAgentNetworkPersistenceMiddleware(IsolatedAsyncioTestCase):  # pylint: disable=too-many-public-methods
    """
    End-to-end unit tests for AgentNetworkPersistenceMiddleware.aafter_agent.

    The designer is stateless: the client owns the metadata block and sends it back under
    sly_data["agent_network_metadata"], so most tests feed that block and check what the save
    wrote and what it handed back. The one bounded exception is the compatibility fallback for a
    client that sends no key (or an explicit null): the middleware then asks the persistor once
    for the block of the network it is about to overwrite. The fallback tests plant an existing
    file (or make a first save) and check that block is carried forward, that a client sending
    {} gets no read at all, and that a corrupt file costs one warning and is repaired by the save.
    File mode persists into a temp registries dir with every process-wide cache, MCP, toolbox and
    manifest dependency stubbed at the class-attribute level; reservations mode stubs
    ReservationUtil.wait_for_one. The saved HOCON is parsed back with pyhocon so the assertions
    are about what a reader of the file sees, not about the text.
    """

    def setUp(self) -> None:
        """
        Create a temp registries dir, point AGENT_MANIFEST_FILE at it, force file mode, and stub
        every dependency that would otherwise do manifest / MCP / toolbox I/O.
        """
        ProcessGlobals.clear_all_for_testing()
        self.addCleanup(ProcessGlobals.clear_all_for_testing)
        # mkdtemp + addCleanup(rmtree) rather than TemporaryDirectory(): pylint flags the latter with
        # consider-using-with (R1732) in setUp, and fail-under=10.0 makes any message a CI failure.
        temp_dir: str = tempfile.mkdtemp(prefix="and1398_")
        self.addCleanup(shutil.rmtree, temp_dir, True)
        self.registries_dir: str = os.path.join(temp_dir, "registries")
        os.makedirs(self.registries_dir)
        manifest_path: str = os.path.join(self.registries_dir, "manifest.hocon")
        with open(manifest_path, "w", encoding="utf-8") as manifest_file:
            manifest_file.write("{\n}\n")
        # AGENT_MANIFEST_FILE drives FileSystemAgentNetworkPersistor.output_path. Unsetting
        # PROGRESS_STYLE keeps the "internal" export path, which touches no ToolboxFactory, and
        # unsetting MAX_VALIDATION_ATTEMPTS keeps the default retry budget so the validation test
        # always gets a jump_to rather than a bail-out. patch.dict restores both on cleanup.
        self._start(mock.patch.dict(os.environ, {"AGENT_MANIFEST_FILE": manifest_path}))
        os.environ.pop("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", None)
        os.environ.pop("AGENT_NETWORK_DESIGNER_MAX_VALIDATION_ATTEMPTS", None)
        # WRITE_TO_FILE is an import-time constant; patch the module attribute the code reads at call time.
        self._start(mock.patch.object(persistence_module, "WRITE_TO_FILE", True))
        self._start(mock.patch.object(GetSubnetwork, "get_subnetwork_names", new=AsyncMock(return_value=[])))
        self._start(
            mock.patch.object(GetMcpTool, "get_mcp_servers_load", new=AsyncMock(return_value=McpServersLoad([], True)))
        )
        self._start(mock.patch.object(GetMcpTool, "get_mcp_servers", new=AsyncMock(return_value=[])))
        self._start(mock.patch.object(GetToolbox, "get_toolbox_info", new=AsyncMock(return_value={})))

    def _start(self, patcher: Any) -> None:
        """
        Start a patcher and register its stop as cleanup.

        :param patcher: A unittest.mock patcher object
        """
        patcher.start()
        self.addCleanup(patcher.stop)

    def _freeze_clock(self, *stamps: str) -> mock.MagicMock:
        """
        Replace AgentNetworkPersistenceMiddleware._utc_now_iso for the rest of the test with a mock
        that hands out the given stamps in order, one per call.

        The middleware reads the clock once per file-mode save and stamp_file_dates() uses the one
        value for both dates, so freezing it makes blocks with server timestamps comparable with
        assertEqual.

        :param stamps: The timestamps to return, one per call to _utc_now_iso
        :return: The mock, so a test can count how many times the clock was read
        """
        clock: mock.MagicMock = mock.MagicMock(side_effect=list(stamps))
        self._start(mock.patch.object(AgentNetworkPersistenceMiddleware, "_utc_now_iso", new=clock))
        return clock

    def _enter_reservations_mode(self) -> AsyncMock:
        """
        Switch the middleware to reservations mode and stub the neuro-san deployment call.

        The fake Reservation reports RESERVATION_ID / LIFETIME_SECONDS / EXPIRATION_SECONDS, which
        ReservationsAgentNetworkPersistor echoes into sly_data["agent_reservations"].

        :return: The AsyncMock standing in for ReservationUtil.wait_for_one, so a test can inspect
                the agent_spec it was awaited with (positional argument 1) and the prefix (argument 3)
        """
        self._start(mock.patch.object(persistence_module, "WRITE_TO_FILE", False))
        fake_reservation: Reservation = mock.create_autospec(Reservation, instance=True)
        fake_reservation.get_reservation_id.return_value = RESERVATION_ID
        fake_reservation.get_lifetime_in_seconds.return_value = LIFETIME_SECONDS
        fake_reservation.get_expiration_time_in_seconds.return_value = EXPIRATION_SECONDS
        wait_for_one: AsyncMock = AsyncMock(return_value=(fake_reservation, None))
        self._start(mock.patch.object(ReservationUtil, "wait_for_one", new=wait_for_one))
        return wait_for_one

    @staticmethod
    def _network_def() -> dict[str, Any]:
        """
        Build a two-agent definition that passes every validator without toolbox/MCP/subnetwork lookups.

        :return: The agent network definition dict
        """
        return {
            "front_man": {"description": "Routes requests.", "instructions": "Delegate.", "tools": ["helper"]},
            "helper": {"description": "Answers.", "instructions": "Answer.", "tools": []},
        }

    @staticmethod
    def _request(
        queries: list[str] | None = None,
        skip_designer: bool | None = None,
        client_block: Any = NO_BLOCK,
        network_def: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build the sly_data of one designer request for NETWORK_NAME.

        Keys are only set when a value is given, because the middleware distinguishes an absent
        key from a falsy one (e.g. skip_designer absent vs False, queries absent vs []). For
        agent_network_metadata the line that matters runs between absent-or-None (fallback read)
        and any other value (client-owned), so its "leave the key out" marker is the NO_BLOCK
        sentinel rather than None, which lets a test send an explicit null.

        :param queries: Value for agent_network_queries, or None to leave the key out
        :param skip_designer: Value for skip_designer, or None to leave the key out
        :param client_block: Value for agent_network_metadata, the block the client sends back from
                an earlier save (any type, so a test can send a non-dict or an explicit None), or
                NO_BLOCK to leave the key out
        :param network_def: The agent network definition; defaults to _network_def()
        :return: The sly_data dict
        """
        sly_data: dict[str, Any] = {
            "agent_network_definition": network_def
            if network_def is not None
            else TestAgentNetworkPersistenceMiddleware._network_def(),
            "agent_network_name": NETWORK_NAME,
        }
        if queries is not None:
            sly_data["agent_network_queries"] = queries
        if skip_designer is not None:
            sly_data["skip_designer"] = skip_designer
        if client_block is not NO_BLOCK:
            sly_data["agent_network_metadata"] = client_block
        return sly_data

    @staticmethod
    async def _save(sly_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Run one aafter_agent call of a fresh middleware over the given sly_data.

        A fresh instance per call mirrors the stateless contract: nothing but sly_data carries
        over from one request to the next.

        :param sly_data: The request's sly_data, mutated in place by the middleware
        :return: What aafter_agent returned: None on success, a jump_to dict on validation failure
        """
        middleware: AgentNetworkPersistenceMiddleware = AgentNetworkPersistenceMiddleware(Reservationist(), sly_data)
        return await middleware.aafter_agent({}, None)

    def _generated_path(self) -> Path:
        """
        Locate the file the persistor writes NETWORK_NAME to.

        :return: <registries_dir>/generated/<NETWORK_NAME>.hocon
        """
        return Path(self.registries_dir) / "generated" / f"{NETWORK_NAME}.hocon"

    def _read_metadata(self) -> dict[str, Any]:
        """
        Parse the persisted HOCON (from the repo root so its includes resolve) and return its metadata block.

        :return: The metadata block as plain dicts and lists
        """
        text: str = self._generated_path().read_text(encoding="utf-8")
        cwd: str = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            return self._plain(ConfigFactory.parse_string(text)["metadata"])
        finally:
            os.chdir(cwd)

    @staticmethod
    def _plain(value: Any) -> Any:
        """
        Convert pyhocon's ConfigTree / ConfigList containers into plain dicts and lists, recursively.

        Both are dict / list subclasses, so equality would already hold, but plain containers make
        assertEqual's failure diff readable.

        :param value: A parsed HOCON value
        :return: The same value built from plain dicts, lists and scalars
        """
        if isinstance(value, dict):
            plain_dict: dict[str, Any] = {}
            for key, item in value.items():
                plain_dict[key] = TestAgentNetworkPersistenceMiddleware._plain(item)
            return plain_dict
        if isinstance(value, list):
            plain_list: list[Any] = []
            for item in value:
                plain_list.append(TestAgentNetworkPersistenceMiddleware._plain(item))
            return plain_list
        return value

    def _assert_iso_timestamp(self, value: Any) -> None:
        """
        Assert a value is the UTC ISO-8601 string AgentNetworkPersistenceMiddleware._utc_now_iso produces.

        :param value: The timestamp value to check
        """
        self.assertIsInstance(value, str)
        stamp: datetime = datetime.fromisoformat(value)
        self.assertIsNotNone(stamp.tzinfo)
        self.assertEqual(stamp.utcoffset(), timedelta(0))

    def _write_existing_network(self, block: dict[str, Any]) -> Path:
        """
        Plant a network file carrying the given metadata block where the persistor looks for NETWORK_NAME.

        The file is include-free JSON syntax (valid HOCON), so the fallback read parses it from any
        CWD; a file the middleware wrote includes registries/aaosa.hocon relative to the CWD instead,
        see _save_from_repo_root. The rest of the config is a token tools list, since
        async_restore_metadata only looks at "metadata".

        :param block: The metadata block to write under the top-level "metadata" key
        :return: The path written, i.e. _generated_path()
        """
        path: Path = self._generated_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        config: dict[str, Any] = {"metadata": block, "tools": [{"name": "front_man"}]}
        path.write_text(json.dumps(config, indent=4), encoding="utf-8")
        return path

    @staticmethod
    async def _save_from_repo_root(sly_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Run _save with the repo root as CWD, for a save whose fallback read must parse a file the
        middleware itself wrote earlier.

        Generated files include registries/aaosa.hocon and config/llm_config.hocon relative to the
        process CWD (the server runs from the project root), so the fallback read of such a file
        succeeds only from there. The chdir keeps the test independent of where pytest was launched,
        as _read_metadata does for its own parse.

        :param sly_data: The request's sly_data, mutated in place by the middleware
        :return: What aafter_agent returned, see _save
        """
        cwd: str = os.getcwd()
        os.chdir(REPO_ROOT)
        try:
            return await TestAgentNetworkPersistenceMiddleware._save(sly_data)
        finally:
            os.chdir(cwd)

    def _spy_on_restore(self, persistor_class: type[AgentNetworkPersistor]) -> Any:
        """
        Wrap persistor_class.async_restore_metadata for the rest of the test so it still runs its
        real body but records its awaits.

        autospec keeps the descriptor behaviour, so the instance the middleware created is bound as
        usual and shows up as await_args.args[0]; the network name is await_args.args[1].

        :param persistor_class: FileSystemAgentNetworkPersistor or ReservationsAgentNetworkPersistor
        :return: The spy, an autospecced async function exposing assert_awaited_once and await_args
        """
        original: Any = persistor_class.async_restore_metadata
        patcher: Any = mock.patch.object(
            persistor_class, "async_restore_metadata", autospec=True, side_effect=original
        )
        spy: Any = patcher.start()
        self.addCleanup(patcher.stop)
        return spy

    @staticmethod
    def _probe_restore(path: Path, seen: list[bool], file_reference: str) -> dict[str, Any]:
        """
        Stand-in body for async_restore_metadata that records whether the network file existed at
        the moment of the fallback read, then answers a block with a description only.

        Bound to a path and a list with functools.partial and installed as an AsyncMock side_effect:
        a plain callable there is called on each await and its value is what the await yields.

        :param path: The file the persistor would read, i.e. _generated_path()
        :param seen: Receives one bool per read: True when the file already existed at that moment
        :param file_reference: The network name the middleware asked for; passed through by the mock
        :return: {"description": "old"}, so a save that built on the read shows it in the block
        """
        _ = file_reference
        seen.append(path.exists())
        return {"description": "old"}

    # ------------------------------------------------------------------ file mode

    async def test_designer_save_writes_queries_and_both_timestamps(self) -> None:
        """
        A designer run in file mode (agent_network_queries set, no client block) writes a block of
        exactly sample_queries, date_created and date_modified, the two dates equal on a first save
        because one clock reading stamps both; the block handed back under
        sly_data["agent_network_metadata"] is what the file says, and the HOCON text handed back is
        the file content.
        """
        sly_data: dict[str, Any] = self._request(queries=list(SAMPLE_QUERIES))
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        block: dict[str, Any] = self._read_metadata()
        self.assertEqual(set(block), {"sample_queries", "date_created", "date_modified"})
        self.assertEqual(block["sample_queries"], SAMPLE_QUERIES)
        self._assert_iso_timestamp(block["date_created"])
        self.assertEqual(block["date_modified"], block["date_created"])
        self.assertEqual(sly_data["agent_network_metadata"], block)
        self.assertEqual(sly_data["agent_network_hocon_text"], self._generated_path().read_text(encoding="utf-8"))

    async def test_skip_designer_save_keeps_client_block_and_stamps_date_modified(self) -> None:
        """
        Issue #1398: a skip_designer save with no agent_network_queries writes the block the client
        sent back, key for key, plus a fresh date_modified; the client's date_created is kept.
        """
        self._freeze_clock(NOW_STAMP)
        sly_data: dict[str, Any] = self._request(skip_designer=True, client_block=deepcopy(CLIENT_METADATA))
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        expected: dict[str, Any] = deepcopy(CLIENT_METADATA)
        expected["date_modified"] = NOW_STAMP
        block: dict[str, Any] = self._read_metadata()
        self.assertEqual(block, expected)
        self.assertEqual(block["date_created"], CLIENT_METADATA["date_created"])
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_fresh_queries_replace_only_sample_queries(self) -> None:
        """
        A designer save over a client block replaces sample_queries and stamps date_modified;
        description, tags, export_user and date_created are written exactly as received.
        """
        self._freeze_clock(NOW_STAMP)
        sly_data: dict[str, Any] = self._request(queries=list(FRESH_QUERIES), client_block=deepcopy(CLIENT_METADATA))
        await self._save(sly_data)
        expected: dict[str, Any] = deepcopy(CLIENT_METADATA)
        expected["sample_queries"] = list(FRESH_QUERIES)
        expected["date_modified"] = NOW_STAMP
        block: dict[str, Any] = self._read_metadata()
        self.assertEqual(block, expected)
        self.assertEqual(block["description"], CLIENT_METADATA["description"])
        self.assertEqual(block["tags"], CLIENT_METADATA["tags"])
        self.assertEqual(block["date_created"], CLIENT_METADATA["date_created"])
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_save_without_block_or_queries_writes_only_timestamps(self) -> None:
        """
        With no client block and no queries the block is exactly {date_created, date_modified};
        no sample_queries key is invented.
        """
        self._freeze_clock(NOW_STAMP)
        sly_data: dict[str, Any] = self._request(skip_designer=True)
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        block: dict[str, Any] = self._read_metadata()
        self.assertEqual(block, {"date_created": NOW_STAMP, "date_modified": NOW_STAMP})
        self.assertNotIn("sample_queries", block)
        self.assertEqual(sly_data["agent_network_metadata"], block)

    async def test_storage_owned_and_none_valued_keys_are_stripped(self) -> None:
        """
        A client block carrying neuro-san's storage keys (reservation, stored_at) and a None-valued
        key loses all three, both in the file and in the block handed back.
        """
        self._freeze_clock(NOW_STAMP)
        client_block: dict[str, Any] = {
            "description": "Came back from a reservation.",
            "sample_queries": list(SAMPLE_QUERIES),
            "reservation": {"reservation_id": "old-reservation"},
            "stored_at": "2024-06-07T08:09:11+00:00",
            "owner": None,
        }
        sly_data: dict[str, Any] = self._request(skip_designer=True, client_block=client_block)
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        expected: dict[str, Any] = {
            "description": "Came back from a reservation.",
            "sample_queries": list(SAMPLE_QUERIES),
            "date_created": NOW_STAMP,
            "date_modified": NOW_STAMP,
        }
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_non_dict_client_block_owns_an_empty_block_warns_and_reads_nothing(self) -> None:
        """
        A client block that is not a dict (here a str) is not "no block": the persistor is never asked
        for the existing file's block, the str is ignored with one WARNING naming the sly_data key, the
        save succeeds, and the block is exactly {date_created, date_modified} in the file and in
        sly_data, replacing the rich block the file held.
        """
        self._freeze_clock(NOW_STAMP)
        self._write_existing_network(deepcopy(CLIENT_METADATA))
        restore: AsyncMock = AsyncMock(return_value={"description": "must not be used"})
        self._start(mock.patch.object(FileSystemAgentNetworkPersistor, "async_restore_metadata", new=restore))
        sly_data: dict[str, Any] = self._request(skip_designer=True, client_block="not a block")
        with self.assertLogs(METADATA_LOGGER, level="WARNING") as captured:
            result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        restore.assert_not_awaited()
        self.assertEqual(len(captured.records), 1)
        message: str = captured.records[0].getMessage()
        self.assertIn("str", message)
        self.assertIn("agent_network_metadata", message)
        expected: dict[str, Any] = {"date_created": NOW_STAMP, "date_modified": NOW_STAMP}
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_failed_persist_hands_back_no_freshly_stamped_block(self) -> None:
        """
        When the persistor raises, the error propagates and sly_data still holds the block exactly as the
        client sent it and no HOCON text: both are published only after the save they describe happened,
        so the client never learns a date_modified for a write that did not take place.
        """
        self._freeze_clock(NOW_STAMP)
        failing_persist: AsyncMock = AsyncMock(side_effect=OSError("simulated disk failure"))
        self._start(mock.patch.object(FileSystemAgentNetworkPersistor, "async_persist", new=failing_persist))
        sly_data: dict[str, Any] = self._request(skip_designer=True, client_block=deepcopy(CLIENT_METADATA))

        with self.assertRaises(OSError):
            await self._save(sly_data)

        failing_persist.assert_awaited_once()
        self.assertEqual(sly_data["agent_network_metadata"], CLIENT_METADATA)
        self.assertNotIn("date_modified", sly_data["agent_network_metadata"])
        self.assertNotIn("agent_network_hocon_text", sly_data)

    async def test_name_that_escapes_the_generated_directory_is_refused_before_anything_is_touched(self) -> None:
        """
        A client-supplied network name that climbs out of the generated directory fails the save with
        ValueError before the fallback read or the write: nothing appears in the registries directory above,
        and neither a block nor HOCON text is handed back.
        """
        self._freeze_clock(NOW_STAMP)
        sly_data: dict[str, Any] = self._request(skip_designer=True)
        sly_data["agent_network_name"] = "../escaped"

        with self.assertRaises(ValueError):
            await self._save(sly_data)

        self.assertFalse(Path(self.registries_dir, "escaped.hocon").exists())
        self.assertNotIn("agent_network_metadata", sly_data)
        self.assertNotIn("agent_network_hocon_text", sly_data)

    async def test_designer_turn_without_queries_keeps_client_sample_queries(self) -> None:
        """
        A designer turn that skipped the query generator (skip_designer absent, no
        agent_network_queries) keeps the client's sample_queries and the rest of its block.
        """
        self._freeze_clock(NOW_STAMP)
        sly_data: dict[str, Any] = self._request(client_block=deepcopy(CLIENT_METADATA))
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        expected: dict[str, Any] = deepcopy(CLIENT_METADATA)
        expected["date_modified"] = NOW_STAMP
        block: dict[str, Any] = self._read_metadata()
        self.assertEqual(block["sample_queries"], SAMPLE_QUERIES)
        self.assertEqual(block, expected)

    async def test_validation_failure_jumps_to_model_without_writing(self) -> None:
        """
        An agent with empty instructions fails the instructions validator: aafter_agent returns a
        jump_to "model" with a HumanMessage naming the error, flips skip_designer to False so the
        definition middleware does not bounce straight back, writes nothing, and leaves the client's
        block in sly_data untouched (same object, same content).
        """
        network_def: dict[str, Any] = self._network_def()
        network_def["front_man"]["instructions"] = ""
        client_block: dict[str, Any] = deepcopy(CLIENT_METADATA)
        before: dict[str, Any] = deepcopy(client_block)
        sly_data: dict[str, Any] = self._request(
            skip_designer=True, client_block=client_block, network_def=network_def
        )
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["jump_to"], "model")
        self.assertEqual(len(result["messages"]), 1)
        self.assertIsInstance(result["messages"][0], HumanMessage)
        self.assertIn("front_man 'instructions' cannot be empty.", result["messages"][0].content)
        self.assertIn("agent_network_instructions_editor", result["messages"][0].content)
        self.assertIs(sly_data["skip_designer"], False)
        self.assertFalse(self._generated_path().exists())
        self.assertNotIn("agent_network_hocon_text", sly_data)
        self.assertIs(sly_data["agent_network_metadata"], client_block)
        self.assertEqual(client_block, before)

    async def test_second_save_advances_date_modified_and_keeps_date_created(self) -> None:
        """
        Two saves in file mode, the second sending back the block the first returned: date_created
        keeps the first stamp, date_modified takes the second, and the clock is read exactly once
        per save (the assemblers stamp nothing of their own).
        """
        clock: mock.MagicMock = self._freeze_clock(NOW_STAMP, LATER_STAMP)
        first: dict[str, Any] = self._request(skip_designer=True)
        await self._save(first)
        self.assertEqual(first["agent_network_metadata"], {"date_created": NOW_STAMP, "date_modified": NOW_STAMP})
        # The client sends the block back with the next request, as the stateless contract requires.
        second: dict[str, Any] = self._request(skip_designer=True, client_block=first["agent_network_metadata"])
        await self._save(second)
        expected: dict[str, Any] = {"date_created": NOW_STAMP, "date_modified": LATER_STAMP}
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(second["agent_network_metadata"], expected)
        self.assertEqual(clock.call_count, 2)

    async def test_awkward_queries_round_trip_through_the_file(self) -> None:
        """
        Queries with an embedded quote, a newline, three consecutive quotes, HOCON substitution
        syntax, non-ASCII text, a tab and U+2028 parse back from the written file unchanged.
        """
        await self._save(self._request(queries=list(AWKWARD_QUERIES)))
        self.assertEqual(self._read_metadata()["sample_queries"], AWKWARD_QUERIES)

    async def test_returned_block_is_a_copy_and_input_block_is_not_mutated(self) -> None:
        """
        The block handed back under sly_data["agent_network_metadata"] is a new object, deep-copied
        down to its nested containers, and the client's input block is deep-equal to what it was.
        """
        self._freeze_clock(NOW_STAMP)
        client_block: dict[str, Any] = {
            "description": "Sent back by the client.",
            "tags": ["x"],
            "sample_queries": ["old query"],
            "date_created": "2024-06-07T08:09:10+00:00",
        }
        before: dict[str, Any] = deepcopy(client_block)
        sly_data: dict[str, Any] = self._request(queries=list(FRESH_QUERIES), client_block=client_block)
        await self._save(sly_data)
        returned: dict[str, Any] = sly_data["agent_network_metadata"]
        self.assertIsNot(returned, client_block)
        self.assertIsNot(returned["tags"], client_block["tags"])
        self.assertEqual(client_block, before)
        expected: dict[str, Any] = deepcopy(before)
        expected["sample_queries"] = list(FRESH_QUERIES)
        expected["date_modified"] = NOW_STAMP
        self.assertEqual(returned, expected)
        self.assertEqual(self._read_metadata(), expected)

    # ------------------------------------------------------------------ reservations mode

    async def test_reservations_mode_deploys_sanitized_block_without_timestamps(self) -> None:
        """
        In reservations mode the deployable spec handed to ReservationUtil.wait_for_one carries the
        client's block with the storage-owned keys stripped and this turn's queries overlaid, gets no
        studio timestamps, sly_data["agent_reservations"] describes the reservation, the block handed
        back equals the spec's, and no file is written. The HOCON text handed back for download is the
        one place a date appears: a date_created, never a date_modified.
        """
        wait_for_one: AsyncMock = self._enter_reservations_mode()
        client_block: dict[str, Any] = {
            "description": "Loaded from a reservation.",
            "tags": ["finance"],
            "sample_queries": list(SAMPLE_QUERIES),
            # Written by neuro-san's reservation storage; must not be carried into the next save.
            "reservation": {"reservation_id": "old-reservation"},
            "stored_at": "2024-06-07T08:09:11+00:00",
        }
        sly_data: dict[str, Any] = self._request(queries=list(FRESH_QUERIES), client_block=client_block)
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        wait_for_one.assert_awaited_once()
        agent_spec: dict[str, Any] = wait_for_one.await_args.args[1]
        expected: dict[str, Any] = {
            "description": "Loaded from a reservation.",
            "tags": ["finance"],
            "sample_queries": list(FRESH_QUERIES),
        }
        self.assertEqual(agent_spec["metadata"], expected)
        self.assertNotIn("date_created", agent_spec["metadata"])
        self.assertNotIn("date_modified", agent_spec["metadata"])
        self.assertEqual(wait_for_one.await_args.args[3], NETWORK_NAME)
        self.assertEqual(
            sly_data["agent_reservations"],
            [
                {
                    "reservation_id": RESERVATION_ID,
                    "lifetime_in_seconds": LIFETIME_SECONDS,
                    "expiration_time_in_seconds": EXPIRATION_SECONDS,
                }
            ],
        )
        self.assertEqual(sly_data["agent_network_metadata"], agent_spec["metadata"])
        self.assertFalse(self._generated_path().exists())
        self.assertIn('"date_created"', sly_data["agent_network_hocon_text"])
        self.assertNotIn("date_modified", sly_data["agent_network_hocon_text"])

    async def test_reservations_mode_without_block_or_queries_omits_metadata_key(self) -> None:
        """
        With no client block and no queries the deployable spec has no "metadata" key at all, the
        client is handed an empty block, and the downloadable HOCON text still carries a date_created.
        """
        wait_for_one: AsyncMock = self._enter_reservations_mode()
        sly_data: dict[str, Any] = self._request(skip_designer=True)
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        wait_for_one.assert_awaited_once()
        agent_spec: dict[str, Any] = wait_for_one.await_args.args[1]
        self.assertNotIn("metadata", agent_spec)
        self.assertEqual(sly_data["agent_network_metadata"], {})
        self.assertIn("agent_reservations", sly_data)
        self.assertIn('"date_created"', sly_data["agent_network_hocon_text"])

    async def test_reservations_mode_passes_client_dates_through_unchanged(self) -> None:
        """
        Dates the client sent (here date_created) pass through to the deployable spec verbatim and
        nothing is stamped alongside them: the block equals the client's exactly.
        """
        wait_for_one: AsyncMock = self._enter_reservations_mode()
        sly_data: dict[str, Any] = self._request(skip_designer=True, client_block=deepcopy(CLIENT_METADATA))
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        agent_spec: dict[str, Any] = wait_for_one.await_args.args[1]
        self.assertEqual(agent_spec["metadata"], CLIENT_METADATA)
        self.assertNotIn("date_modified", agent_spec["metadata"])
        self.assertEqual(sly_data["agent_network_metadata"], CLIENT_METADATA)

    # ------------------------------------------------------------------ absent-key fallback

    async def test_absent_key_carries_forward_the_block_of_the_file_being_overwritten(self) -> None:
        """
        A client that sends no agent_network_metadata key at all (nsflow's manual save as of 0.7.1)
        over a network the middleware itself saved earlier keeps that file's whole block: description,
        tags, sample_queries, export_user and date_created survive, date_modified takes this save's
        stamp, the block handed back is what the file now says, and reading the middleware's own
        HOCON output raises no warning on either logger.
        """
        clock: mock.MagicMock = self._freeze_clock(NOW_STAMP, LATER_STAMP)
        first: dict[str, Any] = self._request(skip_designer=True, client_block=deepcopy(CLIENT_METADATA))
        await self._save(first)
        self.assertEqual(self._read_metadata()["date_modified"], NOW_STAMP)
        # The next client says nothing about the block: no key, no queries.
        second: dict[str, Any] = self._request(skip_designer=True)
        self.assertNotIn("agent_network_metadata", second)
        with self.assertNoLogs(PERSISTOR_LOGGER, level="WARNING"), self.assertNoLogs(METADATA_LOGGER, level="WARNING"):
            result: dict[str, Any] | None = await self._save_from_repo_root(second)
        self.assertIsNone(result)
        expected: dict[str, Any] = deepcopy(CLIENT_METADATA)
        expected["date_modified"] = LATER_STAMP
        block: dict[str, Any] = self._read_metadata()
        self.assertEqual(block, expected)
        self.assertEqual(block["date_created"], CLIENT_METADATA["date_created"])
        self.assertEqual(block["sample_queries"], SAMPLE_QUERIES)
        self.assertEqual(block["export_user"], CLIENT_METADATA["export_user"])
        self.assertEqual(second["agent_network_metadata"], block)
        self.assertEqual(clock.call_count, 2)

    async def test_absent_key_with_fresh_queries_replaces_only_sample_queries_of_existing_file(self) -> None:
        """
        A designer run (agent_network_queries set) for a client that sends no key replaces only
        sample_queries in the existing file's block: description, tags, export_user and date_created
        are carried forward as they were, and date_modified is stamped.
        """
        self._freeze_clock(NOW_STAMP)
        self._write_existing_network(deepcopy(CLIENT_METADATA))
        sly_data: dict[str, Any] = self._request(queries=list(FRESH_QUERIES))
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        expected: dict[str, Any] = deepcopy(CLIENT_METADATA)
        expected["sample_queries"] = list(FRESH_QUERIES)
        expected["date_modified"] = NOW_STAMP
        block: dict[str, Any] = self._read_metadata()
        self.assertEqual(block, expected)
        self.assertEqual(block["description"], CLIENT_METADATA["description"])
        self.assertEqual(block["tags"], CLIENT_METADATA["tags"])
        self.assertEqual(block["export_user"], CLIENT_METADATA["export_user"])
        self.assertEqual(block["date_created"], CLIENT_METADATA["date_created"])
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_empty_client_block_owns_the_block_and_nothing_is_read(self) -> None:
        """
        A client that sends agent_network_metadata as {} owns the block: the persistor is never asked
        for the existing file's block (the stand-in would have supplied a description if it were), and
        the rich block in the file is replaced by exactly {date_created, date_modified}.
        """
        self._freeze_clock(NOW_STAMP)
        self._write_existing_network(deepcopy(CLIENT_METADATA))
        self.assertEqual(self._read_metadata(), CLIENT_METADATA)
        restore: AsyncMock = AsyncMock(return_value={"description": "must not be used"})
        self._start(mock.patch.object(FileSystemAgentNetworkPersistor, "async_restore_metadata", new=restore))
        sly_data: dict[str, Any] = self._request(skip_designer=True, client_block={})
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        restore.assert_not_awaited()
        expected: dict[str, Any] = {"date_created": NOW_STAMP, "date_modified": NOW_STAMP}
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_explicit_null_client_block_falls_back_like_an_absent_key(self) -> None:
        """
        A client that sends agent_network_metadata as an explicit null is treated like one that sent
        no key: the persistor is asked once, by network name, for the existing file's block, and that
        block is kept with date_modified stamped.
        """
        self._freeze_clock(NOW_STAMP)
        self._write_existing_network(deepcopy(CLIENT_METADATA))
        spy: Any = self._spy_on_restore(FileSystemAgentNetworkPersistor)
        sly_data: dict[str, Any] = self._request(skip_designer=True, client_block=None)
        self.assertIn("agent_network_metadata", sly_data)
        self.assertIsNone(sly_data["agent_network_metadata"])
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        spy.assert_awaited_once()
        self.assertEqual(spy.await_args.args[1], NETWORK_NAME)
        expected: dict[str, Any] = deepcopy(CLIENT_METADATA)
        expected["date_modified"] = NOW_STAMP
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_absent_key_with_unparseable_existing_file_warns_once_and_repairs_it(self) -> None:
        """
        When the existing file cannot be parsed, the fallback logs exactly one WARNING on the
        persistor's logger naming the file (and none on the metadata logger), the save still succeeds
        with a block of exactly {date_created, date_modified}, and the file parses again afterwards.
        """
        self._freeze_clock(NOW_STAMP)
        path: Path = self._generated_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("metadata = { unterminated", encoding="utf-8")
        sly_data: dict[str, Any] = self._request(skip_designer=True)
        with (
            self.assertNoLogs(METADATA_LOGGER, level="WARNING"),
            self.assertLogs(PERSISTOR_LOGGER, level="WARNING") as captured,
        ):
            result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        message: str = captured.records[0].getMessage()
        self.assertIn("Could not read existing agent network", message)
        self.assertIn(str(path), message)
        expected: dict[str, Any] = {"date_created": NOW_STAMP, "date_modified": NOW_STAMP}
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_absent_key_on_first_save_asks_once_and_warns_nothing(self) -> None:
        """
        On a first save (no file yet) for a client that sends no key, the persistor is asked once, by
        network name, and finds nothing, which is not worth a warning on either logger; the block is
        exactly {date_created, date_modified}. Complements
        test_save_without_block_or_queries_writes_only_timestamps, which does not watch the read.
        """
        self._freeze_clock(NOW_STAMP)
        self.assertFalse(self._generated_path().exists())
        spy: Any = self._spy_on_restore(FileSystemAgentNetworkPersistor)
        sly_data: dict[str, Any] = self._request(skip_designer=True)
        with self.assertNoLogs(PERSISTOR_LOGGER, level="WARNING"), self.assertNoLogs(METADATA_LOGGER, level="WARNING"):
            result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        spy.assert_awaited_once()
        self.assertEqual(spy.await_args.args[1], NETWORK_NAME)
        expected: dict[str, Any] = {"date_created": NOW_STAMP, "date_modified": NOW_STAMP}
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(sly_data["agent_network_metadata"], expected)

    async def test_reservations_mode_with_absent_key_reads_no_file(self) -> None:
        """
        In reservations mode a client that sends no key gets the pre-#1398 result, not a file's block:
        the reservations persistor is asked once and answers None (there is no previous reservation to
        look up), FileSystemAgentNetworkPersistor.async_restore_metadata is never awaited even though a
        generated file of that name exists, the deployed spec has no "metadata" key, the client is
        handed an empty block, and the file is left exactly as it was.
        """
        wait_for_one: AsyncMock = self._enter_reservations_mode()
        path: Path = self._write_existing_network(deepcopy(CLIENT_METADATA))
        before: str = path.read_text(encoding="utf-8")
        file_restore: AsyncMock = AsyncMock(return_value={"description": "must not be used"})
        self._start(mock.patch.object(FileSystemAgentNetworkPersistor, "async_restore_metadata", new=file_restore))
        spy: Any = self._spy_on_restore(ReservationsAgentNetworkPersistor)
        sly_data: dict[str, Any] = self._request(skip_designer=True)
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        file_restore.assert_not_awaited()
        spy.assert_awaited_once()
        self.assertEqual(spy.await_args.args[1], NETWORK_NAME)
        wait_for_one.assert_awaited_once()
        agent_spec: dict[str, Any] = wait_for_one.await_args.args[1]
        self.assertNotIn("metadata", agent_spec)
        self.assertEqual(sly_data["agent_network_metadata"], {})
        self.assertIn("agent_reservations", sly_data)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    async def test_fallback_reads_once_before_the_write_and_builds_on_the_result(self) -> None:
        """
        The fallback asks the persistor exactly once per save, by network name, before anything is
        written (the stand-in sees no file at read time on a first save), and what it answers is the
        base of the saved block: the description it supplied is written alongside this turn's queries
        and the two stamps, handed back to the client, and the HOCON text handed back is the file.
        """
        self._freeze_clock(NOW_STAMP)
        seen: list[bool] = []
        restore: AsyncMock = AsyncMock(side_effect=partial(self._probe_restore, self._generated_path(), seen))
        self._start(mock.patch.object(FileSystemAgentNetworkPersistor, "async_restore_metadata", new=restore))
        sly_data: dict[str, Any] = self._request(queries=list(FRESH_QUERIES))
        result: dict[str, Any] | None = await self._save(sly_data)
        self.assertIsNone(result)
        restore.assert_awaited_once_with(NETWORK_NAME)
        # One read, and the file did not exist yet when it happened: the read precedes the write.
        self.assertEqual(seen, [False])
        self.assertTrue(self._generated_path().exists())
        expected: dict[str, Any] = {
            "description": "old",
            "sample_queries": list(FRESH_QUERIES),
            "date_created": NOW_STAMP,
            "date_modified": NOW_STAMP,
        }
        self.assertEqual(self._read_metadata(), expected)
        self.assertEqual(sly_data["agent_network_metadata"], expected)
        self.assertEqual(sly_data["agent_network_hocon_text"], self._generated_path().read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ clock

    def test_utc_now_iso_is_a_timezone_aware_utc_stamp(self) -> None:
        """
        The unpatched _utc_now_iso() hands out what the HOCON header always held for date_created: a
        string datetime.fromisoformat parses, carrying an explicit UTC offset (aware, never a naive
        local time, and spelled "+00:00" rather than "Z" so a reader comparing files sees one form),
        and two successive reads compare as non-decreasing plain strings.
        """
        first: str = AgentNetworkPersistenceMiddleware._utc_now_iso()  # pylint: disable=protected-access
        second: str = AgentNetworkPersistenceMiddleware._utc_now_iso()  # pylint: disable=protected-access

        self._assert_iso_timestamp(first)
        stamp: datetime = datetime.fromisoformat(first)
        self.assertEqual(stamp.utcoffset(), timedelta(0))
        self.assertTrue(first.endswith("+00:00"))
        # isoformat() keeps a fixed field order and zero-pads every field, so string order is time order.
        self.assertLessEqual(first, second)
