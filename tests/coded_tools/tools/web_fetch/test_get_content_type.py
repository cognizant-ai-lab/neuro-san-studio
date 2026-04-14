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
from unittest.mock import patch

from aiohttp import ClientError
from aiohttp import ClientResponseError

from coded_tools.tools.web_fetch import MAX_RESPONSE_BYTES
from coded_tools.tools.web_fetch import WebFetch

from .helpers import make_head_session
from .helpers import make_response_error


class TestGetContentType(TestCase):
    """Unit tests for WebFetch._get_content_type."""

    def setUp(self):
        self.tool = WebFetch()

    def test_head_success_returns_content_type(self):
        """Tests that a successful HEAD response returns the Content-Type header value."""
        session, _ = make_head_session(status=200, content_type="text/html; charset=utf-8")
        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            result = asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertEqual(result, "text/html; charset=utf-8")

    def test_head_405_falls_back_to_get(self):
        """Tests that a 405 response from HEAD causes a fallback GET request to retrieve the content type."""
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 200
        get_response.headers = {"Content-Type": "application/pdf"}
        get_response.raise_for_status = MagicMock()
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            result = asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertEqual(result, "application/pdf")
        session.get.assert_called_once()

    def test_non_2xx_raises_with_url_not_accessible_prefix(self):
        """Tests that a non-2xx HTTP error raises ClientResponseError with url_not_accessible prefix."""
        exc = make_response_error(404)
        session, _ = make_head_session(status=404, raise_for_status_exc=exc)
        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            with self.assertRaises(ClientResponseError) as ctx:
                asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertIn("url_not_accessible", ctx.exception.message)
        self.assertEqual(ctx.exception.status, 404)

    def test_429_raises_with_too_many_requests_prefix(self):
        """Tests that a 429 response raises ClientResponseError with too_many_requests prefix."""
        exc = make_response_error(429)
        session, _ = make_head_session(status=429, raise_for_status_exc=exc)
        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            with self.assertRaises(ClientResponseError) as ctx:
                asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertIn("too_many_requests", ctx.exception.message)

    def test_connection_error_raises_with_url_not_accessible_prefix(self):
        """Tests that a connection error raises ClientError with url_not_accessible prefix."""
        head_cm = MagicMock()
        head_cm.__aenter__ = AsyncMock(side_effect=ClientError("DNS failure"))
        head_cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session.head = MagicMock(return_value=head_cm)

        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            with self.assertRaises(ClientError) as ctx:
                asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_timeout_raises_with_url_not_accessible_prefix(self):
        """Tests that a request timeout raises ClientError with url_not_accessible prefix."""
        head_cm = MagicMock()
        head_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        head_cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session.head = MagicMock(return_value=head_cm)

        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            with self.assertRaises(ClientError) as ctx:
                asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_content_length_over_limit_raises_response_too_large(self):
        """Tests that a Content-Length header exceeding the limit raises ValueError with response_too_large."""
        session, _ = make_head_session(status=200, content_type="text/html", content_length=MAX_RESPONSE_BYTES + 1)
        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertIn("response_too_large", str(ctx.exception))

    def test_head_redirect_raises_url_not_allowed(self):
        """Tests that a 3xx HEAD response raises ValueError with url_not_allowed."""
        session, _ = make_head_session(status=301)
        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_405_get_redirect_raises_url_not_allowed(self):
        """Tests that a 405 HEAD followed by a 3xx GET response raises ValueError with url_not_allowed."""
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 302
        get_response.headers = {}
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        with patch("coded_tools.tools.web_fetch.ClientSession", return_value=session):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(self.tool._get_content_type("http://example.com"))  # pylint: disable=protected-access
        self.assertIn("url_not_allowed", str(ctx.exception))
