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
Tests for the ``create_store`` factory and ``MemoryStoreConfig.resolve``.

Focus is on the env-override precedence chain:
HOCON < MEMORY_STORE_CONFIG JSON < individual MEMORY_* vars.
"""

import os
from unittest import TestCase
from unittest.mock import patch

from coded_tools.tools.persistent_memory.base_memory_store import MemoryStoreConfig
from coded_tools.tools.persistent_memory.json_file_store import JsonFileStoreBackend
from coded_tools.tools.persistent_memory.md_file_store import MdFileStoreBackend
from coded_tools.tools.persistent_memory.memory_store_factory import create_store
from coded_tools.tools.persistent_memory.memory_store_factory import resolve_config


# All MEMORY_* vars the factory inspects. Cleared in each test so host-env
# values cannot leak in and corrupt assertions.
_MEMORY_ENV_VARS: tuple[str, ...] = (
    "MEMORY_STORE_CONFIG",
    "MEMORY_BACKEND",
    "MEMORY_ROOT_PATH",
)


def _clean_env() -> dict[str, str]:
    """Return a dict copy of ``os.environ`` with every MEMORY_* var stripped."""
    return {k: v for k, v in os.environ.items() if k not in _MEMORY_ENV_VARS}


class TestResolveConfigPrecedence(TestCase):
    """The three-layer precedence chain: HOCON → JSON env → individual env vars."""

    def test_defaults_when_nothing_supplied(self):
        """No HOCON, no env: file_system backend under ./memory."""
        with patch.dict(os.environ, _clean_env(), clear=True):
            config: MemoryStoreConfig = resolve_config(None)
        self.assertEqual(config.backend, "file_system")
        self.assertEqual(config.root_path, "./memory")

    def test_hocon_only(self):
        """With no env overrides, HOCON values flow through unchanged."""
        with patch.dict(os.environ, _clean_env(), clear=True):
            config = resolve_config({"backend": "json_file", "root_path": "/some/path"})
        self.assertEqual(config.backend, "json_file")
        self.assertEqual(config.root_path, "/some/path")

    def test_individual_env_var_beats_hocon(self):
        """Setting only an individual MEMORY_* var overrides the HOCON field."""
        env = _clean_env()
        env["MEMORY_ROOT_PATH"] = "/from/env"
        with patch.dict(os.environ, env, clear=True):
            config = resolve_config({"backend": "file_system", "root_path": "/from/hocon"})
        self.assertEqual(config.root_path, "/from/env")

class TestCreateStore(TestCase):
    """Factory instantiation for the file-backed backends."""

    def test_file_system_backend(self):
        """``file_system`` yields a markdown-backed store."""
        with patch.dict(os.environ, _clean_env(), clear=True):
            store = create_store({"backend": "file_system", "root_path": "./memory"})
        self.assertIsInstance(store, MdFileStoreBackend)

    def test_json_file_backend(self):
        """``json_file`` yields a JSON-backed store."""
        with patch.dict(os.environ, _clean_env(), clear=True):
            store = create_store({"backend": "json_file", "root_path": "./memory"})
        self.assertIsInstance(store, JsonFileStoreBackend)

    def test_unknown_backend_raises(self):
        """An unrecognised backend name is a configuration error, not a silent fall-through."""
        with patch.dict(os.environ, _clean_env(), clear=True):
            with self.assertRaises(ValueError):
                create_store({"backend": "not_a_real_backend"})
