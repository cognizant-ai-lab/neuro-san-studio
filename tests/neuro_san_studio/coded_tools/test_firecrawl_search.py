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
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from aiohttp import ClientError

from neuro_san_studio.coded_tools.firecrawl_search import FirecrawlSearch

MODULE = "neuro_san_studio.coded_tools.firecrawl_search"

HEADERS = {"Authorization": "Bearer secret", "Content-Type": "application/json"}
URL = "https://api.firecrawl.dev/v2/search"

RAW_RESPONSE = {
    "success": True,
    "data": {
        "web": [
            {
                "title": "Result",
                "url": "https://example.com",
                "description": "A description.",
                "markdown": "# Result\n\nPage content.",
                "metadata": {"statusCode": 200, "sourceURL": "https://example.com"},
            }
        ]
    },
    "creditsUsed": 3,
}

FORMATTED_RESPONSE = {
    "web": [
        {
            "title": "Result",
            "url": "https://example.com",
            "description": "A description.",
            "markdown": "# Result\n\nPage content.",
        }
    ],
    "credits_used": 3,
}


def _client_session(response):
    """Create a mocked aiohttp session returning the supplied response."""
    session = MagicMock()

    @asynccontextmanager
    async def response_context():
        yield response

    session.post.return_value = response_context()

    @asynccontextmanager
    async def session_context():
        yield session

    return session_context(), session


def _invoke(args, payload=None):
    """Invoke FirecrawlSearch with a mocked HTTP response."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=payload if payload is not None else RAW_RESPONSE)

    session_context, session = _client_session(response)
    with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
        with patch(f"{MODULE}.ClientSession", return_value=session_context) as client_session:
            result = asyncio.run(FirecrawlSearch().async_invoke(args, {}))

    return result, response, client_session, session


class TestFirecrawlSearch:
    """Behavioral tests for the Firecrawl Search API client."""

    def test_defaults_are_translated_to_the_request_body(self):
        """Default arguments are translated to the Firecrawl request body."""
        result, response, client_session, session = _invoke({"query": "python"})

        assert result == FORMATTED_RESPONSE
        response.raise_for_status.assert_called_once_with()
        client_session.assert_called_once()
        session.post.assert_called_once_with(
            URL,
            headers=HEADERS,
            json={
                "query": "python",
                "limit": 5,
                "sources": [{"type": "web"}],
                "country": "us",
                "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True},
            },
        )

    def test_news_results_keep_snippet_and_date(self):
        """News results carry 'snippet' and 'date' rather than 'description'."""
        payload = {
            "data": {
                "news": [
                    {
                        "title": "Headline",
                        "url": "https://example.com/story",
                        "snippet": "What happened.",
                        "date": "18 hours ago",
                        "imageUrl": "https://example.com/thumb.jpg",
                        "position": "1",
                    }
                ]
            },
            "creditsUsed": 2,
        }
        result, _, _, _ = _invoke({"query": "news", "source": "news"}, payload=payload)

        assert result == {
            "news": [
                {
                    "title": "Headline",
                    "url": "https://example.com/story",
                    "snippet": "What happened.",
                    "date": "18 hours ago",
                }
            ],
            "credits_used": 2,
        }

    def test_image_results_keep_the_image_url_and_dimensions(self):
        """Image results carry 'imageUrl' and its dimensions alongside the source page URL."""
        payload = {
            "data": {
                "images": [
                    {
                        "title": "A photo",
                        "url": "https://example.com/page",
                        "imageUrl": "https://example.com/photo.jpg",
                        "imageWidth": "1024",
                        "imageHeight": "683",
                        "position": "1",
                    }
                ]
            },
            "creditsUsed": 2,
        }
        result, _, _, _ = _invoke({"query": "photo", "source": "images"}, payload=payload)

        assert result == {
            "images": [
                {
                    "title": "A photo",
                    "url": "https://example.com/page",
                    "imageUrl": "https://example.com/photo.jpg",
                    "imageWidth": "1024",
                    "imageHeight": "683",
                }
            ],
            "credits_used": 2,
        }

    def test_unsuccessful_body_on_a_200_returns_an_error(self):
        """A body reporting failure is an error, not an empty result set."""
        payload = {"success": False, "error": "Something went wrong."}
        result, _, _, _ = _invoke({"query": "python"}, payload=payload)

        assert result == "Error: Firecrawl request failed: Something went wrong."

    def test_custom_arguments_are_forwarded(self):
        """All optional tool arguments are forwarded to the API."""
        result, _, _, session = _invoke(
            {
                "query": "actualités",
                "limit": "3",
                "source": "news",
                "category": "research",
                "country": "fr",
                "tbs": "qdr:d",
                "scrape_content": False,
            }
        )

        assert result == FORMATTED_RESPONSE
        session.post.assert_called_once_with(
            URL,
            headers=HEADERS,
            json={
                "query": "actualités",
                "limit": 3,
                "sources": [{"type": "news"}],
                "country": "fr",
                "categories": [{"type": "research"}],
                "tbs": "qdr:d",
            },
        )

    def test_url_and_timeout_can_be_overridden(self):
        """A self-hosted endpoint and a custom timeout are honored."""
        _, _, client_session, session = _invoke(
            {"query": "python", "firecrawl_url": "https://firecrawl.internal/v2/search", "firecrawl_timeout": 5}
        )

        assert session.post.call_args.args[0] == "https://firecrawl.internal/v2/search"
        assert client_session.call_args.kwargs["timeout"].total == 5.0

    def test_results_without_scraped_content_omit_markdown(self):
        """Snippet-only results do not carry an empty markdown key."""
        payload = {"data": {"web": [{"title": "Result", "url": "https://example.com", "description": "A."}]}}
        result, _, _, _ = _invoke({"query": "python", "scrape_content": False}, payload=payload)

        assert result == {
            "web": [{"title": "Result", "url": "https://example.com", "description": "A."}],
            "credits_used": None,
        }

    def test_warnings_are_surfaced(self):
        """A warning from the API is passed through to the agent."""
        payload = {"data": {}, "creditsUsed": 1, "warning": "Some results could not be scraped."}
        result, _, _, _ = _invoke({"query": "python"}, payload=payload)

        assert result == {"credits_used": 1, "warning": "Some results could not be scraped."}

    def test_missing_query_returns_error_without_request(self):
        """A missing query is reported before opening an HTTP session."""
        with patch(f"{MODULE}.ClientSession") as client_session:
            result = asyncio.run(FirecrawlSearch().async_invoke({}, {}))

        assert result == "Error: No query provided."
        client_session.assert_not_called()

    def test_overlong_query_returns_error_without_request(self):
        """Queries above the documented API limit are rejected locally."""
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "x" * 501}, {}))

        assert result == "Error: 'query' must be at most 500 characters, got: 501."
        client_session.assert_not_called()

    def test_missing_api_key_returns_error_without_request(self):
        """A missing API key is reported before opening an HTTP session."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "python"}, {}))

        assert result == "Error: FIRECRAWL_API_KEY is not set."
        client_session.assert_not_called()

    def test_unsupported_source_returns_error_without_request(self):
        """Only sources accepted by the API are allowed."""
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "python", "source": "videos"}, {}))

        assert result == "Error: Unsupported source: videos."
        client_session.assert_not_called()

    def test_unsupported_category_returns_error_without_request(self):
        """Only categories accepted by the API are allowed."""
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "python", "category": "news"}, {}))

        assert result == "Error: Unsupported category: news."
        client_session.assert_not_called()

    @pytest.mark.parametrize("invalid_limit", [None, "many"])
    def test_invalid_result_count_returns_error_without_request(self, invalid_limit):
        """Invalid result counts follow the coded tool error contract."""
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "python", "limit": invalid_limit}, {}))

        assert result == f"Error: 'limit' must be an integer, got: {invalid_limit!r}."
        client_session.assert_not_called()

    @pytest.mark.parametrize("out_of_range", [0, -1, 101, 500])
    def test_out_of_range_limit_returns_error_without_request(self, out_of_range):
        """Limits outside the API's 1-100 range are rejected locally rather than by an HTTP 400."""
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "python", "limit": out_of_range}, {}))

        assert result == f"Error: 'limit' must be between 1 and 100, got: {out_of_range}."
        client_session.assert_not_called()

    @pytest.mark.parametrize("falsey", ["false", "False", " FALSE ", "0", "no", "off"])
    def test_scrape_content_accepts_textual_false(self, falsey):
        """An LLM-supplied string such as "false" turns scraping off, unlike bool("false")."""
        _, _, _, session = _invoke({"query": "python", "scrape_content": falsey})

        assert "scrapeOptions" not in session.post.call_args.kwargs["json"]

    @pytest.mark.parametrize("truthy", ["true", "True", "yes", True])
    def test_scrape_content_accepts_textual_true(self, truthy):
        """Textual and real booleans both keep scraping on."""
        _, _, _, session = _invoke({"query": "python", "scrape_content": truthy})

        assert session.post.call_args.kwargs["json"]["scrapeOptions"] == {
            "formats": ["markdown"],
            "onlyMainContent": True,
        }

    def test_http_errors_return_error_string(self):
        """HTTP failures follow the coded tool error contract."""
        error = ClientError("request failed")
        response = MagicMock()
        response.raise_for_status.side_effect = error
        response.json = AsyncMock()
        session_context, _ = _client_session(response)

        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession", return_value=session_context):
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "python"}, {}))

        assert result == "Error: Firecrawl request failed: request failed"
        response.json.assert_not_awaited()

    def test_timeout_returns_error_string(self):
        """Request timeouts follow the coded tool error contract."""
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession", side_effect=TimeoutError("timed out")):
                result = asyncio.run(FirecrawlSearch().async_invoke({"query": "python"}, {}))

        assert result == "Error: Firecrawl request failed: timed out"
