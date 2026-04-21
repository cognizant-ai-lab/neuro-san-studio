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
Tests for ``MemoryStoreFactory`` and ``MemoryStoreConfig.resolve``.

Focus is on the env-override precedence chain:
HOCON < MEMORY_STORE_CONFIG JSON < individual MEMORY_* vars.
"""

import os
from unittest.mock import patch

from coded_tools.tools.persistent_memory.json_file_store import JsonFileStore
from coded_tools.tools.persistent_memory.markdown_file_store import MarkdownFileStore
from coded_tools.tools.persistent_memory.memory_store_config import MemoryStoreConfig
from coded_tools.tools.persistent_memory.memory_store_factory import MemoryStoreFactory
from tests.coded_tools.tools.persistent_memory._base import MemoryTestBase


class TestResolveConfigPrecedence(MemoryTestBase):
    """The three-layer precedence chain: HOCON → JSON env → individual env vars."""

    def test_defaults_when_nothing_supplied(self):
        """No HOCON, no env: markdown_file backend under ./memory."""
        with patch.dict(os.environ, self.clean_env_dict(), clear=True):
            config: MemoryStoreConfig = MemoryStoreFactory.resolve_config(None)
        self.assertEqual(config.backend, "markdown_file")
        self.assertEqual(config.root_path, "./memory")

    def test_hocon_only(self):
        """With no env overrides, HOCON values flow through unchanged."""
        with patch.dict(os.environ, self.clean_env_dict(), clear=True):
            config = MemoryStoreFactory.resolve_config({"backend": "json_file", "root_path": "/some/path"})
        self.assertEqual(config.backend, "json_file")
        self.assertEqual(config.root_path, "/some/path")

    def test_individual_env_var_beats_hocon(self):
        """Setting only an individual MEMORY_* var overrides the HOCON field."""
        env = self.clean_env_dict()
        env["MEMORY_ROOT_PATH"] = "/from/env"
        with patch.dict(os.environ, env, clear=True):
            config = MemoryStoreFactory.resolve_config({"backend": "markdown_file", "root_path": "/from/hocon"})
        self.assertEqual(config.root_path, "/from/env")


class TestCreateStore(MemoryTestBase):
    """Factory instantiation for the file-backed backends."""

    def test_markdown_file_backend(self):
        """``markdown_file`` yields a markdown-backed store."""
        with patch.dict(os.environ, self.clean_env_dict(), clear=True):
            store = MemoryStoreFactory.create({"backend": "markdown_file", "root_path": "./memory"})
        self.assertIsInstance(store, MarkdownFileStore)

    def test_json_file_backend(self):
        """``json_file`` yields a JSON-backed store."""
        with patch.dict(os.environ, self.clean_env_dict(), clear=True):
            store = MemoryStoreFactory.create({"backend": "json_file", "root_path": "./memory"})
        self.assertIsInstance(store, JsonFileStore)

    def test_unknown_backend_raises(self):
        """An unrecognised backend name is a configuration error, not a silent fall-through."""
        with patch.dict(os.environ, self.clean_env_dict(), clear=True):
            with self.assertRaises(ValueError):
                MemoryStoreFactory.create({"backend": "not_a_real_backend"})
