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


class TestWebFetch(TestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for the WebFetch coded tool.

    Covers async_invoke routing/truncation (with SafeFetch mocked so no network
    is touched) and the _validate_max_content_chars parameter validation.
    """

    def setUp(self):
        self.tool = WebFetch()
        self.sly_data: dict = {}

    def test_html_fetch_returns_correct_keys(self):
        """Tests that an HTML fetch returns url, final_url, content and retrieved_at keys."""
        with (
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None, "http://example.com"))
            ),
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="Hello world")),
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com"}, self.sly_data))

        self.assertEqual(result["url"], "http://example.com")
        self.assertEqual(result["final_url"], "http://example.com")
        self.assertEqual(result["content"], "Hello world")
        self.assertIn("retrieved_at", result)

    def test_405_prefetched_body_skips_fetch_text(self):
        """Tests that a prefetched body from the 405 GET fallback is used directly without calling fetch_text."""
        with (
            patch.object(
                SafeFetch,
                "get_content_type",
                new=AsyncMock(return_value=("text/html", "<p>prefetched</p>", "http://example.com")),
            ),
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="should not be called")) as mock_text,
        ):
            result = asyncio.run(self.tool.async_invoke({"url": "http://example.com"}, self.sly_data))

        mock_text.assert_not_called()
        self.assertIn("prefetched", result["content"])

    def test_pdf_by_content_type_calls_fetch_pdf(self):
        """Tests that an application/pdf content type routes to SafeFetch.fetch_pdf_text and not fetch_text."""
        with (
            patch.object(
                SafeFetch,
                "get_content_type",
                new=AsyncMock(return_value=("application/pdf", None, "http://example.com/file")),
            ),
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
                SafeFetch,
                "get_content_type",
                new=AsyncMock(return_value=("application/octet-stream", None, "http://example.com/report.pdf")),
            ),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF content")) as mock_pdf,
        ):
            asyncio.run(self.tool.async_invoke({"url": "http://example.com/report.pdf"}, self.sly_data))

        mock_pdf.assert_called_once()

    def test_redirected_pdf_is_classified_by_final_url(self) -> None:
        """A link without a .pdf suffix that redirects to a .pdf served as a generic download type is parsed as PDF.

        The suffix fallback must look at the URL the headers came from, not the
        requested one. The PDF fetch then starts from that final URL (one walk of the
        redirect chain, body and classification from the same place); the result keeps
        the requested URL as "url" and reports the fetched one as "final_url".
        """
        requested: str = "http://example.com/download?id=42"
        final: str = "http://cdn.example.com/files/report.pdf"
        with (
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("application/octet-stream", None, final))
            ),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF content")) as mock_pdf,
        ):
            result = asyncio.run(self.tool.async_invoke({"url": requested}, self.sly_data))

        mock_pdf.assert_awaited_once()
        self.assertEqual(mock_pdf.await_args.args[0], final)
        self.assertEqual(result["content"], "PDF content")
        self.assertEqual(result["url"], requested)
        self.assertEqual(result["final_url"], final)

    def test_redirected_text_page_is_fetched_from_final_url_with_domain_rules(self) -> None:
        """Tests that a redirected HTML page is fetched from the probe's final URL, with the domain rules forwarded.

        The redirect chain is walked once (by the probe), so the body comes from the
        same place the classification did. "url" stays the requested URL so the caller
        can match the result to its request; "final_url" says where the content came
        from. The allow-list must still reach the fetch, which re-validates final_url.
        """
        requested: str = "http://example.com/go"
        final: str = "http://www.example.com/landing"
        with (
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None, final))),
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="Landed")) as mock_text,
        ):
            result = asyncio.run(
                self.tool.async_invoke({"url": requested, "allowed_domains": ["example.com"]}, self.sly_data)
            )

        mock_text.assert_awaited_once()
        self.assertEqual(mock_text.await_args.args[0], final)
        self.assertEqual(mock_text.await_args.kwargs["allowed_domains"], ["example.com"])
        self.assertEqual(result["url"], requested)
        self.assertEqual(result["final_url"], final)
        self.assertEqual(result["content"], "Landed")

    def test_redirect_logs_redact_server_controlled_url(self) -> None:
        """Tests that a presigned redirect target is logged without its query, while the result keeps the full URL.

        The redirect target is chosen by the server and may carry a bearer token in its query
        string; log lines must not persist it. The agent still receives the full final URL,
        which it needs to cite the document.
        """
        requested: str = "http://example.com/report"
        final: str = "http://files.example.com/report.pdf?X-Amz-Signature=secret-token"
        with (
            patch.object(SafeFetch, "get_content_type", new=AsyncMock(return_value=("application/pdf", None, final))),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF content")),
        ):
            with self.assertLogs("WebFetch", level="INFO") as logs:
                result = asyncio.run(self.tool.async_invoke({"url": requested}, self.sly_data))

        joined: str = "\n".join(logs.output)
        self.assertNotIn("secret-token", joined)
        self.assertIn("redirected to http://files.example.com/report.pdf?[redacted]", joined)
        self.assertEqual(result["final_url"], final)

    def test_redirected_generic_download_without_pdf_suffix_is_unsupported(self) -> None:
        """A generic download type whose final URL has no .pdf suffix is still rejected, not guessed as PDF."""
        with patch.object(
            SafeFetch,
            "get_content_type",
            new=AsyncMock(return_value=("application/octet-stream", None, "http://cdn.example.com/files/blob")),
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool.async_invoke({"url": "http://example.com/download?id=43"}, self.sly_data))
        self.assertIn("unsupported_content_type", str(ctx.exception))

    def test_pdf_not_a_pdf_propagates_as_value_error(self) -> None:
        """A not_a_pdf refusal from fetch_pdf_text surfaces as ValueError with its prefix intact.

        not_a_pdf is a documented error of this tool: a link classified as PDF whose
        body carries no "%PDF-" header (an HTML error page served as application/pdf)
        must not be reported as a generic url_not_accessible parse failure.
        """
        refusal = ValueError("not_a_pdf: 'http://example.com/file.pdf' has no PDF header in its first 1024 bytes.")
        with (
            patch.object(
                SafeFetch,
                "get_content_type",
                new=AsyncMock(return_value=("application/pdf", None, "http://example.com/file.pdf")),
            ),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(side_effect=refusal)) as mock_pdf,
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool.async_invoke({"url": "http://example.com/file.pdf"}, self.sly_data))

        mock_pdf.assert_awaited_once()
        self.assertIn("not_a_pdf", str(ctx.exception))

    def test_unsupported_content_type_raises(self):
        """Tests that an unsupported content type raises ValueError with unsupported_content_type."""
        for content_type in ("image/png", "image/svg+xml"):
            with self.subTest(content_type=content_type):
                with patch.object(
                    SafeFetch,
                    "get_content_type",
                    new=AsyncMock(return_value=(content_type, None, "http://example.com/image")),
                ):
                    with self.assertRaises(ValueError) as ctx:
                        asyncio.run(self.tool.async_invoke({"url": "http://example.com/image"}, self.sly_data))
                self.assertIn("unsupported_content_type", str(ctx.exception))

    def test_uppercase_pdf_content_type_routes_to_pdf(self):
        """Tests that a mixed-case 'Application/PDF' header still routes to PDF parsing, not rejection."""
        with (
            patch.object(
                SafeFetch,
                "get_content_type",
                new=AsyncMock(return_value=("Application/PDF", None, "http://example.com/file")),
            ),
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
                    patch.object(
                        SafeFetch,
                        "get_content_type",
                        new=AsyncMock(return_value=(content_type, None, "http://example.com/doc")),
                    ),
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
            SafeFetch,
            "get_content_type",
            new=AsyncMock(return_value=('image/png; profile="text/plain"', None, "http://example.com/img")),
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool.async_invoke({"url": "http://example.com/img"}, self.sly_data))
        self.assertIn("unsupported_content_type", str(ctx.exception))

    def test_content_truncated_to_max_content_chars(self):
        """Tests that fetched content is truncated to the specified max_content_chars limit."""
        long_text = "x" * 1000
        with (
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/plain", None, "http://example.com"))
            ),
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value=long_text)),
        ):
            result = asyncio.run(
                self.tool.async_invoke({"url": "http://example.com", "max_content_chars": 100}, self.sly_data)
            )
        self.assertEqual(len(result["content"]), 100)

    def test_domain_rules_forwarded_to_text_path(self) -> None:
        """Tests that allowed_domains / blocked_domains reach get_content_type and fetch_text as keyword args.

        SafeFetch re-validates every redirect hop with the rules it is given; if
        WebFetch validated only the agent's URL and called SafeFetch without them, an
        open redirect on an allowed domain could land on a blocked or non-allowed one.
        """
        allowed = ["example.com"]
        blocked = ["example.org"]
        with (
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/html", None, "http://example.com"))
            ) as mock_ct,
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="Hello")) as mock_text,
        ):
            asyncio.run(
                self.tool.async_invoke(
                    {"url": "http://example.com", "allowed_domains": allowed, "blocked_domains": blocked},
                    self.sly_data,
                )
            )

        expected_kwargs = {"allowed_domains": allowed, "blocked_domains": blocked}
        # Positional args are (url, session); the session is an object created inside
        # async_invoke, so only the URL and the arity can be pinned from out here.
        self.assertEqual(mock_ct.await_args.args[0], "http://example.com")
        self.assertEqual(len(mock_ct.await_args.args), 2)
        self.assertEqual(mock_ct.await_args.kwargs, expected_kwargs)
        self.assertEqual(mock_text.await_args.kwargs, expected_kwargs)

    def test_domain_rules_forwarded_to_pdf_path(self) -> None:
        """Tests that allowed_domains / blocked_domains reach fetch_pdf_text as keyword args on the PDF route."""
        allowed = ["example.com"]
        blocked = ["example.org"]
        with (
            patch.object(
                SafeFetch,
                "get_content_type",
                new=AsyncMock(return_value=("application/pdf", None, "http://example.com/file.pdf")),
            ),
            patch.object(SafeFetch, "fetch_pdf_text", new=AsyncMock(return_value="PDF content")) as mock_pdf,
        ):
            asyncio.run(
                self.tool.async_invoke(
                    {"url": "http://example.com/file.pdf", "allowed_domains": allowed, "blocked_domains": blocked},
                    self.sly_data,
                )
            )

        self.assertEqual(mock_pdf.await_args.kwargs, {"allowed_domains": allowed, "blocked_domains": blocked})

    def test_absent_domain_rules_forwarded_as_none(self) -> None:
        """Tests that omitted domain rules are forwarded as None so SafeFetch applies no domain policy to hops."""
        with (
            patch.object(
                SafeFetch, "get_content_type", new=AsyncMock(return_value=("text/plain", None, "http://example.com"))
            ) as mock_ct,
            patch.object(SafeFetch, "fetch_text", new=AsyncMock(return_value="Hello")) as mock_text,
        ):
            asyncio.run(self.tool.async_invoke({"url": "http://example.com"}, self.sly_data))

        self.assertEqual(mock_ct.await_args.kwargs, {"allowed_domains": None, "blocked_domains": None})
        self.assertEqual(mock_text.await_args.kwargs, {"allowed_domains": None, "blocked_domains": None})

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
