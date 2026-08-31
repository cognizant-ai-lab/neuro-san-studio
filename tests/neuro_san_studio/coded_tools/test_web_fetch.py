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

from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch
from neuro_san_studio.coded_tools.web_fetch import MAX_CHARS
from neuro_san_studio.coded_tools.web_fetch import WebFetch


class TestWebFetch(TestCase):
    """Unit tests for the WebFetch coded tool.

    Covers async_invoke routing/truncation (with SafeFetch mocked so no network
    is touched) and the _validate_max_content_chars parameter validation.
    """

    def setUp(self):
        self.tool = WebFetch()
        self.sly_data: dict = {}

    def test_html_fetch_returns_correct_keys(self):
        """Tests that fetching an HTML page returns a result with url, content, and retrieved_at keys."""
        with (
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None))),
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="Hello world")),
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com"}, self.sly_data))

        self.assertEqual(result["url"], "http://example.com")
        self.assertEqual(result["content"], "Hello world")
        self.assertIn("retrieved_at", result)

    def test_405_prefetched_body_skips_fetch_text(self):
        """Tests that a prefetched body from the 405 GET fallback is used directly without calling fetch_text."""
        with (
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", "<p>prefetched</p>"))
            ),
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="should not be called")) as mock_text,
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com"}, self.sly_data))

        mock_text.assert_not_called()
        self.assertIn("prefetched", result["content"])

    def test_pdf_by_content_type_calls_fetch_pdf(self):
        """Tests that an application/pdf content type routes to SafeFetch.fetch_pdf_text and not fetch_text."""
        with (
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("application/pdf", None))),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF content")) as mock_pdf,
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="should not be called")) as mock_text,
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com/file"}, self.sly_data))

        mock_pdf.assert_called_once()
        mock_text.assert_not_called()
        self.assertEqual(result["content"], "PDF content")

    def test_pdf_by_url_extension_calls_fetch_pdf(self):
        """Tests that a .pdf URL extension routes to fetch_pdf_text when the type is a generic download type."""
        with (
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("application/octet-stream", None))
            ),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF content")) as mock_pdf,
        ):
            asyncio.run(self.tool.async_invoke({"url": "http://example.com/report.pdf"}, self.sly_data))

        mock_pdf.assert_called_once()

    def test_unsupported_content_type_raises(self):
        """Tests that an unsupported content type raises ValueError with unsupported_content_type."""
        for content_type in ("image/png", "image/svg+xml"):
            with self.subTest(content_type=content_type):
                with patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=(content_type, None))):
                    with self.assertRaises(ValueError) as ctx:
                        asyncio.run(self.tool.async_invoke({"url": "http://example.com/image"}, self.sly_data))
                self.assertIn("unsupported_content_type", str(ctx.exception))

    def test_uppercase_pdf_content_type_routes_to_pdf(self):
        """Tests that a mixed-case 'Application/PDF' header still routes to PDF parsing, not rejection."""
        with (
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("Application/PDF", None))),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF content")) as mock_pdf,
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com/file"}, self.sly_data))
        mock_pdf.assert_called_once()
        self.assertEqual(result["content"], "PDF content")

    def test_supported_text_content_types_route_to_text_fetch(self):
        """Tests that each vetted textual media type is fetched through the text path."""
        content_types = (
            "TEXT/HTML",
            "application/atom+xml",
            "application/json",
            "application/rss+xml",
            "application/xml",
            "text/csv",
            "text/markdown",
            "text/xml",
        )

        for content_type in content_types:
            with self.subTest(content_type=content_type):
                with (
                    patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=(content_type, None))),
                    patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="readable text")) as mock_text,
                ):
                    result = asyncio.run(self.tool.async_invoke({"url": "http://example.com/doc"}, self.sly_data))

                mock_text.assert_awaited_once()
                self.assertEqual(result["content"], "readable text")

    def test_supported_token_in_parameter_still_unsupported(self):
        """Tests that a supported token appearing only in a parameter does not make a type supported.

        'image/png; profile="text/plain"' reduces to base type image/png and must be
        rejected, guarding against the old substring match that accepted it.
        """
        with patch.object(
            SafeFetch, "get_content_type", new=AsyncMock(return_value=('image/png; profile="text/plain"', None))
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool.async_invoke({"url": "http://example.com/img"}, self.sly_data))
        self.assertIn("unsupported_content_type", str(ctx.exception))

    def test_content_truncated_to_max_content_chars(self):
        """Tests that fetched content is truncated to the specified max_content_chars limit."""
        long_text = "x" * 1000
        with (
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/plain", None))),
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value=long_text)),
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

    def _call(self, args):
        """Invoke _validate_max_content_chars with the given args dict and return the result."""
        return self.tool._validate_max_content_chars(args)  # pylint: disable=protected-access

    def test_default_value_used_when_absent(self):
        """Tests that the default MAX_CHARS value is returned when max_content_chars is absent."""
        self.assertEqual(self._call({}), MAX_CHARS)

    def test_none_falls_back_to_default(self):
        """Tests that an explicit None falls back to MAX_CHARS instead of raising."""
        self.assertEqual(self._call({"max_content_chars": None}), MAX_CHARS)

    def test_valid_positive_int(self):
        """Tests that a valid positive integer is accepted and returned as-is."""
        self.assertEqual(self._call({"max_content_chars": 500}), 500)

    def test_zero_raises(self):
        """Tests that zero is rejected as non-positive rather than silently defaulting."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": 0})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_negative_raises(self):
        """Tests that a negative value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": -1})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_bool_raises(self):
        """Tests that a bool (True/False) is rejected rather than treated as 1/0."""
        for value in (True, False):
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as ctx:
                    self._call({"max_content_chars": value})
                self.assertIn("invalid_input", str(ctx.exception))

    def test_string_raises(self):
        """Tests that a string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": "1000"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_float_raises(self):
        """Tests that a float value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": 1000.0})
        self.assertIn("invalid_input", str(ctx.exception))
