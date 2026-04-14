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
from unittest.mock import MagicMock

from aiohttp import ClientError
from aiohttp import ClientResponseError

from coded_tools.tools.web_fetch import WebFetch

from .helpers import make_get_response
from .helpers import make_response_error


class TestFetchText(TestCase):
    """Unit tests for WebFetch._fetch_text."""

    def setUp(self):
        self.tool = WebFetch()

    def test_plain_text_returned_as_is(self):
        """Tests that plain text body content is returned unchanged."""
        session, _ = make_get_response(body="just plain text")
        result = asyncio.run(self.tool._fetch_text("http://example.com", session))  # pylint: disable=protected-access
        self.assertEqual(result, "just plain text")

    def test_html_is_stripped(self):
        """Tests that HTML tags, scripts, and styles are stripped from the fetched content."""
        html = "<html><head><style>body{}</style></head><body><p>Hello</p><script>alert(1)</script></body></html>"
        session, _ = make_get_response(body=html)
        result = asyncio.run(self.tool._fetch_text("http://example.com", session))  # pylint: disable=protected-access
        self.assertIn("Hello", result)
        self.assertNotIn("<p>", result)
        self.assertNotIn("alert", result)
        self.assertNotIn("body{}", result)

    def test_non_2xx_raises_client_response_error_with_prefix(self):
        """Tests that a non-2xx HTTP error raises ClientResponseError with url_not_accessible prefix."""
        exc = make_response_error(503)
        session, _ = make_get_response(status=503, raise_for_status_exc=exc)
        with self.assertRaises(ClientResponseError) as ctx:
            asyncio.run(self.tool._fetch_text("http://example.com", session))  # pylint: disable=protected-access
        self.assertIn("url_not_accessible", ctx.exception.message)

    def test_429_raises_with_too_many_requests_prefix(self):
        """Tests that a 429 response raises ClientResponseError with too_many_requests prefix."""
        exc = make_response_error(429)
        session, _ = make_get_response(status=429, raise_for_status_exc=exc)
        with self.assertRaises(ClientResponseError) as ctx:
            asyncio.run(self.tool._fetch_text("http://example.com", session))  # pylint: disable=protected-access
        self.assertIn("too_many_requests", ctx.exception.message)

    def test_redirect_raises_url_not_allowed(self):
        """Tests that a 3xx GET response raises ValueError with url_not_allowed and the Location URL."""
        session, response = make_get_response(status=301)
        response.headers["Location"] = "http://other.com/"

        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool._fetch_text("http://example.com", session))  # pylint: disable=protected-access
        error = str(ctx.exception)
        self.assertIn("url_not_allowed", error)
        self.assertIn("http://other.com/", error)

    def test_connection_error_raises_client_error_with_prefix(self):
        """Tests that a connection error raises ClientError with url_not_accessible prefix."""
        response_cm = MagicMock()
        response_cm.__aenter__ = AsyncMock(side_effect=ClientError("connection reset"))
        response_cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get = MagicMock(return_value=response_cm)

        with self.assertRaises(ClientError) as ctx:
            asyncio.run(self.tool._fetch_text("http://example.com", session))  # pylint: disable=protected-access
        self.assertIn("url_not_accessible", str(ctx.exception))
