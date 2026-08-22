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

from asyncio import to_thread
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForRetrieverRun
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

WIKIPEDIA_MAX_QUERY_LENGTH = 300


class ModifiedWikipediaRetriever(BaseRetriever):
    """Wikipedia retriever that depends directly on the ``wikipedia`` package."""

    top_k_results: int = 3
    lang: str = "en"
    doc_content_chars_max: int = 4000

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        """Retrieve Wikipedia documents synchronously."""
        return self.load(query)

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun
    ) -> list[Document]:
        """Retrieve Wikipedia documents without blocking the event loop."""
        return await to_thread(self.load, query)

    def load(self, query: str) -> list[Document]:
        """Search Wikipedia and load the matching article content and metadata."""
        wikipedia = self._get_wikipedia_client()
        wikipedia.set_lang(self.lang)
        page_titles = wikipedia.search(
            query[:WIKIPEDIA_MAX_QUERY_LENGTH],
            results=self.top_k_results,
        )

        documents: list[Document] = []
        for page_title in page_titles[: self.top_k_results]:
            try:
                page = wikipedia.page(title=page_title, auto_suggest=False)
            except (wikipedia.exceptions.PageError, wikipedia.exceptions.DisambiguationError):
                continue

            documents.append(
                Document(
                    page_content=page.content[: self.doc_content_chars_max],
                    metadata={
                        "title": page_title,
                        "summary": page.summary,
                        "source": page.url,
                    },
                )
            )

        return documents

    @staticmethod
    def _get_wikipedia_client() -> Any:
        """Import and return the optional ``wikipedia`` dependency."""
        try:
            import wikipedia  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise ImportError(
                "Could not import wikipedia python package. Please install it with `pip install wikipedia`."
            ) from exc

        return wikipedia
