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

"""Tests for BaseRag's vector store persistence: never save, and never trust, an empty store (issue #1368)."""

import asyncio
import os
import shutil
import tempfile
from typing import Optional
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.vectorstores import VectorStore

from neuro_san_studio.coded_tools.pdf_rag import PdfRag

LOGGER_NAME = "neuro_san_studio.coded_tools.base_rag"
SPLITTER_TARGET = "neuro_san_studio.coded_tools.base_rag.RecursiveCharacterTextSplitter"
LOADER_ARGS = {"urls": ["http://example.com/report.pdf"]}
GOOD_DOCS = [
    Document(page_content="Page one text", metadata={"source": "http://example.com/report.pdf"}),
    Document(page_content="Page two text", metadata={"source": "http://example.com/report.pdf"}),
]
# InMemoryVectorStore.dump writes "{}" for a store with no documents.
EMPTY_STORE_FILE_SIZE = 2


class TestBaseRag(TestCase):
    """
    Unit tests for BaseRag's save/load path using a real InMemoryVectorStore on disk.

    PdfRag is used as the concrete subclass so this module keeps exactly one class; its load_documents is
    patched with an AsyncMock so no network or PDF parsing is involved. The embedding is deterministic and
    network-free, so dump/load round trips exercise the real langchain serialization.
    """

    def setUp(self) -> None:
        """
        Build a PdfRag without running BaseRag.__init__ and give each test its own temporary directory.
        """
        # Bypass BaseRag.__init__, which instantiates OpenAIEmbeddings and therefore requires an
        # OPENAI_API_KEY; set the three attributes it would have set by hand instead.
        self.tool: PdfRag = object.__new__(PdfRag)
        self.tool.save_vector_store = False
        self.tool.abs_vector_store_path = None
        self.tool.embeddings = DeterministicFakeEmbedding(size=8)

        self.tmp_dir: str = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)

    @staticmethod
    def _passthrough_splitter_cls() -> MagicMock:
        """
        Build a stand-in for RecursiveCharacterTextSplitter whose splitter returns documents unchanged.

        The real from_tiktoken_encoder downloads a tokenizer, so tests must not reach it.

        :return: A MagicMock class whose from_tiktoken_encoder(...).split_documents(docs) returns docs.
        """
        splitter_cls = MagicMock()
        splitter_cls.from_tiktoken_encoder.return_value.split_documents.side_effect = list
        return splitter_cls

    @staticmethod
    def _store_path(tmp_dir: str) -> str:
        """
        Build the vector store JSON path inside the given temporary directory.

        :param tmp_dir: The temporary directory owned by the test.
        :return: The absolute path of the vector store file.
        """
        return os.path.join(tmp_dir, "vector_store.json")

    def _configure_save(self) -> str:
        """
        Turn on persistence for the tool, pointing at a file in the test's temporary directory.

        :return: The absolute path the tool will save to and load from.
        """
        path: str = self._store_path(self.tmp_dir)
        self.tool.save_vector_store = True
        self.tool.abs_vector_store_path = path
        return path

    def _generate(self, docs: list[Document]) -> tuple[Optional[VectorStore], AsyncMock]:
        """
        Run generate_vector_store with load_documents returning the given documents and a passthrough splitter.

        :param docs: The documents the patched load_documents should return.
        :return: The vector store returned by generate_vector_store and the load_documents mock.
        """
        loader: AsyncMock = AsyncMock(return_value=docs)
        with patch(SPLITTER_TARGET, new=self._passthrough_splitter_cls()):
            with patch.object(PdfRag, "load_documents", new=loader):
                store: Optional[VectorStore] = asyncio.run(self.tool.generate_vector_store(LOADER_ARGS))
        return store, loader

    def _build_and_save(self, docs: list[Document]) -> Optional[VectorStore]:
        """
        Run the cache-miss half of generate_vector_store: build an in-memory store from docs, then save it.

        :param docs: The documents the patched load_documents should return.
        :return: The vector store that was built (and offered to _save_vector_store).
        """
        # pylint: disable=protected-access
        with patch(SPLITTER_TARGET, new=self._passthrough_splitter_cls()):
            with patch.object(PdfRag, "load_documents", new=AsyncMock(return_value=docs)):
                store: Optional[VectorStore] = asyncio.run(
                    self.tool._create_new_vector_store(LOADER_ARGS, None, "in_memory")
                )
        asyncio.run(self.tool._save_vector_store(store, "in_memory"))
        return store

    def _dump_store(self, path: str, texts: list[str]) -> None:
        """
        Write a real InMemoryVectorStore holding the given texts to disk with the tool's embedding.

        :param path: Where to write the JSON file.
        :param texts: The texts to embed; an empty list writes an empty store.
        """
        store: InMemoryVectorStore = InMemoryVectorStore(embedding=self.tool.embeddings)
        if texts:
            store.add_texts(texts)
        store.dump(path)

    def _load_store(self, path: str) -> InMemoryVectorStore:
        """
        Load a saved InMemoryVectorStore from disk with the tool's embedding.

        :param path: The JSON file to load.
        :return: The loaded store.
        """
        return InMemoryVectorStore.load(path, self.tool.embeddings)

    def test_all_fail_run_does_not_create_file_and_warns(self) -> None:
        """An all-fail run returns an empty store without raising, writes no file, and warns naming the path."""
        path: str = self._configure_save()

        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            store, _ = self._generate([])

        # The issue's premise: zero documents build an EMPTY store rather than raising.
        self.assertIsInstance(store, InMemoryVectorStore)
        self.assertEqual(len(store.store), 0)
        self.assertFalse(os.path.exists(path))
        self.assertIn(path, "\n".join(logs.output))

    def test_all_fail_run_without_saving_configured_is_silent(self) -> None:
        """With persistence off (the setUp default) an all-sources-failed run neither warns nor writes a file."""
        path: str = self._store_path(self.tmp_dir)

        with self.assertNoLogs(LOGGER_NAME, level="WARNING"):
            store, _ = self._generate([])

        self.assertIsInstance(store, InMemoryVectorStore)
        self.assertEqual(len(store.store), 0)
        self.assertFalse(os.path.exists(path))

    def test_all_fail_run_leaves_existing_good_file_untouched(self) -> None:
        """An all-sources-failed build must not overwrite a previously saved good store (the issue's poisoning)."""
        path: str = self._configure_save()
        self._dump_store(path, ["Cached page one", "Cached page two"])
        with open(path, "rb") as handle:
            before: bytes = handle.read()

        # generate_vector_store would serve the good file from cache before ever loading the source, so the
        # only way an empty store can meet an existing file is through the build-then-save half it runs on a
        # cache miss; drive exactly that half here.
        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            self._build_and_save([])

        with open(path, "rb") as handle:
            after: bytes = handle.read()
        self.assertEqual(before, after)
        self.assertEqual(len(self._load_store(path).store), 2)
        self.assertIn(path, "\n".join(logs.output))

    def test_save_none_store_warns_and_writes_nothing(self) -> None:
        """_save_vector_store tolerates None: it warns like an empty store and never creates the file."""
        path: str = self._configure_save()

        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            asyncio.run(self.tool._save_vector_store(None, "in_memory"))  # pylint: disable=protected-access

        self.assertFalse(os.path.exists(path))
        self.assertIn(path, "\n".join(logs.output))

    def test_healthy_run_saves_store_with_all_chunks(self) -> None:
        """A healthy run with saving configured writes a file that loads back with one entry per chunk."""
        path: str = self._configure_save()

        store, _ = self._generate(GOOD_DOCS)

        self.assertIsNotNone(store)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(len(self._load_store(path).store), len(GOOD_DOCS))

    def test_empty_saved_store_is_ignored_and_rebuilt(self) -> None:
        """An empty saved store is ignored with a warning, the source is reloaded, and the good store replaces it."""
        path: str = self._configure_save()
        self._dump_store(path, [])
        self.assertEqual(len(self._load_store(path).store), 0)

        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            store, loader = self._generate(GOOD_DOCS)

        loader.assert_awaited_once()
        self.assertIsInstance(store, InMemoryVectorStore)
        self.assertEqual(len(store.store), len(GOOD_DOCS))
        self.assertIn(path, "\n".join(logs.output))
        # The rebuilt (non-empty) store overwrites the poisoned file on disk.
        self.assertEqual(len(self._load_store(path).store), len(GOOD_DOCS))

    def test_empty_saved_store_then_all_fail_rebuild_keeps_file_and_warns_twice(self) -> None:
        """An empty file on disk plus an all-fail rebuild fires both guards and leaves the file as it was."""
        path: str = self._configure_save()
        self._dump_store(path, [])
        self.assertEqual(os.path.getsize(path), EMPTY_STORE_FILE_SIZE)

        with self.assertLogs(LOGGER_NAME, level="WARNING") as logs:
            store, loader = self._generate([])

        # Load-side guard: the empty file is not trusted, so the source is consulted...
        loader.assert_awaited_once()
        # ...and the save-side guard: the equally empty rebuild is not written over it.
        self.assertIsInstance(store, InMemoryVectorStore)
        self.assertEqual(len(store.store), 0)
        self.assertEqual(os.path.getsize(path), EMPTY_STORE_FILE_SIZE)

        warnings_naming_path: list[str] = []
        for line in logs.output:
            if line.startswith("WARNING:") and path in line:
                warnings_naming_path.append(line)
        self.assertEqual(len(warnings_naming_path), 2, logs.output)

    def test_non_empty_saved_store_is_returned_without_reloading(self) -> None:
        """A non-empty saved store is served from the cache without touching the source."""
        path: str = self._configure_save()
        self._dump_store(path, ["Cached page one", "Cached page two", "Cached page three"])

        store, loader = self._generate(GOOD_DOCS)

        loader.assert_not_awaited()
        self.assertIsInstance(store, InMemoryVectorStore)
        self.assertEqual(len(store.store), 3)

    def test_is_empty_vector_store(self) -> None:
        """_is_empty_vector_store is True for None and empty in-memory stores, False otherwise."""
        # pylint: disable=protected-access
        empty: InMemoryVectorStore = InMemoryVectorStore(embedding=self.tool.embeddings)
        one: InMemoryVectorStore = InMemoryVectorStore.from_texts(["one text"], self.tool.embeddings)

        self.assertTrue(PdfRag._is_empty_vector_store(None))
        self.assertTrue(PdfRag._is_empty_vector_store(empty))
        self.assertFalse(PdfRag._is_empty_vector_store(one))
        # Non-in-memory stores cannot be counted cheaply and are never persisted, so they are never "empty".
        self.assertFalse(PdfRag._is_empty_vector_store(MagicMock(spec=VectorStore)))
