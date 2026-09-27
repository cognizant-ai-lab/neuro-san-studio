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

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from neuro_san_studio.coded_tools.modified_wikipedia_retriever import WIKIPEDIA_MAX_QUERY_LENGTH
from neuro_san_studio.coded_tools.modified_wikipedia_retriever import ModifiedWikipediaRetriever

MODULE = "neuro_san_studio.coded_tools.modified_wikipedia_retriever"


class PageError(Exception):
    """Fake wikipedia PageError."""


class DisambiguationError(Exception):
    """Fake wikipedia DisambiguationError."""


@pytest.fixture(name="wikipedia")
def wikipedia_fixture() -> SimpleNamespace:
    """Create a mocked wikipedia module."""
    return SimpleNamespace(
        set_lang=Mock(),
        search=Mock(return_value=["First", "Second"]),
        page=Mock(
            side_effect=[
                SimpleNamespace(content="first content", summary="first summary", url="https://example.com/first"),
                SimpleNamespace(content="second content", summary="second summary", url="https://example.com/second"),
            ]
        ),
        exceptions=SimpleNamespace(PageError=PageError, DisambiguationError=DisambiguationError),
    )


class TestModifiedWikipediaRetriever:
    """Behavioral tests for ModifiedWikipediaRetriever."""

    def test_load_preserves_content_and_metadata(self, wikipedia: SimpleNamespace):
        """Loaded documents match the previous retriever's result contract."""
        retriever = ModifiedWikipediaRetriever(lang="fr", top_k_results=2, doc_content_chars_max=5)

        with patch.object(retriever, "_get_wikipedia_client", return_value=wikipedia):
            documents = retriever.load("query")

        wikipedia.set_lang.assert_called_once_with("fr")
        assert [document.page_content for document in documents] == ["first", "secon"]
        assert documents[0].metadata == {
            "title": "First",
            "summary": "first summary",
            "source": "https://example.com/first",
        }

    def test_load_truncates_query_and_limits_results(self, wikipedia: SimpleNamespace):
        """Search input and returned pages respect the configured limits."""
        wikipedia.search.return_value = ["First", "Second", "Third"]
        retriever = ModifiedWikipediaRetriever(top_k_results=1)
        query = "x" * (WIKIPEDIA_MAX_QUERY_LENGTH + 10)

        with patch.object(retriever, "_get_wikipedia_client", return_value=wikipedia):
            documents = retriever.load(query)

        wikipedia.search.assert_called_once_with("x" * WIKIPEDIA_MAX_QUERY_LENGTH, results=1)
        wikipedia.page.assert_called_once_with(title="First", auto_suggest=False)
        assert len(documents) == 1

    @pytest.mark.parametrize("error", [PageError(), DisambiguationError()])
    def test_load_skips_unavailable_pages(self, wikipedia: SimpleNamespace, error: Exception):
        """Missing and ambiguous pages are skipped."""
        wikipedia.page.side_effect = [error, SimpleNamespace(content="ok", summary="summary", url="source")]
        retriever = ModifiedWikipediaRetriever(top_k_results=2)

        with patch.object(retriever, "_get_wikipedia_client", return_value=wikipedia):
            documents = retriever.load("query")

        assert len(documents) == 1
        assert documents[0].metadata["title"] == "Second"

    @pytest.mark.asyncio
    async def test_async_retrieval_offloads_blocking_load(self):
        """The async retriever path executes the synchronous client in a worker thread."""
        retriever = ModifiedWikipediaRetriever()

        with patch(f"{MODULE}.to_thread", new=AsyncMock(return_value=["document"])) as mock_to_thread:
            documents = await retriever.ainvoke("query")

        assert documents == ["document"]
        mock_to_thread.assert_awaited_once_with(retriever.load, "query")

    def test_missing_dependency_has_installation_guidance(self):
        """A missing optional dependency reports the existing installation command."""
        retriever = ModifiedWikipediaRetriever()

        with patch.dict("sys.modules", {"wikipedia": None}):
            with pytest.raises(ImportError, match="pip install wikipedia"):
                retriever.load("query")
