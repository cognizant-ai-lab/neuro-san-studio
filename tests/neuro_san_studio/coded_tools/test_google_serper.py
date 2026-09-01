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

from neuro_san_studio.coded_tools.google_serper import GoogleSerper

MODULE = "neuro_san_studio.coded_tools.google_serper"


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


def _invoke(args, response=None):
    """Invoke GoogleSerper with a mocked HTTP response."""
    response = response or MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value={"organic": [{"title": "Result"}]})

    session_context, session = _client_session(response)
    with patch.dict("os.environ", {"SERPER_API_KEY": "secret"}, clear=True):
        with patch(f"{MODULE}.ClientSession", return_value=session_context) as client_session:
            result = asyncio.run(GoogleSerper().async_invoke(args, {}))

    return result, response, client_session, session


class TestGoogleSerper:
    """Behavioral tests for the direct Google Serper API client."""

    def test_defaults_match_previous_wrapper_contract(self):
        """Default arguments are translated to the Serper request parameters."""
        result, response, client_session, session = _invoke({"query": "python"})

        assert result == {"organic": [{"title": "Result"}]}
        response.raise_for_status.assert_called_once_with()
        client_session.assert_called_once()
        session.post.assert_called_once_with(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": "secret", "Content-Type": "application/json"},
            params={"q": "python", "gl": "us", "hl": "en", "num": 10},
        )

    def test_custom_arguments_are_forwarded(self):
        """All existing optional tool arguments remain supported."""
        result, _, _, session = _invoke(
            {"query": "actualités", "type": "news", "k": "5", "gl": "fr", "hl": "fr", "tbs": "qdr:d"}
        )

        assert result == {"organic": [{"title": "Result"}]}
        session.post.assert_called_once_with(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": "secret", "Content-Type": "application/json"},
            params={"q": "actualités", "gl": "fr", "hl": "fr", "num": 5, "tbs": "qdr:d"},
        )

    def test_missing_query_returns_error_without_request(self):
        """A missing query retains the existing public error response."""
        with patch(f"{MODULE}.ClientSession") as client_session:
            result = asyncio.run(GoogleSerper().async_invoke({}, {}))

        assert result == "Error: No query provided."
        client_session.assert_not_called()

    def test_missing_api_key_returns_error_without_request(self):
        """A missing API key is reported before opening an HTTP session."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(GoogleSerper().async_invoke({"query": "python"}, {}))

        assert result == "Error: SERPER_API_KEY is not set."
        client_session.assert_not_called()

    def test_unsupported_search_type_returns_error_without_request(self):
        """Only search types accepted by the previous wrapper are allowed."""
        with patch.dict("os.environ", {"SERPER_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(GoogleSerper().async_invoke({"query": "python", "type": "videos"}, {}))

        assert result == "Error: Unsupported search type: videos."
        client_session.assert_not_called()

    @pytest.mark.parametrize("invalid_k", [None, "many"])
    def test_invalid_result_count_returns_error_without_request(self, invalid_k):
        """Invalid result counts follow the coded tool error contract."""
        with patch.dict("os.environ", {"SERPER_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession") as client_session:
                result = asyncio.run(GoogleSerper().async_invoke({"query": "python", "k": invalid_k}, {}))

        assert result == f"Error: 'k' must be an integer, got: {invalid_k!r}."
        client_session.assert_not_called()

    def test_http_errors_return_error_string(self):
        """HTTP failures follow the coded tool error contract."""
        error = ClientError("request failed")
        response = MagicMock()
        response.raise_for_status.side_effect = error
        response.json = AsyncMock()
        session_context, _ = _client_session(response)

        with patch.dict("os.environ", {"SERPER_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession", return_value=session_context):
                result = asyncio.run(GoogleSerper().async_invoke({"query": "python"}, {}))

        assert result == "Error: Serper request failed: request failed"
        response.json.assert_not_awaited()

    def test_timeout_returns_error_string(self):
        """Request timeouts follow the coded tool error contract."""
        with patch.dict("os.environ", {"SERPER_API_KEY": "secret"}, clear=True):
            with patch(f"{MODULE}.ClientSession", side_effect=TimeoutError("timed out")):
                result = asyncio.run(GoogleSerper().async_invoke({"query": "python"}, {}))

        assert result == "Error: Serper request failed: timed out"
