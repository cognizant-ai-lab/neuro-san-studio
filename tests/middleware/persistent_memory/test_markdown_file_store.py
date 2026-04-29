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
        """load_all without any files returns an empty dict."""
        store: MarkdownFileStore = self._make_store()
        self.assertEqual(asyncio.run(store.load_all("net.agent")), {})

    def test_roundtrip_preserves_topics(self) -> None:
        """Writing then loading restores the same ``{topic: content}``."""
        store: MarkdownFileStore = self._make_store()
        memory: dict = {
            "mike": "Works in Sales.",
            "shrushti": "Works in Education.",
        }
        asyncio.run(store.save_all("net.agent", memory))
        loaded: dict = asyncio.run(store.load_all("net.agent"))
        self.assertEqual(loaded, memory)

    def test_md_file_format(self) -> None:
        """Files start with the H1 heading and contain the content body."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.save_all("net.agent", {"role": "Engineer"}))
        text: str = (Path(self._tmp) / "net" / "agent" / "role.md").read_text()
        self.assertTrue(text.startswith("# role"))
        self.assertIn("Engineer", text)

    def test_orphan_topic_file_removed(self) -> None:
        """Topics dropped from memory have their ``.md`` files deleted."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.save_all("net.agent", {"coffee": "black", "role": "E"}))
        asyncio.run(store.save_all("net.agent", {"role": "E"}))
        base: Path = Path(self._tmp) / "net" / "agent"
        self.assertFalse((base / "coffee.md").exists())
        self.assertTrue((base / "role.md").exists())

    def test_filename_sanitisation(self) -> None:
        """Unsafe characters collapse to underscores, and the file stem lowercases."""
        store: MarkdownFileStore = self._make_store()
        asyncio.run(store.save_all("net.agent", {"My Fancy Topic!": "x"}))
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
