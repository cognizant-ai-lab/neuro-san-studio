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

"""Tests for the PDF RAG coded tool's SafeFetch-backed document loading."""

import asyncio
import os
import tempfile
from typing import Any
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from aiohttp import ClientError

from neuro_san_studio.coded_tools.pdf_rag import PdfRag
from neuro_san_studio.coded_tools.utils.pdf_utils import PdfUtils
from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch

PDF_BYTES = b"%PDF-1.4 fake body"
PAGE_TEXTS = ["Page one text", "Page two text"]


def make_session_cm() -> MagicMock:
    """
    Build an async-context-manager mock standing in for SafeFetch.open_session().

    :return: A MagicMock usable as ``async with`` that yields a mock session.
    """
    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    return session_cm


class TestPdfRag(TestCase):
    """Unit tests for PdfRag: SSRF-hardened remote loading, local paths, input guards."""

    def setUp(self):
        # Bypass BaseRag.__init__, which instantiates OpenAIEmbeddings and therefore
        # requires an OPENAI_API_KEY; these tests never embed or build a store.
        self.tool = object.__new__(PdfRag)

    def _load(self, urls: list[str]) -> list:
        """
        Run load_documents with the given items against mocked session and parsing.

        :param urls: The list of URLs/paths to pass to load_documents.
        :return: The list of loaded Documents.
        """
        return asyncio.run(self.tool.load_documents({"urls": urls}))

    def test_remote_pdf_produces_per_page_documents(self):
        """A downloaded PDF yields one Document per page with source/page/total_pages metadata."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=PDF_BYTES)) as mock_dl,
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=PAGE_TEXTS) as mock_parse,
        ):
            docs = self._load(["http://example.com/report.pdf"])

        mock_dl.assert_awaited_once()
        mock_parse.assert_called_once_with(PDF_BYTES)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].page_content, "Page one text")
        self.assertEqual(docs[0].metadata, {"source": "http://example.com/report.pdf", "page": 0, "total_pages": 2})
        self.assertEqual(docs[1].metadata["page"], 1)

    def test_local_path_reads_file_without_network(self):
        """A local file path is read from disk; no download is attempted."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(PDF_BYTES)
            local_path = handle.name
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
                patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock()) as mock_dl,
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["local text"]) as mock_parse,
            ):
                docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        mock_dl.assert_not_awaited()
        # The parser received the actual bytes read from disk.
        mock_parse.assert_called_once_with(PDF_BYTES)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], local_path)

    def test_private_ip_url_skipped_without_download(self):
        """A URL that fails SSRF validation is skipped and never downloaded; others still load."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=PDF_BYTES)) as mock_dl,
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]),
        ):
            # validate_url is NOT mocked, so the private-IP URL is rejected for real.
            docs = self._load(["http://192.168.1.1/internal.pdf", "http://example.com/good.pdf"])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/good.pdf")
        mock_dl.assert_awaited_once()  # only the allowed URL reached the network

    def test_failed_download_does_not_discard_other_pdfs(self):
        """One unreachable PDF is logged and skipped; the rest of the corpus survives."""

        async def download(url: str, _session: Any) -> bytes:
            """Return PDF bytes, raising ClientError for any URL containing 'bad'."""
            if "bad" in url:
                raise ClientError("url_not_accessible: connection reset")
            return PDF_BYTES

        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(side_effect=download)),
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]),
        ):
            docs = self._load(["http://bad.example.com/a.pdf", "http://example.com/good.pdf"])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/good.pdf")

    def test_parse_failure_skips_only_that_item(self):
        """A pypdf parse error skips that item instead of aborting the whole load."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=b"not a pdf")),
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", side_effect=ValueError("bad pdf")),
        ):
            docs = self._load(["http://example.com/broken.pdf"])

        self.assertEqual(docs, [])  # skipped, not raised

    def test_missing_local_file_is_skipped(self):
        """A nonexistent local path is logged and skipped rather than raising."""
        with patch.object(SafeFetch, "open_session", return_value=make_session_cm()):
            docs = self._load(["/nonexistent/dir/missing.pdf"])

        self.assertEqual(docs, [])

    def test_empty_url_list_returns_empty_without_session(self):
        """An empty item list returns [] without ever opening a network session."""
        with patch.object(SafeFetch, "open_session") as mock_session:
            docs = self._load([])

        self.assertEqual(docs, [])
        mock_session.assert_not_called()

    def test_all_items_skipped_returns_clear_message(self):
        """When nothing is ingested, async_invoke returns a clear message, not an empty list."""
        with (
            patch.object(PdfRag, "generate_vector_store", new=AsyncMock(return_value=MagicMock())),
            patch.object(PdfRag, "query_vectorstore", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(self.tool.async_invoke({"query": "q", "urls": ["http://example.com/x.pdf"]}, {}))

        self.assertIn("No content could be retrieved", result)

    def test_missing_query_or_urls_returns_error_without_network(self):
        """async_invoke reports missing inputs before any session is opened."""
        with patch.object(SafeFetch, "open_session") as mock_session:
            no_query = asyncio.run(self.tool.async_invoke({"urls": ["http://example.com/x.pdf"]}, {}))
            no_urls = asyncio.run(self.tool.async_invoke({"query": "hello"}, {}))

        self.assertIn("Missing required input: 'query'", no_query)
        self.assertIn("Missing required input: 'urls'", no_urls)
        mock_session.assert_not_called()
