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

"""Tests for ``TopicStoreFactory`` backend selection."""

from __future__ import annotations

from middleware.persistent_memory.json_file_store import JsonFileStore
from middleware.persistent_memory.markdown_file_store import MarkdownFileStore
from middleware.persistent_memory.topic_store_factory import TopicStoreFactory
from tests.middleware.persistent_memory.base import MemoryTestBase


class TopicStoreFactoryTests(MemoryTestBase):
    """Factory dispatch tests."""

    def test_default_backend_is_json_file(self) -> None:
        """With no config supplied the factory builds a JSON-backed store."""
        store = TopicStoreFactory.create(None)
        self.assertIsInstance(store, JsonFileStore)

    def test_markdown_file_backend(self) -> None:
        """``markdown_file`` yields a markdown-backed store."""
        store = TopicStoreFactory.create({"backend": "markdown_file", "folder_name": self._tmp})
        self.assertIsInstance(store, MarkdownFileStore)

    def test_unknown_backend_raises(self) -> None:
        """An unrecognised backend name raises ``ValueError``."""
        with self.assertRaises(ValueError):
            TopicStoreFactory.create({"backend": "no_such_backend"})

    def test_file_name_propagates_to_json_backend(self) -> None:
        """The ``file_name`` HOCON field is forwarded to ``JsonFileStore``."""
        store = TopicStoreFactory.create(
            {"backend": "json_file", "folder_name": self._tmp, "file_name": "notes"}
        )
        self.assertIsInstance(store, JsonFileStore)
        # Internal check: the resolved file path uses the custom stem.
        path = store._path_for("net.agent")  # pylint: disable=protected-access
        self.assertTrue(str(path).endswith("notes.json"))

    def test_backend_name_normalised(self) -> None:
        """Backend names are lower-cased and stripped before dispatch."""
        store = TopicStoreFactory.create(
            {"backend": "  MARKDOWN_FILE  ", "folder_name": self._tmp}
        )
        self.assertIsInstance(store, MarkdownFileStore)
