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
from io import BytesIO
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from aiohttp import ClientError
from aiohttp import ClientResponseError
from pypdf import PdfWriter

from neuro_san_studio.coded_tools.web_fetch import MAX_RESPONSE_BYTES
from neuro_san_studio.coded_tools.web_fetch import WebFetch
from tests.neuro_san_studio.coded_tools.web_fetch.helpers import make_response_error
from tests.neuro_san_studio.coded_tools.web_fetch.helpers import make_stream_session


def make_pdf_bytes(pages: int = 1) -> bytes:
    """Build a minimal valid PDF with the given number of blank pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestFetchPdf(TestCase):
    """Unit tests for WebFetch._fetch_pdf."""

    def setUp(self):
        self.tool = WebFetch()

    def _call(self, url: str, session) -> str:
        """Invoke _fetch_pdf with the given URL and session."""
        return asyncio.run(self.tool._fetch_pdf(url, session))  # pylint: disable=protected-access

    def test_returns_joined_page_text(self):
        """Tests that text from all PDF pages is joined into a single newline-separated string."""
        pages = [MagicMock(), MagicMock()]
        pages[0].extract_text.return_value = "Page one"
        pages[1].extract_text.return_value = "Page two"
        mock_reader = MagicMock()
        mock_reader.pages = pages

        with (
            patch.object(self.tool, "_download_pdf_bytes", new=AsyncMock(return_value=b"%PDF-fake")),
            patch("neuro_san_studio.coded_tools.web_fetch.PdfReader", return_value=mock_reader),
        ):
            result = self._call("http://example.com/doc.pdf", MagicMock())

        self.assertEqual(result, "Page one\nPage two")

    def test_none_page_text_coerced_to_empty(self):
        """Tests that a page whose extract_text() returns None is treated as empty text."""
        pages = [MagicMock(), MagicMock(), MagicMock()]
        pages[0].extract_text.return_value = "Page one"
        pages[1].extract_text.return_value = None
        pages[2].extract_text.return_value = "Page three"
        mock_reader = MagicMock()
        mock_reader.pages = pages

        with (
            patch.object(self.tool, "_download_pdf_bytes", new=AsyncMock(return_value=b"%PDF-fake")),
            patch("neuro_san_studio.coded_tools.web_fetch.PdfReader", return_value=mock_reader),
        ):
            result = self._call("http://example.com/doc.pdf", MagicMock())

        self.assertEqual(result, "Page one\n\nPage three")

    def test_real_pdf_bytes_parse_successfully(self):
        """Tests that genuine PDF bytes are parsed by real pypdf without errors."""
        data = make_pdf_bytes(pages=2)
        with patch.object(self.tool, "_download_pdf_bytes", new=AsyncMock(return_value=data)):
            result = self._call("http://example.com/doc.pdf", MagicMock())
        self.assertIsInstance(result, str)

    def test_invalid_pdf_bytes_raise_client_error_with_prefix(self):
        """Tests that unparseable PDF bytes raise ClientError with url_not_accessible prefix."""
        with patch.object(self.tool, "_download_pdf_bytes", new=AsyncMock(return_value=b"not a pdf")):
            with self.assertRaises(ClientError) as ctx:
                self._call("http://example.com/doc.pdf", MagicMock())
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_download_uses_provided_session(self):
        """Tests that the PDF download goes through the session passed by async_invoke."""
        data = make_pdf_bytes()
        session, _ = make_stream_session([data])
        self._call("http://example.com/doc.pdf", session)
        session.get.assert_called_once()
        self.assertEqual(session.get.call_args.args[0], "http://example.com/doc.pdf")
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])


class TestDownloadPdfBytes(TestCase):
    """Unit tests for WebFetch._download_pdf_bytes."""

    def setUp(self):
        self.tool = WebFetch()

    def _call(self, session, url: str = "http://example.com/doc.pdf") -> bytes:
        """Invoke _download_pdf_bytes with the given mocked session."""
        return asyncio.run(self.tool._download_pdf_bytes(url, session))  # pylint: disable=protected-access

    def test_joins_streamed_chunks(self):
        """Tests that streamed chunks are concatenated into the full body."""
        session, _ = make_stream_session([b"%PDF", b"-1.4", b" body"])
        self.assertEqual(self._call(session), b"%PDF-1.4 body")

    def test_redirect_raises_url_not_allowed(self):
        """Tests that a 3xx response raises ValueError with url_not_allowed."""
        session, _ = make_stream_session([], status=302)
        with self.assertRaises(ValueError) as ctx:
            self._call(session)
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_429_maps_to_too_many_requests(self):
        """Tests that HTTP 429 raises ClientResponseError with too_many_requests prefix."""
        session, _ = make_stream_session([], status=429, raise_for_status_exc=make_response_error(429))
        with self.assertRaises(ClientResponseError) as ctx:
            self._call(session)
        self.assertIn("too_many_requests", str(ctx.exception))

    def test_http_error_maps_to_url_not_accessible(self):
        """Tests that a non-2xx response raises ClientResponseError with url_not_accessible prefix."""
        session, _ = make_stream_session([], status=500, raise_for_status_exc=make_response_error(500))
        with self.assertRaises(ClientResponseError) as ctx:
            self._call(session)
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_content_length_header_over_limit_raises(self):
        """Tests that a Content-Length header above MAX_RESPONSE_BYTES raises response_too_large."""
        session, _ = make_stream_session([b"x"], content_length=MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(ValueError) as ctx:
            self._call(session)
        self.assertIn("response_too_large", str(ctx.exception))

    def test_streamed_body_over_limit_raises(self):
        """Tests that a body exceeding MAX_RESPONSE_BYTES on the wire raises response_too_large.

        This covers the server-lies-about-Content-Length case: the header is absent,
        so only the running byte count can enforce the cap.
        """
        session, _ = make_stream_session([b"x" * 8, b"y" * 8])
        with patch("neuro_san_studio.coded_tools.web_fetch.MAX_RESPONSE_BYTES", 10):
            with self.assertRaises(ValueError) as ctx:
                self._call(session)
        self.assertIn("response_too_large", str(ctx.exception))

    def test_connection_error_wrapped_as_url_not_accessible(self):
        """Tests that a connection-level ClientError is wrapped with url_not_accessible prefix."""
        session = MagicMock()
        session.get = MagicMock(side_effect=ClientError("connection reset"))
        with self.assertRaises(ClientError) as ctx:
            self._call(session)
        self.assertIn("url_not_accessible", str(ctx.exception))
