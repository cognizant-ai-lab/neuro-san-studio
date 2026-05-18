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

"""Behaviour tests for ``MarkdownFileStore``."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from middleware.persistent_memory.markdown_file_store import MarkdownFileStore
from tests.middleware.persistent_memory.base import MemoryTestBase


class MarkdownFileStoreTests(MemoryTestBase):
    """Behaviour tests for the markdown backend."""

    def _make_store(self) -> MarkdownFileStore:
        """Build a store rooted in the scratch directory."""
        return MarkdownFileStore(folder_name=self._tmp)

    def test_load_missing_tree_returns_empty(self) -> None:
        """Reading from an unseen agent returns an empty dict."""
        store: MarkdownFileStore = self._make_store()
        self.assertEqual(asyncio.run(store._read_bucket("net.agent")), {})  # pylint: disable=protected-access

    def test_roundtrip_preserves_topics(self) -> None:
        """Per-topic writes accumulate and read back as one dict."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.set_topic("net.agent", "mike", "Works in Sales."))
        asyncio.run(store.set_topic("net.agent", "john", "Works in Education."))
        loaded: dict = asyncio.run(store._read_bucket("net.agent"))  # pylint: disable=protected-access
        self.assertEqual(loaded, {"mike": "Works in Sales.", "john": "Works in Education."})

    def test_md_file_format(self) -> None:
        """Files start with the H1 heading and contain the content body."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.set_topic("net.agent", "role", "Engineer"))
        text: str = (Path(self._tmp) / "net" / "agent" / "role.md").read_text()
        self.assertTrue(text.startswith("# role"))
        self.assertIn("Engineer", text)

    def test_filename_sanitisation(self) -> None:
        """Unsafe characters collapse to underscores, and the file stem lowercases."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.set_topic("net.agent", "My Fancy Topic!", "x"))
        base: Path = Path(self._tmp) / "net" / "agent"
        self.assertTrue((base / "my_fancy_topic.md").exists())

    def test_delete_topic_unlinks_only_that_file(self) -> None:
        """``delete_topic`` removes one file and leaves the rest in place."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.set_topic("net.agent", "coffee", "black"))
        asyncio.run(store.set_topic("net.agent", "role", "engineer"))
        removed: bool = asyncio.run(store.delete_topic("net.agent", "coffee"))
        base: Path = Path(self._tmp) / "net" / "agent"
        self.assertTrue(removed)
        self.assertFalse((base / "coffee.md").exists())
        self.assertTrue((base / "role.md").exists())

    def test_append_to_topic_round_trips(self) -> None:
        """``append_to_topic`` reads-modifies-writes the topic file."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.set_topic("net.agent", "orders", "matcha"))
        final: str = asyncio.run(store.append_to_topic("net.agent", "orders", "latte"))
        self.assertTrue(final.startswith("matcha"))
        self.assertIn("latte", final)
        loaded: Optional[str] = asyncio.run(store.get_topic("net.agent", "orders"))
        self.assertEqual(loaded, final)
