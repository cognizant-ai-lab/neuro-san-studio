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
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from coded_tools.tools.persistent_memory.md_file_store import DEFAULT_KEY
from coded_tools.tools.persistent_memory.md_file_store import MdFileStoreBackend

NS = ("net", "agent", "mike")


class TestMdFileStoreBackend(TestCase):
    """CRUD + one-file-per-user markdown layout + path-traversal sanitisation."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.root = Path(self._tmp)
        self.store = MdFileStoreBackend(root_path=str(self.root))

    def test_put_then_get_returns_stored_value(self):
        """Round-trip via the filesystem returns the written value."""
        asyncio.run(self.store.create(NS, "name", {"content": "The user's name is Mike."}))
        item = asyncio.run(self.store.read(NS, "name"))
        self.assertEqual(item.value["content"], "The user's name is Mike.")

    def test_entries_survive_new_backend_instance(self):
        """Data is persistent: a fresh backend over the same root_path sees prior writes."""
        asyncio.run(self.store.create(NS, "name", {"content": "persisted"}))
        fresh = MdFileStoreBackend(root_path=str(self.root))
        item = asyncio.run(fresh.read(NS, "name"))
        self.assertIsNotNone(item)
        self.assertEqual(item.value["content"], "persisted")

    def test_on_disk_layout_is_one_file_per_user(self):
        """
        The user's whole memory lives in one markdown file named after them,
        at <root>/<network>/<agent>/<actor>.md, with one H1 section per topic.
        """
        asyncio.run(self.store.create(NS, "name", {"content": "The user's name is Mike."}))
        asyncio.run(self.store.create(NS, "favorite_coffee_order", {"content": "Black coffee from Henry's."}))
        path = self.root / "net" / "agent" / "mike.md"
        self.assertTrue(path.exists(), f"expected one file per user at {path}")
        text = path.read_text()
        # Both topics land as H1 sections inside the same file.
        self.assertIn("# name", text)
        self.assertIn("The user's name is Mike.", text)
        self.assertIn("# favorite_coffee_order", text)
        self.assertIn("Black coffee from Henry's.", text)

    def test_extra_fields_render_as_fenced_json_block(self):
        """Fields other than 'content' are written as a ```json block inside the section."""
        asyncio.run(self.store.create(NS, "drink", {"content": "likes dark coffee", "category": "beverage"}))
        text = (self.root / "net" / "agent" / "mike.md").read_text()
        self.assertIn("# drink", text)
        self.assertIn("```json", text)
        self.assertIn('"category": "beverage"', text)
        self.assertIn("likes dark coffee", text)

        # Round-trip preserves both fields.
        item = asyncio.run(self.store.read(NS, "drink"))
        self.assertEqual(item.value["content"], "likes dark coffee")
        self.assertEqual(item.value["category"], "beverage")

    def test_namespace_component_sanitisation(self):
        """Path-traversal characters in any namespace part are replaced."""
        ns_bad = ("../evil", "agent", "user")
        asyncio.run(self.store.create(ns_bad, "k1", {"content": "safe"}))
        outside = self.root.parent / "evil"
        self.assertFalse(outside.exists(), "sanitisation failed — write escaped root")
        self.assertTrue(any(self.root.rglob("*.md")))

    def test_delete_removes_only_that_section(self):
        """delete() strips one H1 section from the user's file; siblings survive."""
        asyncio.run(self.store.create(NS, "k1", {"content": "one"}))
        asyncio.run(self.store.create(NS, "k2", {"content": "two"}))
        asyncio.run(self.store.delete(NS, "k1"))

        self.assertIsNone(asyncio.run(self.store.read(NS, "k1")))
        remaining = asyncio.run(self.store.read(NS, "k2"))
        self.assertEqual(remaining.value["content"], "two")

        text = (self.root / "net" / "agent" / "mike.md").read_text()
        self.assertNotIn("# k1", text)
        self.assertIn("# k2", text)

    def test_search_uses_shared_keyword_ranker(self):
        """Search ranks by the same keyword rule as the in-memory backend."""
        asyncio.run(self.store.create(NS, "k1", {"content": "loves coffee and tea"}))
        asyncio.run(self.store.create(NS, "k2", {"content": "only tea"}))
        results = asyncio.run(self.store.search(NS, "coffee tea", limit=5))
        self.assertEqual([r.key for r in results], ["k1", "k2"])

    def test_list_keys_returns_all_topics_in_user_file(self):
        """list_keys returns every H1 heading in the user's file, sorted."""
        asyncio.run(self.store.create(NS, "b_topic", {"content": "v"}))
        asyncio.run(self.store.create(NS, "a_topic", {"content": "v"}))
        self.assertEqual(asyncio.run(self.store.list(NS)), ["a_topic", "b_topic"])

    def test_hand_edited_minimal_file_is_readable(self):
        """
        A user can edit the markdown file directly — any valid H1-sectioned
        doc is readable by the store without relying on exact serialisation.
        """
        directory = self.root / "net" / "agent"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "mike.md").write_text(
            "# name\n\nThe user's name is Mike.\n\n# favorite_coffee_order\n\nBlack, from Henry's.\n"
        )
        self.assertEqual(asyncio.run(self.store.list(NS)), ["favorite_coffee_order", "name"])
        item = asyncio.run(self.store.read(NS, "name"))
        self.assertIn("Mike", item.value["content"])

    def test_single_default_entry_writes_without_heading(self):
        """
        When the only entry uses the canonical default key, the file is just
        the accumulated prose — no '# content' heading, no scaffolding.
        """
        asyncio.run(self.store.create(NS, DEFAULT_KEY, {"content": "likes latte from Bob's"}))
        text = (self.root / "net" / "agent" / "mike.md").read_text()
        self.assertNotIn("#", text)
        self.assertIn("likes latte from Bob's", text)

        # Round-trip still works: read/get returns the same content.
        item = asyncio.run(self.store.read(NS, DEFAULT_KEY))
        self.assertEqual(item.value["content"], "likes latte from Bob's")

    def test_headingless_file_parses_as_default_key(self):
        """A hand-written prose file (no H1) is readable under the default key."""
        directory = self.root / "net" / "agent"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "mike.md").write_text("Mike ordered a latte at Bob's today.\n")
        item = asyncio.run(self.store.read(NS, DEFAULT_KEY))
        self.assertIsNotNone(item)
        self.assertIn("latte at Bob's", item.value["content"])
