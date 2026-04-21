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

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from coded_tools.tools.persistent_memory.json_file_store import JsonFileStoreBackend


NS = ("net", "agent", "mike")


class TestJsonFileStoreBackend(TestCase):
    """CRUD + one-JSON-file-per-user layout + path-traversal sanitisation."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = Path(self._tmp)
        self.store = JsonFileStoreBackend(root_path=str(self.root))

    def test_extra_fields_are_preserved_in_json(self):
        """Non-``content`` fields round-trip as-is through the JSON serialiser."""
        asyncio.run(
            self.store.create(NS, "drink", {"content": "likes dark coffee", "category": "beverage"})
        )
        item = asyncio.run(self.store.read(NS, "drink"))
        self.assertEqual(item.value["content"], "likes dark coffee")
        self.assertEqual(item.value["category"], "beverage")

        parsed = json.loads((self.root / "net" / "agent" / "mike.json").read_text())
        self.assertEqual(parsed["drink"]["category"], "beverage")

    def test_hand_edited_json_file_is_readable(self):
        """A user can edit the JSON file directly — any valid object loads."""
        directory = self.root / "net" / "agent"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "mike.json").write_text(json.dumps({
            "name": {"content": "The user's name is Mike."},
            "favorite_coffee_order": {"content": "Black, from Henry's."},
        }))
        self.assertEqual(asyncio.run(self.store.list(NS)), ["favorite_coffee_order", "name"])
        item = asyncio.run(self.store.read(NS, "name"))
        self.assertIn("Mike", item.value["content"])

    def test_raw_string_values_are_coerced_into_content_shape(self):
        """A hand-edited ``{"name": "Mike"}`` still loads as ``{"name": {"content": "Mike"}}``."""
        directory = self.root / "net" / "agent"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "mike.json").write_text(json.dumps({"name": "Mike"}))
        item = asyncio.run(self.store.read(NS, "name"))
        self.assertIsNotNone(item)
        self.assertEqual(item.value["content"], "Mike")

    def test_malformed_json_file_is_treated_as_empty(self):
        """A corrupt JSON file does not crash the tool — it reads as empty."""
        directory = self.root / "net" / "agent"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "mike.json").write_text("{not valid json}")
        self.assertEqual(asyncio.run(self.store.list(NS)), [])
        # A subsequent write recovers cleanly by overwriting the bad file.
        asyncio.run(self.store.create(NS, "name", {"content": "recovered"}))
        item = asyncio.run(self.store.read(NS, "name"))
        self.assertEqual(item.value["content"], "recovered")
