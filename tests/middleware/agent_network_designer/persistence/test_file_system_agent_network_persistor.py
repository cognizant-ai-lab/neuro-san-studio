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
import os
import tempfile
from unittest.mock import patch

from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import (
    FileSystemAgentNetworkPersistor,
)


class TestFileSystemAgentNetworkPersistor:
    """Tests for FileSystemAgentNetworkPersistor."""

    @staticmethod
    def _make_persistor(tmp_dir: str, subdirectory: str = "generated") -> FileSystemAgentNetworkPersistor:
        """Creates a persistor pointing at the given temp directory."""
        manifest_path = os.path.join(tmp_dir, "manifest.hocon")
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": manifest_path}):
            persistor = FileSystemAgentNetworkPersistor(demo_mode=False)
        persistor.output_path = tmp_dir
        persistor.subdirectory = subdirectory
        return persistor

    # Tests for async_persist reading a manifest with various encodings

    def test_persist_appends_to_utf8_manifest(self):
        """async_persist reads and updates a UTF-8 manifest with non-ASCII content."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor = self._make_persistor(tmp_dir)
            manifest_dir = os.path.join(tmp_dir, "generated")
            os.makedirs(manifest_dir)
            manifest_path = os.path.join(manifest_dir, "manifest.hocon")
            with open(manifest_path, "wb") as f:
                f.write('{\n    "café_network.hocon": true,\n}\n'.encode("utf-8"))

            asyncio.run(persistor.async_persist("agent = {}", "new_net"))

            with open(manifest_path, "rb") as f:
                raw = f.read()
            content = raw.decode("utf-8")
            assert '"generated/new_net.hocon": true' in content
            assert "café_network.hocon" in content

    def test_persist_appends_to_cp1252_manifest(self):
        """async_persist reads a cp1252-encoded manifest and appends a new entry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor = self._make_persistor(tmp_dir)
            manifest_dir = os.path.join(tmp_dir, "generated")
            os.makedirs(manifest_dir)
            manifest_path = os.path.join(manifest_dir, "manifest.hocon")
            # 0xe9 is e-acute in cp1252, invalid as a UTF-8 continuation byte
            with open(manifest_path, "wb") as f:
                f.write(b'{\n    "caf\xe9_network.hocon": true,\n}\n')

            asyncio.run(persistor.async_persist("agent = {}", "new_net"))

            with open(manifest_path, "rb") as f:
                content = f.read().decode("utf-8")
            assert '"generated/new_net.hocon": true' in content

    def test_persist_detects_duplicate_in_cp1252_manifest(self):
        """async_persist correctly finds an existing entry in a cp1252-encoded manifest."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor = self._make_persistor(tmp_dir)
            manifest_dir = os.path.join(tmp_dir, "generated")
            os.makedirs(manifest_dir)
            manifest_path = os.path.join(manifest_dir, "manifest.hocon")
            with open(manifest_path, "wb") as f:
                f.write(b'{\n    "generated/existing.hocon": true,\n    "caf\xe9.hocon": true,\n}\n')

            result = asyncio.run(persistor.async_persist("agent = {}", "existing"))

            assert result is None
            with open(manifest_path, "rb") as f:
                raw = f.read()
            assert raw.count(b"existing.hocon") == 1

    # Tests for _async_update_main_manifest reading non-UTF-8 content

    def test_update_main_manifest_reads_cp1252(self):
        """_async_update_main_manifest reads a cp1252-encoded main manifest."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor = self._make_persistor(tmp_dir, subdirectory="custom")
            main_manifest = os.path.join(tmp_dir, "manifest.hocon")
            # Write main manifest with cp1252 content and an existing include line
            with open(main_manifest, "wb") as f:
                f.write(b'# caf\xe9 comment\n    include "registries/generated/manifest.hocon",\n')
            persistor.main_manifest_path = main_manifest

            asyncio.run(persistor._async_update_main_manifest())  # pylint: disable=protected-access

            with open(main_manifest, "rb") as f:
                content = f.read().decode("utf-8")
            base = os.path.basename(tmp_dir)
            assert f'include "{base}/custom/manifest.hocon"' in content

    # Tests for async_persist file encoding and line endings

    def test_persist_writes_utf8(self):
        """Persisted files are encoded as UTF-8."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            persistor = self._make_persistor(tmp_dir)

            hocon_content = 'description = "café network"\n'
            asyncio.run(persistor.async_persist(hocon_content, "test_net"))

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
            asyncio.run(persistor.async_persist(hocon_content, "test_net"))

            file_path = os.path.join(tmp_dir, "generated", "test_net.hocon")
            with open(file_path, "rb") as f:
                raw = f.read()
            assert b"\r\n" not in raw
            assert b"\n" in raw
