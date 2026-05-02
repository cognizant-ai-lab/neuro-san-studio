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

"""Tests for FileSystemAgentNetworkPersistor encoding behavior."""

import asyncio
import logging
import os
import tempfile
from unittest.mock import patch

import aiofiles

from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import (
    FileSystemAgentNetworkPersistor,
)


class TestFileSystemAgentNetworkPersistor:
    """Tests for FileSystemAgentNetworkPersistor."""

    @staticmethod
    def _make_persistor(tmp_dir: str) -> FileSystemAgentNetworkPersistor:
        """Creates a persistor pointing at the given temp directory."""
        manifest_path = os.path.join(tmp_dir, "manifest.hocon")
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": manifest_path}):
            persistor = FileSystemAgentNetworkPersistor(demo_mode=False)
        persistor.output_path = tmp_dir
        persistor.subdirectory = "generated"
        return persistor

    # Test cases for _async_read_text

    def test_read_utf8_file(self):
        """Reads a UTF-8 file with non-ASCII content correctly."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".hocon", delete=False) as tmp:
            tmp.write('description = "café résumé"\n'.encode("utf-8"))
            tmp_path = tmp.name

        try:
            persistor = self._make_persistor(os.path.dirname(tmp_path))
            result = asyncio.run(persistor._async_read_text(tmp_path))  # pylint: disable=protected-access
            assert "café résumé" in result
        finally:
            os.unlink(tmp_path)

    def test_read_ascii_file(self):
        """Reads a pure-ASCII file (valid in both UTF-8 and cp1252)."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".hocon", delete=False) as tmp:
            tmp.write(b'{\n    "network.hocon": true\n}\n')
            tmp_path = tmp.name

        try:
            persistor = self._make_persistor(os.path.dirname(tmp_path))
            result = asyncio.run(persistor._async_read_text(tmp_path))  # pylint: disable=protected-access
            assert '"network.hocon": true' in result
        finally:
            os.unlink(tmp_path)

    def test_fallback_called_on_non_utf8(self, caplog):
        """Logs a warning and falls back when file is not valid UTF-8."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".hocon", delete=False) as tmp:
            # 0x80 is invalid UTF-8 start byte but valid in cp1252 (euro sign)
            tmp.write(b'key = "val\x80ue"\n')
            tmp_path = tmp.name

        try:
            persistor = self._make_persistor(os.path.dirname(tmp_path))

            # Mock the fallback open to simulate a Windows platform where
            # encoding="locale" would be cp1252
            original_open = aiofiles.open

            call_count = {"n": 0}

            def mock_open(path, mode="r", **kwargs):
                call_count["n"] += 1
                if call_count["n"] == 2:
                    # Second call is the fallback — force cp1252
                    kwargs["encoding"] = "cp1252"
                return original_open(path, mode, **kwargs)

            with patch("aiofiles.open", side_effect=mock_open):
                with caplog.at_level(logging.WARNING):
                    result = asyncio.run(persistor._async_read_text(tmp_path))  # pylint: disable=protected-access

            assert "not valid UTF-8" in caplog.text
            assert "val€ue" in result
        finally:
            os.unlink(tmp_path)

    def test_fallback_reads_cp1252_content(self):
        """Verifies the fallback correctly decodes cp1252 bytes."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".hocon", delete=False) as tmp:
            # Write cp1252-encoded content: café where é = 0xe9 in cp1252
            tmp.write(b'description = "caf\xe9"\n')
            tmp_path = tmp.name

        try:
            persistor = self._make_persistor(os.path.dirname(tmp_path))

            original_open = aiofiles.open
            call_count = {"n": 0}

            def mock_open(path, mode="r", **kwargs):
                call_count["n"] += 1
                if call_count["n"] == 2:
                    kwargs["encoding"] = "cp1252"
                return original_open(path, mode, **kwargs)

            with patch("aiofiles.open", side_effect=mock_open):
                result = asyncio.run(persistor._async_read_text(tmp_path))  # pylint: disable=protected-access

            assert "café" in result
        finally:
            os.unlink(tmp_path)

    # Tests for async_persist file encoding and line endings."""

    def test_persist_writes_utf8(self):
        """Persisted files are encoded as UTF-8."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor = self._make_persistor(tmp_dir)

            hocon_content = 'description = "café network"\n'
            asyncio.run(persistor.async_persist(hocon_content, "generated/test_net"))

            file_path = os.path.join(tmp_dir, "generated", "test_net.hocon")
            with open(file_path, "rb") as f:
                raw = f.read()
            raw.decode("utf-8")
            assert "café".encode("utf-8") in raw

    def test_persist_unix_line_endings(self):
        """Persisted files use Unix line endings regardless of platform."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor = self._make_persistor(tmp_dir)

            hocon_content = "line1\nline2\nline3\n"
            asyncio.run(persistor.async_persist(hocon_content, "generated/test_net"))

            file_path = os.path.join(tmp_dir, "generated", "test_net.hocon")
            with open(file_path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw
            assert b"\n" in raw
