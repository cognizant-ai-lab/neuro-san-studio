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
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from coded_tools.tools.web_fetch import WebFetch


class TestAsyncInvoke(TestCase):
    """Integration-level tests for WebFetch.async_invoke with mocked helpers."""

    def setUp(self):
        self.tool = WebFetch()
        self.sly_data: dict = {}

    def test_html_fetch_returns_correct_keys(self):
        """Tests that fetching an HTML page returns a result with url, content, and retrieved_at keys."""
        with (
            patch.object(self.tool, "_get_content_type", new=AsyncMock(return_value=("text/html", None))),
            patch.object(self.tool, "_fetch_text", new=AsyncMock(return_value="Hello world")),
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com"}, self.sly_data))

        self.assertEqual(result["url"], "http://example.com")
        self.assertEqual(result["content"], "Hello world")
        self.assertIn("retrieved_at", result)

    def test_405_prefetched_body_skips_fetch_text(self):
        """Tests that a prefetched body from the 405 GET fallback is used directly without calling _fetch_text."""
        with (
            patch.object(
                self.tool, "_get_content_type", new=AsyncMock(return_value=("text/html", "<p>prefetched</p>"))
            ),
            patch.object(self.tool, "_fetch_text", new=AsyncMock(return_value="should not be called")) as mock_text,
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com"}, self.sly_data))

        mock_text.assert_not_called()
        self.assertIn("prefetched", result["content"])

    def test_pdf_by_content_type_calls_fetch_pdf(self):
        """Tests that an application/pdf content type routes to _fetch_pdf and not _fetch_text."""
        with (
            patch.object(self.tool, "_get_content_type", new=AsyncMock(return_value=("application/pdf", None))),
            patch.object(self.tool, "_fetch_pdf", new=AsyncMock(return_value="PDF content")) as mock_pdf,
            patch.object(self.tool, "_fetch_text", new=AsyncMock(return_value="should not be called")) as mock_text,
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com/file"}, self.sly_data))

        mock_pdf.assert_called_once()
        mock_text.assert_not_called()
        self.assertEqual(result["content"], "PDF content")

    def test_pdf_by_url_extension_calls_fetch_pdf(self):
        """Tests that a .pdf URL extension routes to _fetch_pdf regardless of content type."""
        with (
            patch.object(
                self.tool, "_get_content_type", new=AsyncMock(return_value=("application/octet-stream", None))
            ),
            patch.object(self.tool, "_fetch_pdf", new=AsyncMock(return_value="PDF content")) as mock_pdf,
        ):
            asyncio.run(self.tool.async_invoke({"url": "http://example.com/report.pdf"}, self.sly_data))

        mock_pdf.assert_called_once()

    def test_unsupported_content_type_raises(self):
        """Tests that an unsupported content type raises ValueError with unsupported_content_type."""
        with patch.object(self.tool, "_get_content_type", new=AsyncMock(return_value=("image/png", None))):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool.async_invoke({"url": "http://example.com/img.png"}, self.sly_data))
        self.assertIn("unsupported_content_type", str(ctx.exception))

    def test_content_truncated_to_max_content_chars(self):
        """Tests that fetched content is truncated to the specified max_content_chars limit."""
        long_text = "x" * 1000
        with (
            patch.object(self.tool, "_get_content_type", new=AsyncMock(return_value=("text/plain", None))),
            patch.object(self.tool, "_fetch_text", new=AsyncMock(return_value=long_text)),
        ):
            result = asyncio.run(
                self.tool.async_invoke({"url": "http://example.com", "max_content_chars": 100}, self.sly_data)
            )
        self.assertEqual(len(result["content"]), 100)

    def test_invalid_url_raises_before_network_call(self):
        """Tests that an invalid URL scheme raises ValueError before any network call is made."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"url": "ftp://example.com"}, self.sly_data))
        self.assertIn("invalid_input", str(ctx.exception))

    def test_private_ip_raises_before_network_call(self):
        """Tests that a private IP address raises ValueError before any network call is made."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"url": "http://192.168.1.1/secret"}, self.sly_data))
        self.assertIn("url_not_allowed", str(ctx.exception))
