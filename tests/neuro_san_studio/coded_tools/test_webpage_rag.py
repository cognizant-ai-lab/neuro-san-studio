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

"""Tests for the webpage RAG coded tool's SafeFetch-backed document loading."""

import asyncio
from typing import Any
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from aiohttp import ClientError

from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch
from neuro_san_studio.coded_tools.webpage_rag import WebpageRag

HTML_PAGE = (
    '<html lang="en"><head><title>My Title</title>'
    '<meta name="description" content="A test page."><style>body{}</style></head>'
    "<body><p>Hello world</p><script>alert(1)</script></body></html>"
)


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


class TestWebpageRag(TestCase):
    """Unit tests for WebpageRag: SSRF-hardened loading, PDF/HTML routing, input guards."""

    def setUp(self):
        # Bypass BaseRag.__init__, which instantiates OpenAIEmbeddings and therefore
        # requires an OPENAI_API_KEY; these tests never embed or build a store.
        self.tool = object.__new__(WebpageRag)

    def _load(self, urls: list[str]) -> list:
        """
        Run load_documents with the given URLs against mocked session and bodies.

        :param urls: The list of URLs to pass to load_documents.
        :return: The list of loaded Documents.
        """
        return asyncio.run(self.tool.load_documents({"urls": urls}))

    def test_html_document_metadata_shape(self):
        """An HTML page is stripped to text and keeps source/title/description/language metadata."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None))),
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value=HTML_PAGE)),
        ):
            docs = self._load(["http://example.com/page"])

        self.assertEqual(len(docs), 1)
        self.assertIn("Hello world", docs[0].page_content)
        self.assertNotIn("alert", docs[0].page_content)  # <script> stripped
        self.assertEqual(
            docs[0].metadata,
            {
                "source": "http://example.com/page",
                "title": "My Title",
                "description": "A test page.",
                "language": "en",
            },
        )

    def test_missing_metadata_fields_are_omitted(self):
        """A page without title/description/language yields metadata with only the source."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None))),
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value="<html><body>plain</body></html>")),
        ):
            docs = self._load(["http://example.com"])

        self.assertEqual(docs[0].metadata, {"source": "http://example.com"})

    def test_pdf_content_type_routes_to_fetch_pdf(self):
        """An application/pdf response is parsed via fetch_pdf_text, not the HTML path."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("application/pdf", None))),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="Extracted PDF body")) as mock_pdf,
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value=HTML_PAGE)) as mock_raw,
        ):
            docs = self._load(["http://example.com/doc"])

        mock_pdf.assert_awaited_once()
        mock_raw.assert_not_awaited()  # HTML stripper must not touch a PDF
        self.assertEqual(docs[0].page_content, "Extracted PDF body")
        self.assertEqual(docs[0].metadata, {"source": "http://example.com/doc"})

    def test_pdf_url_suffix_routes_to_fetch_pdf(self):
        """A .pdf URL is parsed as PDF when the server only declares a generic download type."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("application/octet-stream", None))
            ),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF from suffix")) as mock_pdf,
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value=HTML_PAGE)) as mock_raw,
        ):
            docs = self._load(["http://example.com/report.pdf"])

        mock_pdf.assert_awaited_once()
        mock_raw.assert_not_awaited()
        self.assertEqual(docs[0].page_content, "PDF from suffix")

    def test_unsupported_binary_type_is_skipped(self):
        """A binary content type (image) is skipped without decoding it as text or PDF."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("image/png", None))),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="nope")) as mock_pdf,
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value="nope")) as mock_raw,
        ):
            docs = self._load(["http://example.com/img.png"])

        self.assertEqual(docs, [])
        mock_pdf.assert_not_awaited()
        mock_raw.assert_not_awaited()

    def test_prefetched_body_avoids_second_fetch(self):
        """A body prefetched during the 405 GET fallback is reused without a second fetch_raw."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", HTML_PAGE))),
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value="should not be used")) as mock_raw,
        ):
            docs = self._load(["http://example.com/page"])

        mock_raw.assert_not_awaited()
        self.assertIn("Hello world", docs[0].page_content)

    def test_disallowed_url_is_skipped_without_fetch(self):
        """A URL that fails SSRF validation is skipped and never fetched; others still load."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None))),
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value=HTML_PAGE)) as mock_raw,
        ):
            # validate_url is NOT mocked, so the private-IP URL is rejected for real.
            docs = self._load(["http://192.168.1.1/internal", "http://example.com/page"])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/page")
        mock_raw.assert_awaited_once()  # only the allowed URL reached the network

    def test_failed_download_does_not_discard_other_pages(self):
        """One unreachable page is logged and skipped; the rest of the corpus survives."""

        async def fetch_raw(url: str, _session: Any) -> str:
            """Return a page body, raising ClientError for any URL containing 'bad'."""
            if "bad" in url:
                raise ClientError("url_not_accessible: connection reset")
            return HTML_PAGE

        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None))),
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(side_effect=fetch_raw)),
        ):
            docs = self._load(["http://bad.example.com", "http://example.com/good"])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/good")

    def test_empty_content_type_is_treated_as_text(self):
        """A missing/empty Content-Type is loaded as text rather than skipped (WebBaseLoader parity)."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("", None))),
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value=HTML_PAGE)) as mock_raw,
        ):
            docs = self._load(["http://example.com/page"])

        mock_raw.assert_awaited_once()
        self.assertEqual(len(docs), 1)
        self.assertIn("Hello world", docs[0].page_content)

    def test_parse_failure_skips_only_that_url(self):
        """A parse error in _to_document skips that URL instead of aborting the whole load."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None))),
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value=HTML_PAGE)),
            patch.object(WebpageRag, "_to_document", side_effect=RecursionError("boom")),
        ):
            docs = self._load(["http://example.com/page"])

        self.assertEqual(docs, [])  # skipped, not raised

    def test_all_urls_skipped_returns_clear_message(self):
        """When nothing is ingested, async_invoke returns a clear message, not an empty list."""
        with (
            patch.object(WebpageRag, "generate_vector_store", new=AsyncMock(return_value=MagicMock())),
            patch.object(WebpageRag, "query_vectorstore", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(self.tool.async_invoke({"query": "q", "urls": ["http://example.com"]}, {}))

        self.assertIn("No content could be retrieved", result)

    def test_empty_url_list_returns_empty_without_session(self):
        """An empty URL list returns [] without ever opening a network session."""
        with patch.object(SafeFetch, "open_session") as mock_session:
            docs = self._load([])

        self.assertEqual(docs, [])
        mock_session.assert_not_called()

    def test_bare_string_urls_is_treated_as_single_url(self):
        """A single URL passed as a bare string loads as one page, not one fetch per character."""
        with (
            patch.object(SafeFetch, "open_session", return_value=make_session_cm()),
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None))) as mock_ct,
            patch.object(SafeFetch, "fetch_raw", new=AsyncMock(return_value=HTML_PAGE)),
        ):
            docs = asyncio.run(self.tool.load_documents({"urls": "http://example.com/page"}))

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/page")
        # Exactly one URL was probed — not one per character of the string.
        mock_ct.assert_awaited_once()

    def test_missing_query_or_urls_returns_error_without_network(self):
        """async_invoke reports missing inputs before any session is opened."""
        with patch.object(SafeFetch, "open_session") as mock_session:
            no_query = asyncio.run(self.tool.async_invoke({"urls": ["http://example.com"]}, {}))
            no_urls = asyncio.run(self.tool.async_invoke({"query": "hello"}, {}))

        self.assertIn("Missing required input: 'query'", no_query)
        self.assertIn("Missing required input: 'urls'", no_urls)
        mock_session.assert_not_called()
