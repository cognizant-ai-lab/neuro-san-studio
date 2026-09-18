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

"""Tests for FileSystemAgentNetworkPersistor: manifest parsing, encodings, file paths and metadata restore."""

import json
import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import (
    FileSystemAgentNetworkPersistor,
)

# Name of the logger the persistor warns on; FileSystemAgentNetworkPersistor.__init__ builds it
# from the class name, so this is what assertLogs/assertNoLogs must listen to.
LOGGER_NAME: str = "FileSystemAgentNetworkPersistor"

# A metadata block with one value of each type the restorer must hand back as a plain Python
# type. "contact" stands in for any key a user added by hand: #1398 is about such keys surviving.
SAMPLE_METADATA: dict[str, Any] = {
    "date_created": "2026-01-01T00:00:00Z",
    "sample_queries": ["First sample query", "Second sample query"],
    "contact": {"team": "platform"},
}

# The metadata block of ROUND_TRIP_HOCON, spelled as the restorer should return it.
ROUND_TRIP_METADATA: dict[str, Any] = {
    "date_created": "2026-02-02T00:00:00Z",
    "sample_queries": ["Round trip query"],
}

# Minimal network in HOCON (not JSON) syntax with no include statements, so it parses from any
# CWD. Generated files include registries/aaosa.hocon relative to the CWD, which this avoids.
ROUND_TRIP_HOCON: str = (
    "metadata = {\n"
    '    date_created = "2026-02-02T00:00:00Z"\n'
    '    sample_queries = ["Round trip query"]\n'
    "}\n"
    "tools = [\n"
    '    { name = "frontman" }\n'
    "]\n"
)


class TestFileSystemAgentNetworkPersistor(IsolatedAsyncioTestCase):  # pylint: disable=too-many-public-methods
    """
    Tests for FileSystemAgentNetworkPersistor.

    Covers AGENT_MANIFEST_FILE parsing in __init__, reading manifests written in UTF-8 and cp1252, the
    encoding and line endings of persisted files, get_network_file_path, and async_restore_metadata (#1398).
    Every persistor under test is rooted at a throwaway temp directory so no registries/ file is touched.
    """

    @staticmethod
    def _make_persistor(tmp_dir: str, subdirectory: str = "generated") -> FileSystemAgentNetworkPersistor:
        """
        Creates a persistor whose output_path is the given temp directory.

        AGENT_MANIFEST_FILE is patched only while the constructor runs, since __init__ reads it; output_path
        and subdirectory are then overwritten explicitly so no test depends on how __init__ derived them.

        :param tmp_dir: The directory the persistor writes network files and manifests under
        :param subdirectory: The subdirectory of tmp_dir that holds the network files, "generated" by default
        :return: A non-demo-mode persistor rooted at tmp_dir
        """
        manifest_path: str = os.path.join(tmp_dir, "manifest.hocon")
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": manifest_path}):
            persistor: FileSystemAgentNetworkPersistor = FileSystemAgentNetworkPersistor(demo_mode=False)
        persistor.output_path = tmp_dir
        persistor.subdirectory = subdirectory
        return persistor

    # Tests for AGENT_MANIFEST_FILE parsing in __init__

    def test_init_splits_manifest_env_var_on_pathsep(self) -> None:
        """
        __init__ takes the first entry of an os.pathsep-separated AGENT_MANIFEST_FILE.
        """
        first_manifest: str = os.path.join("first_dir", "manifest.hocon")
        second_manifest: str = os.path.join("second_dir", "manifest.hocon")
        env_value: str = os.pathsep.join([first_manifest, second_manifest])
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": env_value}):
            persistor: FileSystemAgentNetworkPersistor = FileSystemAgentNetworkPersistor(demo_mode=False)
        self.assertEqual(persistor.main_manifest_path, first_manifest)
        self.assertEqual(persistor.output_path, "first_dir")

    def test_init_skips_empty_leading_entry(self) -> None:
        """
        __init__ uses the first non-empty entry when AGENT_MANIFEST_FILE has a leading separator.
        """
        manifest: str = os.path.join("real_dir", "manifest.hocon")
        env_value: str = os.pathsep + manifest
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": env_value}):
            persistor: FileSystemAgentNetworkPersistor = FileSystemAgentNetworkPersistor(demo_mode=False)
        self.assertEqual(persistor.main_manifest_path, manifest)
        self.assertEqual(persistor.output_path, "real_dir")

    def test_init_defaults_when_manifest_env_var_empty(self) -> None:
        """
        __init__ falls back to the default registries paths when AGENT_MANIFEST_FILE is empty.
        """
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": ""}):
            persistor: FileSystemAgentNetworkPersistor = FileSystemAgentNetworkPersistor(demo_mode=False)
        self.assertEqual(persistor.output_path, "registries")
        self.assertEqual(persistor.main_manifest_path, os.path.join("registries", "manifest.hocon"))

    # Tests for async_persist reading a manifest with various encodings

    async def test_persist_appends_to_utf8_manifest(self) -> None:
        """
        async_persist reads and updates a UTF-8 manifest with non-ASCII content.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
            manifest_dir: str = os.path.join(tmp_dir, "generated")
            os.makedirs(manifest_dir)
            manifest_path: str = os.path.join(manifest_dir, "manifest.hocon")
            with open(manifest_path, "wb") as f:
                f.write('{\n    "café_network.hocon": true,\n}\n'.encode("utf-8"))

            await persistor.async_persist("agent = {}", "new_net")

            with open(manifest_path, "rb") as f:
                raw: bytes = f.read()
            content: str = raw.decode("utf-8")
            self.assertIn('"generated/new_net.hocon": true', content)
            # The pre-existing non-ASCII entry must survive the rewrite untouched.
            self.assertIn("café_network.hocon", content)

    async def test_persist_appends_to_cp1252_manifest(self) -> None:
        """
        async_persist reads a cp1252-encoded manifest and appends a new entry.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
            manifest_dir: str = os.path.join(tmp_dir, "generated")
            os.makedirs(manifest_dir)
            manifest_path: str = os.path.join(manifest_dir, "manifest.hocon")
            # 0xe9 is e-acute in cp1252, invalid as a UTF-8 continuation byte
            with open(manifest_path, "wb") as f:
                f.write(b'{\n    "caf\xe9_network.hocon": true,\n}\n')

            await persistor.async_persist("agent = {}", "new_net")

            with open(manifest_path, "rb") as f:
                content: str = f.read().decode("utf-8")
            self.assertIn('"generated/new_net.hocon": true', content)

    async def test_persist_detects_duplicate_in_cp1252_manifest(self) -> None:
        """
        async_persist correctly finds an existing entry in a cp1252-encoded manifest.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
            manifest_dir: str = os.path.join(tmp_dir, "generated")
            os.makedirs(manifest_dir)
            manifest_path: str = os.path.join(manifest_dir, "manifest.hocon")
            with open(manifest_path, "wb") as f:
                f.write(b'{\n    "generated/existing.hocon": true,\n    "caf\xe9.hocon": true,\n}\n')

            result: str | None = await persistor.async_persist("agent = {}", "existing")

            # A duplicate name is reported as None rather than a path, and the manifest must not
            # gain a second copy of the entry.
            self.assertIsNone(result)
            with open(manifest_path, "rb") as f:
                raw: bytes = f.read()
            self.assertEqual(raw.count(b"existing.hocon"), 1)

    # Tests for _async_update_main_manifest reading non-UTF-8 content

    async def test_update_main_manifest_reads_cp1252(self) -> None:
        """
        _async_update_main_manifest reads a cp1252-encoded main manifest.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir, subdirectory="custom")
            main_manifest: str = os.path.join(tmp_dir, "manifest.hocon")
            # Write main manifest with cp1252 content and an existing include line
            with open(main_manifest, "wb") as f:
                f.write(b'# caf\xe9 comment\n    include "registries/generated/manifest.hocon",\n')
            persistor.main_manifest_path = main_manifest

            await persistor._async_update_main_manifest()  # pylint: disable=protected-access

            with open(main_manifest, "rb") as f:
                content: str = f.read().decode("utf-8")
            base: str = os.path.basename(tmp_dir)
            self.assertIn(f'include "{base}/custom/manifest.hocon"', content)

    # Tests for async_persist file encoding and line endings

    async def test_persist_writes_utf8(self) -> None:
        """
        Persisted files are encoded as UTF-8.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)

            hocon_content: str = 'description = "café network"\n'
            await persistor.async_persist(hocon_content, "test_net")

            file_path: str = os.path.join(tmp_dir, "generated", "test_net.hocon")
            with open(file_path, "rb") as f:
                raw: bytes = f.read()
            # Decoding first turns a non-UTF-8 file into a loud UnicodeDecodeError instead of a
            # bare "bytes not found" failure from the assertion below.
            raw.decode("utf-8")
            self.assertIn("café".encode("utf-8"), raw)

    async def test_persist_unix_line_endings(self) -> None:
        """
        Persisted files use Unix line endings regardless of platform.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)

            hocon_content: str = "line1\nline2\nline3\n"
            await persistor.async_persist(hocon_content, "test_net")

            file_path: str = os.path.join(tmp_dir, "generated", "test_net.hocon")
            with open(file_path, "rb") as f:
                raw: bytes = f.read()
            self.assertNotIn(b"\r\n", raw)
            self.assertIn(b"\n", raw)

    # Helpers for the get_network_file_path / async_restore_metadata tests (#1398)

    def _make_temp_dir(self) -> str:
        """
        Creates a temporary directory that is removed when the current test finishes.

        mkdtemp plus addCleanup is used instead of TemporaryDirectory so the directory outlives
        the helper call without a context manager (which pylint flags as R1732).

        :return: The absolute path of the new temporary directory
        """
        tmp_dir: str = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir, True)
        return tmp_dir

    @staticmethod
    def _write_network_file(tmp_dir: str, name: str, content: str) -> Path:
        """
        Writes a network file where a persistor built by _make_persistor(tmp_dir) will look for it.

        The path is spelled out rather than taken from get_network_file_path so the restore tests
        cannot silently agree with a broken path helper.

        :param tmp_dir: The persistor's output_path
        :param name: The raw network name, without subdirectory prefix or extension
        :param content: The text to write, in HOCON or JSON syntax
        :return: The path of the written file
        """
        file_path: Path = Path(tmp_dir, "generated", f"{name}.hocon")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    # Tests for get_network_file_path

    def test_get_network_file_path_for_manifest_env_persistor(self) -> None:
        """
        get_network_file_path returns <output_path>/<subdirectory>/<name>.hocon for a persistor
        whose output_path came from AGENT_MANIFEST_FILE, for the default and a custom subdirectory.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        self.assertEqual(persistor.get_network_file_path("my_net"), Path(tmp_dir, "generated", "my_net.hocon"))

        custom: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir, subdirectory="custom")
        self.assertEqual(custom.get_network_file_path("my_net"), Path(tmp_dir, "custom", "my_net.hocon"))

    def test_get_network_file_path_for_default_persistor(self) -> None:
        """
        get_network_file_path returns registries/generated/<name>.hocon for a persistor built
        with AGENT_MANIFEST_FILE not set at all.
        """
        with patch.dict(os.environ):
            # patch.dict restores the variable afterwards; popping it models an unset env var,
            # which is a different branch from the empty-string case the __init__ tests cover.
            os.environ.pop("AGENT_MANIFEST_FILE", None)
            persistor: FileSystemAgentNetworkPersistor = FileSystemAgentNetworkPersistor(demo_mode=False)
        self.assertEqual(persistor.get_network_file_path("my_net"), Path("registries", "generated", "my_net.hocon"))

    def test_get_network_file_path_allows_nested_names(self) -> None:
        """
        A nested name stays inside the generated directory and maps to a nested file, so networks can be
        grouped in subdirectories.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        self.assertEqual(
            persistor.get_network_file_path("team/my_net"), Path(tmp_dir, "generated", "team", "my_net.hocon")
        )

    def test_get_network_file_path_rejects_names_that_escape_the_generated_directory(self) -> None:
        """
        A name that climbs out of <output_path>/<subdirectory>, by a leading or an embedded parent reference,
        is refused with ValueError, so neither the fallback read nor the write can reach a file outside it.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        for name in ("../outside", "../../etc/passwd", "team/../../outside", "sub/../../../x"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                persistor.get_network_file_path(name)

    async def test_restore_metadata_refuses_a_name_that_escapes_and_reads_nothing(self) -> None:
        """
        The fallback read refuses a traversing name before touching the file system: a HOCON file planted right
        above the generated directory is never parsed and its metadata never returned.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        Path(tmp_dir, "outside.hocon").write_text('{"metadata": {"description": "secret"}}\n', encoding="utf-8")

        with self.assertRaises(ValueError):
            await persistor.async_restore_metadata("../outside")

    async def test_persist_refuses_a_name_that_escapes_and_writes_nothing(self) -> None:
        """
        async_persist refuses a traversing name before writing anything: no file appears above the generated
        directory and the generated directory itself is not even created.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)

        with self.assertRaises(ValueError):
            await persistor.async_persist('{"tools": []}\n', "../escaped")

        self.assertFalse(Path(tmp_dir, "escaped.hocon").exists())
        self.assertFalse(Path(tmp_dir, "generated").exists())

    # Tests for async_restore_metadata

    async def test_restore_metadata_stat_failure_returns_none_and_warns(self) -> None:
        """
        A file whose size cannot be read (a permission or transient file system error) is treated like any
        unreadable file: None plus one WARNING, so the save goes on without the block instead of failing.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        self._write_network_file(tmp_dir, "flaky_net", '{"metadata": {"description": "x"}}\n')

        with (
            patch.object(Path, "stat", side_effect=PermissionError("simulated stat failure")),
            self.assertLogs(LOGGER_NAME, level=logging.WARNING) as captured,
        ):
            result: dict[str, Any] | None = await persistor.async_restore_metadata("flaky_net")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        self.assertIn("simulated stat failure", captured.records[0].getMessage())

    async def test_restore_metadata_missing_file_returns_none_silently(self) -> None:
        """
        async_restore_metadata returns None and logs nothing when no file exists for the name,
        because a first save has nothing to carry forward and must not look like an error.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)

        with self.assertNoLogs(LOGGER_NAME, level=logging.WARNING):
            result: dict[str, Any] | None = await persistor.async_restore_metadata("never_saved")

        self.assertIsNone(result)

    async def test_restore_metadata_returns_plain_types_from_json_syntax_file(self) -> None:
        """
        async_restore_metadata returns the metadata block of an include-free file written in JSON
        syntax as plain dict/list/str values with every key intact.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        content: str = json.dumps({"metadata": SAMPLE_METADATA, "tools": [{"name": "frontman"}]})
        self._write_network_file(tmp_dir, "json_net", content)

        with self.assertNoLogs(LOGGER_NAME, level=logging.WARNING):
            result: dict[str, Any] | None = await persistor.async_restore_metadata("json_net")

        self.assertEqual(result, SAMPLE_METADATA)
        self.assertCountEqual(result.keys(), SAMPLE_METADATA.keys())
        # pyhocon parses objects into ConfigTree; the restorer must have flattened them so the
        # middleware can merge and json.dumps the block without further conversion.
        self.assertIs(type(result), dict)
        self.assertIs(type(result["date_created"]), str)
        self.assertIs(type(result["sample_queries"]), list)
        self.assertIs(type(result["contact"]), dict)

    async def test_restore_metadata_unparseable_file_returns_none_and_warns(self) -> None:
        """
        async_restore_metadata returns None and logs one WARNING naming the file when it cannot be
        parsed, so a corrupt network can still be repaired by saving over it.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        file_path: Path = self._write_network_file(tmp_dir, "corrupt", "metadata = { unterminated")

        with self.assertLogs(LOGGER_NAME, level=logging.WARNING) as captured:
            result: dict[str, Any] | None = await persistor.async_restore_metadata("corrupt")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(captured.records[0].levelno, logging.WARNING)
        self.assertIn("Could not read existing agent network", captured.output[0])
        self.assertIn(str(file_path), captured.output[0])

    async def test_restore_metadata_string_metadata_returns_none_and_warns(self) -> None:
        """
        async_restore_metadata returns None and logs one WARNING when the file's "metadata" is a
        string rather than a block.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        content: str = json.dumps({"metadata": "not a block", "tools": []})
        self._write_network_file(tmp_dir, "str_meta", content)

        with self.assertLogs(LOGGER_NAME, level=logging.WARNING) as captured:
            result: dict[str, Any] | None = await persistor.async_restore_metadata("str_meta")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        self.assertIn("non-dict 'metadata' (str)", captured.output[0])

    async def test_restore_metadata_list_metadata_returns_none_and_warns(self) -> None:
        """
        async_restore_metadata returns None and logs one WARNING when the file's "metadata" is a
        list rather than a block.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        content: str = json.dumps({"metadata": ["not", "a", "block"], "tools": []})
        self._write_network_file(tmp_dir, "list_meta", content)

        with self.assertLogs(LOGGER_NAME, level=logging.WARNING) as captured:
            result: dict[str, Any] | None = await persistor.async_restore_metadata("list_meta")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        self.assertIn("non-dict 'metadata' (list)", captured.output[0])

    async def test_restore_metadata_null_metadata_returns_none_and_warns(self) -> None:
        """
        A file whose "metadata" is an explicit null (never something either assembler writes) yields None and one
        WARNING naming the path and the type, unlike a file without the key, which yields None silently.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        file_path: Path = self._write_network_file(tmp_dir, "null_net", '{"metadata": null, "tools": []}\n')

        with self.assertLogs(LOGGER_NAME, level=logging.WARNING) as captured:
            result: dict[str, Any] | None = await persistor.async_restore_metadata("null_net")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        message: str = captured.records[0].getMessage()
        self.assertIn("NoneType", message)
        self.assertIn(str(file_path), message)

    async def test_restore_metadata_absent_key_returns_none_silently(self) -> None:
        """
        async_restore_metadata returns None and logs nothing when the file parses but has no
        "metadata" key, which is how pre-#1398 networks without sample queries look.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        content: str = json.dumps({"tools": [{"name": "frontman"}]})
        self._write_network_file(tmp_dir, "no_meta", content)

        with self.assertNoLogs(LOGGER_NAME, level=logging.WARNING):
            result: dict[str, Any] | None = await persistor.async_restore_metadata("no_meta")

        self.assertIsNone(result)

    async def test_restore_metadata_top_level_list_returns_none_and_warns(self) -> None:
        """
        async_restore_metadata returns None and logs one WARNING when the file parses to a list
        instead of an object, since a list has no "metadata" key to look up.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        content: str = json.dumps([{"name": "frontman"}])
        self._write_network_file(tmp_dir, "top_list", content)

        with self.assertLogs(LOGGER_NAME, level=logging.WARNING) as captured:
            result: dict[str, Any] | None = await persistor.async_restore_metadata("top_list")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        self.assertIn("is not an object (list)", captured.output[0])

    # Test for the async_persist / async_restore_metadata round trip

    @staticmethod
    def _record_swap(seen: list[dict[str, Any]], real_replace: Callable[[Any, Any], None], src: Any, dst: Any) -> None:
        """
        Stand-in for os.replace that records what the swap would publish, then performs it.

        :param seen: The list the record is appended to
        :param real_replace: The real os.replace, called after recording
        :param src: The temp file about to be swapped in
        :param dst: The network file it replaces
        """
        seen.append({"src": Path(src), "dst": Path(dst), "content": Path(src).read_text(encoding="utf-8")})
        real_replace(src, dst)

    async def test_persist_publishes_the_complete_file_in_one_swap(self) -> None:
        """
        async_persist writes a sibling temp file and publishes it with a single os.replace: at swap time the temp
        file already holds the whole text, the swap targets get_network_file_path, no temp file is left behind,
        and the network file ends up with exactly the text.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        content: str = '{"metadata": {"description": "swap"}, "tools": [{"name": "a"}]}\n'
        seen: list[dict[str, Any]] = []
        real_replace: Callable[[Any, Any], None] = os.replace

        with patch("os.replace", side_effect=partial(self._record_swap, seen, real_replace)):
            await persistor.async_persist(content, "swap_net")

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["content"], content)
        self.assertEqual(seen[0]["dst"], persistor.get_network_file_path("swap_net"))
        self.assertEqual(seen[0]["src"].parent, seen[0]["dst"].parent)
        self.assertFalse(seen[0]["src"].exists())
        leftovers: list[str] = []
        for entry in os.listdir(Path(tmp_dir, "generated")):
            if entry.endswith(".tmp"):
                leftovers.append(entry)
        self.assertEqual(leftovers, [])
        self.assertEqual(persistor.get_network_file_path("swap_net").read_text(encoding="utf-8"), content)

    @staticmethod
    def _temp_files(tmp_dir: str) -> list[str]:
        """
        List the temp files async_persist may have left in the generated directory.

        :param tmp_dir: The persistor's output directory
        :return: The names of the *.tmp entries under <tmp_dir>/generated, in directory order
        """
        leftovers: list[str] = []
        for entry in os.listdir(Path(tmp_dir, "generated")):
            if entry.endswith(".tmp"):
                leftovers.append(entry)
        return leftovers

    async def test_persist_keeps_the_old_file_and_no_temp_file_when_the_swap_fails(self) -> None:
        """
        When os.replace raises, the error propagates, the network file still holds its previous text and the
        temp file is gone, so a failed save never leaves a torn or half-published network behind.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        old_content: str = '{"metadata": {"description": "old"}, "tools": [{"name": "a"}]}\n'
        self._write_network_file(tmp_dir, "swap_net", old_content)

        with patch("os.replace", side_effect=OSError("simulated replace failure")), self.assertRaises(OSError):
            await persistor.async_persist('{"metadata": {"description": "new"}}\n', "swap_net")

        self.assertEqual(persistor.get_network_file_path("swap_net").read_text(encoding="utf-8"), old_content)
        self.assertEqual(self._temp_files(tmp_dir), [])

    async def test_persist_keeps_the_old_file_and_no_temp_file_when_the_write_fails(self) -> None:
        """
        When the temp file cannot be opened for writing, the error propagates, the network file still holds its
        previous text and nothing is left behind.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        old_content: str = '{"metadata": {"description": "old"}, "tools": [{"name": "a"}]}\n'
        self._write_network_file(tmp_dir, "swap_net", old_content)

        with (
            patch("aiofiles.open", side_effect=PermissionError("simulated write failure")),
            self.assertRaises(PermissionError),
        ):
            await persistor.async_persist('{"metadata": {"description": "new"}}\n', "swap_net")

        self.assertEqual(persistor.get_network_file_path("swap_net").read_text(encoding="utf-8"), old_content)
        self.assertEqual(self._temp_files(tmp_dir), [])

    async def test_restore_metadata_empty_file_returns_none_and_warns(self) -> None:
        """
        A zero-byte network file (never something the persistor writes) yields None and one WARNING naming the
        path, instead of passing silently as a network without metadata.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)
        file_path: Path = self._write_network_file(tmp_dir, "empty_net", "")

        with self.assertLogs(LOGGER_NAME, level=logging.WARNING) as captured:
            result: dict[str, Any] | None = await persistor.async_restore_metadata("empty_net")

        self.assertIsNone(result)
        self.assertEqual(len(captured.records), 1)
        self.assertIn(str(file_path), captured.records[0].getMessage())
        self.assertIn("empty", captured.records[0].getMessage())

    async def test_persist_then_restore_metadata_round_trip(self) -> None:
        """
        async_restore_metadata reads back the metadata block of a network async_persist just wrote
        under the same name, proving both sides resolve the same file via get_network_file_path.
        """
        tmp_dir: str = self._make_temp_dir()
        persistor: FileSystemAgentNetworkPersistor = self._make_persistor(tmp_dir)

        location: str | None = await persistor.async_persist(ROUND_TRIP_HOCON, "round_trip")
        result: dict[str, Any] | None = await persistor.async_restore_metadata("round_trip")

        self.assertEqual(location, str(persistor.get_network_file_path("round_trip")))
        self.assertEqual(result, ROUND_TRIP_METADATA)
