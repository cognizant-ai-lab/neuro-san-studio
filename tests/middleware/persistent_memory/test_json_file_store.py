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

"""Round-trip + edge-case tests for ``JsonFileStore``."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from middleware.persistent_memory.json_file_store import JsonFileStore
from tests.middleware.persistent_memory.base import MemoryTestBase


class JsonFileStoreTests(MemoryTestBase):
    """Behaviour tests for the JSON backend."""

    def _make_store(self, name: str = "memory") -> JsonFileStore:
        """Build a fresh store rooted in the scratch directory."""
        return JsonFileStore(folder_name=self._tmp, file_name=name)

    def test_load_missing_file_returns_empty(self) -> None:
        """Reading from an unseen agent returns an empty dict."""
        store: JsonFileStore = self._make_store()
        result: dict = asyncio.run(store._read_bucket("net.agent"))  # pylint: disable=protected-access
        self.assertEqual(result, {})

    def test_set_then_read_roundtrip(self) -> None:
        """Per-topic writes accumulate and read back as one dict."""
        store: JsonFileStore = self._make_store()
        asyncio.run(store.set_topic("net.agent", "mike", "Works in Sales."))
        asyncio.run(store.set_topic("net.agent", "john", "Works in Education."))
        loaded: dict = asyncio.run(store._read_bucket("net.agent"))  # pylint: disable=protected-access
        self.assertEqual(loaded, {"mike": "Works in Sales.", "john": "Works in Education."})

    def test_custom_file_name(self) -> None:
        """Configured file_name is honoured."""
        store: JsonFileStore = self._make_store(name="custom")
        asyncio.run(store.set_topic("net.agent", "t", "v"))
        expected: Path = Path(self._tmp) / "net" / "agent" / "custom.json"
        self.assertTrue(expected.exists())

    def test_malformed_json_tolerated(self) -> None:
        """A malformed file loads as an empty dict instead of raising."""
        store: JsonFileStore = self._make_store()
        path: Path = Path(self._tmp) / "net" / "agent" / "memory.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertEqual(asyncio.run(store._read_bucket("net.agent")), {})  # pylint: disable=protected-access

    def test_legacy_content_dict_coerced_to_string(self) -> None:
        """Legacy ``{"content": "..."}`` dicts are coerced to plain strings."""
        store: JsonFileStore = self._make_store()
        path: Path = Path(self._tmp) / "net" / "agent" / "memory.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy: dict = {"coffee": {"content": "black", "meta": 1}}
        path.write_text(json.dumps(legacy), encoding="utf-8")
        loaded: dict = asyncio.run(store._read_bucket("net.agent"))  # pylint: disable=protected-access
        self.assertEqual(loaded, {"coffee": "black"})

    def test_set_topic_overwrites_existing_value(self) -> None:
        """Re-setting a topic replaces its content, leaving other topics intact."""
        store: JsonFileStore = self._make_store()
        asyncio.run(store.set_topic("net.agent", "t1", "a"))
        asyncio.run(store.set_topic("net.agent", "t2", "b"))
        asyncio.run(store.set_topic("net.agent", "t1", "A"))
        loaded: dict = asyncio.run(store._read_bucket("net.agent"))  # pylint: disable=protected-access
        self.assertEqual(loaded, {"t1": "A", "t2": "b"})
