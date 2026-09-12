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

from neuro_san_studio.coded_tools.serply_search import SerplySearch

MODULE = "neuro_san_studio.coded_tools.serply_search"

HEADERS = {"X-Api-Key": "secret", "User-Agent": "neuro-san-studio"}
SEARCH_URL = "https://api.serply.io/v1/search/"

RAW_RESPONSE = {
    "results": [
        {
            "title": "Result",
            "description": "A description.",
            "position": 1,
            "realPosition": 1,
            "result_type": "organic",
            "metadata": {"display_url": "example.com"},
            "link": "https://example.com",
        }
    ],
    "ads": [],
    "related_searches": ["python tutorial"],
    "total": 12000,
}

FORMATTED_RESPONSE = {
    "type": "search",
    "results": [{"title": "Result", "link": "https://example.com", "description": "A description.", "position": 1}],
}


def _client_session(response):
    """Create a mocked aiohttp session returning the supplied response."""
    session = MagicMock()

    @asynccontextmanager
    async def response_context():
        yield response

    session.get.return_value = response_context()

    @asynccontextmanager
    async def session_context():
        yield session

    return session_context(), session


def _invoke(args, payload=None):
    """Invoke SerplySearch with a mocked HTTP response."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=payload if payload is not None else RAW_RESPONSE)

    session_context, session = _client_session(response)
    with patch.dict("os.environ", {"SERPLY_API_KEY": "secret"}, clear=True):
        with patch(f"{MODULE}.ClientSession", return_value=session_context) as client_session:
            result = asyncio.run(SerplySearch().async_invoke(args, {}))

    return result, response, client_session, session


class TestSerplySearch:
    """Behavioral tests for the Serply API client."""

    def test_defaults_are_translated_to_the_request(self):
        """Default arguments are translated to the Serply request parameters."""
        result, response, client_session, session = _invoke({"query": "python"})

        assert result == FORMATTED_RESPONSE
        response.raise_for_status.assert_called_once_with()
        client_session.assert_called_once()
        assert client_session.call_args.kwargs["timeout"].total == 30.0
        session.get.assert_called_once_with(
            SEARCH_URL,
            headers=HEADERS,
            params={"q": "python", "num": 10, "hl": "en", "gl": "us"},
        )

    def test_custom_arguments_are_forwarded(self):
        """All optional tool arguments are forwarded to the API."""
        _, _, _, session = _invoke(
            {"query": "actualités", "type": "news", "k": "5", "gl": "fr", "hl": "fr", "tbs": "qdr:d"},
            payload={"entries": []},
        )

        session.get.assert_called_once_with(
            "https://api.serply.io/v1/news/",
            headers=HEADERS,
            params={"q": "actualités", "num": 5, "hl": "fr", "gl": "fr", "tbs": "qdr:d"},
        )

    def test_null_optional_args_use_defaults(self):
        """JSON null from Neuro SAN is treated as omitted, not sent to the API."""
        result, _, _, session = _invoke(
            {"query": "python", "type": None, "k": None, "gl": None, "hl": None, "tbs": None, "serply_timeout": None}
        )

        assert result == FORMATTED_RESPONSE
        session.get.assert_called_once_with(
            SEARCH_URL,
            headers=HEADERS,
            params={"q": "python", "num": 10, "hl": "en", "gl": "us"},
        )

    def test_news_entries_keep_the_published_date_and_are_cut_to_k(self):
        """News entries carry 'published', and the list is cut to k because the API ignores 'num'."""
        payload = {
            "feed": {"title": "python - Google News"},
            "entries": [
                {"title": "First", "link": "https://example.com/1", "published": "Mon, 07 Sep 2026 15:35:22 GMT"},
                {"title": "Second", "link": "https://example.com/2", "published": "Sun, 06 Sep 2026 09:00:00 GMT"},
                {"title": "Third", "link": "https://example.com/3", "published": "Sat, 05 Sep 2026 09:00:00 GMT"},
            ],
        }
        result, _, _, _ = _invoke({"query": "python", "type": "news", "k": 2}, payload=payload)

        assert result == {
            "type": "news",
            "results": [
                {"title": "First", "link": "https://example.com/1", "published": "Mon, 07 Sep 2026 15:35:22 GMT"},
                {"title": "Second", "link": "https://example.com/2", "published": "Sun, 06 Sep 2026 09:00:00 GMT"},
            ],
        }

    def test_scholar_articles_keep_authors_and_citation_count(self):
        """Scholar articles carry the authors and venue in 'description' plus a citation count."""
        payload = {
            "articles": [
                {
                    "title": "Consensus in Multi-Agent Systems",
                    "link": "https://example.com/paper/1",
                    "id": "W123",
                    "author": {"names": "A. Author - Proceedings, 2007", "authors": [{"name": "A. Author"}]},
                    "description": "A. Author - Proceedings, 2007",
                    "extras": {"citations": {"count": 10522, "link": "https://example.com/cites/W123"}},
                },
                {"title": "No citations yet", "link": "https://example.com/paper/2", "description": "B. Author, 2026"},
            ],
        }
        result, _, _, session = _invoke({"query": "multi agent systems", "type": "scholar"}, payload=payload)

        assert session.get.call_args.args[0] == "https://api.serply.io/v1/scholar/"
        assert result == {
            "type": "scholar",
            "results": [
                {
                    "title": "Consensus in Multi-Agent Systems",
                    "link": "https://example.com/paper/1",
                    "description": "A. Author - Proceedings, 2007",
                    "citations": 10522,
                },
                {"title": "No citations yet", "link": "https://example.com/paper/2", "description": "B. Author, 2026"},
            ],
        }

    def test_results_without_a_link_are_dropped(self):
        """A result the agent cannot follow is not worth a slot in the context."""
        payload = {"results": [{"title": "Answer box", "description": "No link here."}, RAW_RESPONSE["results"][0]]}
        result, _, _, _ = _invoke({"query": "python"}, payload=payload)

        assert result == FORMATTED_RESPONSE

    def test_empty_results_return_an_empty_list(self):
        """No results is a valid, empty answer rather than an error."""
        result, _, _, _ = _invoke({"query": "site:example.com nothing"}, payload={"results": [], "total": None})

        assert result == {"type": "search", "results": []}

    def test_url_and_timeout_can_be_overridden(self):
        """A custom endpoint and a custom timeout are honored."""
        _, _, client_session, session = _invoke(
            {"query": "python", "serply_url": "http://localhost:8000/v1/", "serply_timeout": 5}
        )

        assert session.get.call_args.args[0] == "http://localhost:8000/v1/search/"
        assert client_session.call_args.kwargs["timeout"].total == 5.0

    def test_missing_query_returns_error_without_request(self):
        """A missing query is reported before opening an HTTP session."""
        with patch(f"{MODULE}.ClientSession") as client_session:
            result = asyncio.run(SerplySearch().async_invoke({}, {}))

        assert result == "Error: No query provided."
        client_session.assert_not_called()

    def test_missing_api_key_returns_error_without_request(self):
        """A missing API key is reported before opening an HTTP session."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(SerplySearch().async_invoke({"query": "python"}, {}))

        assert result == "Error: SERPLY_API_KEY is not set."
        client_session.assert_not_called()

    def test_unsupported_search_type_returns_error_without_request(self):
        """Only the search types served by the API are allowed."""
        with patch.dict("os.environ", {"SERPLY_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(SerplySearch().async_invoke({"query": "python", "type": "images"}, {}))

        assert result == "Error: Unsupported search type: images."
        client_session.assert_not_called()

    def test_invalid_result_count_returns_error_without_request(self):
        """Invalid result counts follow the coded tool error contract."""
        with patch.dict("os.environ", {"SERPLY_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(SerplySearch().async_invoke({"query": "python", "k": "many"}, {}))

        assert result == "Error: 'k' must be an integer, got: 'many'."
        client_session.assert_not_called()

    @pytest.mark.parametrize("out_of_range", [0, -1, 101])
    def test_out_of_range_result_count_returns_error_without_request(self, out_of_range):
        """Counts outside the API's 1-100 range are rejected locally rather than by an HTTP 400."""
        with patch.dict("os.environ", {"SERPLY_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(SerplySearch().async_invoke({"query": "python", "k": out_of_range}, {}))

        assert result == f"Error: 'k' must be between 1 and 100, got: {out_of_range}."
        client_session.assert_not_called()

    def test_invalid_timeout_returns_error_without_request(self):
        """A timeout that is not a number follows the coded tool error contract."""
        with patch.dict("os.environ", {"SERPLY_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(SerplySearch().async_invoke({"query": "python", "serply_timeout": "soon"}, {}))

        assert result == "Error: 'serply_timeout' must be a number, got: 'soon'."
        client_session.assert_not_called()

    def test_http_errors_return_error_string(self):
        """HTTP failures follow the coded tool error contract."""
        error = ClientError("request failed")
        response = MagicMock()
        response.raise_for_status.side_effect = error
        response.json = AsyncMock()
        session_context, _ = _client_session(response)

        with patch.dict("os.environ", {"SERPLY_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession", return_value=session_context):
                result = asyncio.run(SerplySearch().async_invoke({"query": "python"}, {}))

        assert result == "Error: Serply request failed: request failed"
        response.json.assert_not_awaited()

    def test_timeout_returns_error_string(self):
        """Request timeouts follow the coded tool error contract."""
        with patch.dict("os.environ", {"SERPLY_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession", side_effect=TimeoutError("timed out")):
                result = asyncio.run(SerplySearch().async_invoke({"query": "python"}, {}))

        assert result == "Error: Serply request failed: timed out"
