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

import re
from asyncio import Semaphore
from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import gather
from asyncio import run as asyncio_run
from asyncio import to_thread
from logging import getLogger
from typing import Any
from typing import ClassVar
from typing import List
from typing import Optional

from aiohttp import ClientError
from aiohttp import ClientSession
from aiohttp import ClientTimeout

# pylint: disable=import-error
from arxiv import ArxivError
from arxiv import Client
from arxiv import Result
from arxiv import Search
from arxiv import SortCriterion
from arxiv import SortOrder
from langchain_core.callbacks import AsyncCallbackManagerForRetrieverRun
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pypdf.errors import PyPdfError

from neuro_san_studio.coded_tools.utils.pdf_utils import PdfUtils

logger = getLogger(__name__)

DOWNLOAD_TIMEOUT_SECONDS: int = 60


class ModifiedArxivRetriever(BaseRetriever):
    """
    Self-contained arXiv retriever, depending only on `arxiv`, `aiohttp`,
    `pypdf`, and `langchain-core`.

    Replaces langchain-community's ArxivRetriever/ArxivAPIWrapper, which are sunset
    with no standalone successor package
    (https://github.com/langchain-ai/langchain-community/issues/674).

    Differences from the original langchain-community implementation:
    - Queries are passed to the arXiv API verbatim (no ":" and "-" removal),
      so field syntax like au:"Firstname Lastname" works.
      User can still ask questions normally since the template is handled by LLM.
    - Adds `sort_by` and `sort_order` support.
    - Keeps `Entry ID` in the main metadata when `get_full_documents` is True.
    - Uses `arxiv.Client().results(search)`; `Search.results()` was removed in arxiv 3.0.
    - Extracts PDF text with `pypdf` (already a project dependency) instead of PyMuPDF.
    - Downloads full-document PDFs concurrently with aiohttp, bounded by
      `max_concurrent_downloads`; the async path (`ainvoke`) is canonical and
      the sync path delegates to it.

    Adapted from
    https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/utilities/arxiv.py
    and
    https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/retrievers/arxiv.py
    """

    top_k_results: int = 3
    continue_on_failure: bool = False
    load_all_available_meta: bool = False
    doc_content_chars_max: Optional[int] = 4000
    get_full_documents: bool = False
    max_concurrent_downloads: int = 5
    sort_by: str = "relevance"
    sort_order: str = "descending"

    ARXIV_MAX_QUERY_LENGTH: ClassVar[int] = 300

    # --- BaseRetriever entry points -------------------------------------------------

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        """
        Retrieve documents for a query (sync path, required by BaseRetriever).

        :param query: a plaintext search query
        :param run_manager: callback manager supplied by langchain (unused)
        :return: list of Documents, full texts or summaries depending on `get_full_documents`
        """
        if self.get_full_documents:
            return self.load(query)

        return self._get_summaries_as_docs(query)

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: AsyncCallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Retrieve documents for a query (async path, used by `ainvoke`).

        :param query: a plaintext search query
        :param run_manager: callback manager supplied by langchain (unused)
        :return: list of Documents, full texts or summaries depending on `get_full_documents`
        """
        if self.get_full_documents:
            return await self.aload(query)

        # The arxiv client is synchronous; run the blocking search in a worker thread.
        return await to_thread(self._get_summaries_as_docs, query)

    # --- Full-document loading ------------------------------------------------------

    def load(self, query: str) -> List[Document]:
        """
        Sync counterpart of aload(); only usable from threads without a running event loop.

        :param query: a plaintext search query
        :return: list of Documents with full PDF text as content
        """
        return asyncio_run(self.aload(query))

    async def aload(self, query: str) -> List[Document]:
        """
        Run Arxiv search, then download the top k results as PDFs concurrently
        and return them as Documents with the article meta information.

        :param query: a plaintext search query
        :return: list of Documents with full PDF text as content; results whose
            PDF could not be fetched or parsed are skipped
        """
        try:
            # The arxiv client is synchronous; run the blocking search in a worker thread.
            results: List[Result] = await to_thread(self._fetch_results, query)
        except ArxivError as ex:
            logger.debug("Error on arxiv: %s", ex)
            return []

        timeout = ClientTimeout(total=DOWNLOAD_TIMEOUT_SECONDS)
        # The semaphore bounds transient memory (at most max_concurrent_downloads
        # raw PDF buffers in flight) and keeps the connection count to arXiv polite.
        semaphore = Semaphore(self.max_concurrent_downloads)
        async with ClientSession(timeout=timeout) as session:
            # return_exceptions=True lets every download finish before the session
            # closes; an unexpected exception is re-raised afterwards instead of
            # tearing the session down under the still-running sibling tasks.
            outcomes = await gather(
                *(self._aload_single(result, session, semaphore) for result in results),
                return_exceptions=True,
            )

        docs: List[Document] = []
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome
            if outcome is not None:
                docs.append(outcome)
        return docs

    async def _aload_single(self, result: Result, session: ClientSession, semaphore: Semaphore) -> Optional[Document]:
        """
        Download one result's PDF and convert it to a Document.

        :param result: arXiv search result to download
        :param session: shared aiohttp session for the whole batch
        :param semaphore: bounds the number of concurrent downloads
        :return: the Document, or None when the result has no PDF or an expected
            download/parse error occurred (the result is skipped)
        """
        try:
            # Result.download_pdf() was removed in arxiv 3.0; fetch the PDF from
            # Result.pdf_url instead, which is available in both old and new versions.
            if not result.pdf_url:
                logger.debug("No PDF link for %s", result.entry_id)
                return None
            # Hold the semaphore through download AND parsing so the raw bytes of
            # at most max_concurrent_downloads PDFs are alive at any moment.
            async with semaphore:
                async with session.get(result.pdf_url) as response:
                    response.raise_for_status()
                    data: bytes = await response.read()
                # Text extraction is CPU-bound; run it in a worker thread so a large
                # or complex PDF does not stall the event loop.
                text: str = await to_thread(PdfUtils.parse_pdf_bytes, data)
        except (ClientError, AsyncTimeoutError, PyPdfError) as f_ex:
            logger.debug(f_ex)
            return None
        except Exception as exception:
            if self.continue_on_failure:
                logger.error(
                    "Unexpected error downloading/parsing PDF for %s: %s", result.entry_id, exception, exc_info=True
                )
                return None
            raise

        return Document(page_content=text[: self.doc_content_chars_max], metadata=self._build_metadata(result))

    def _build_metadata(self, result: Result) -> dict[str, Any]:
        """
        Build Document metadata; include all available arXiv fields when configured.

        :param result: arXiv search result to extract metadata from
        :return: metadata dictionary; extended with the extra arXiv fields when
            `load_all_available_meta` is True
        """
        if self.load_all_available_meta:
            extra_metadata = {
                "published_first_time": str(result.published.date()),
                "comment": result.comment,
                "journal_ref": result.journal_ref,
                "doi": result.doi,
                "primary_category": result.primary_category,
                "categories": result.categories,
                "links": [link.href for link in result.links],
            }
        else:
            extra_metadata = {}
        return {
            "Entry ID": result.entry_id,
            "Published": str(result.updated.date()),
            "Title": result.title,
            "Authors": ", ".join(a.name for a in result.authors),
            "Summary": result.summary,
            **extra_metadata,
        }

    # --- Summaries loading ----------------------------------------------------------

    def _get_summaries_as_docs(self, query: str) -> List[Document]:
        """
        Perform an arxiv search and return the results as Documents with
        summaries as the content.

        :param query: a plaintext search query
        :return: list of Documents with paper summaries as content; on an arXiv
            API error, a single Document containing the error text
        """
        try:
            results = self._fetch_results(query)
        except ArxivError as ex:
            logger.error("Arxiv exception: %s", ex)
            return [Document(page_content=f"Arxiv exception: {ex}")]

        return [
            Document(
                page_content=result.summary,
                metadata={
                    "Entry ID": result.entry_id,
                    "Published": str(result.updated.date()),
                    "Title": result.title,
                    "Authors": ", ".join(a.name for a in result.authors),
                },
            )
            for result in results
        ]

    # --- arXiv search helpers -------------------------------------------------------

    def _fetch_results(self, query: str) -> List[Result]:
        """
        Fetch arxiv results for a query, applying `sort_by`/`sort_order`.

        Blocking: performs the HTTP search request(s) before returning.

        :param query: a plaintext search query or whitespace-separated arXiv identifiers
        :return: list of arxiv.Result
        """
        sort_criterion = self._get_sort_criterion()
        sort_order_enum = self._get_sort_order()

        if self._is_arxiv_identifier(query):
            search = Search(
                id_list=query.split(),
                max_results=self.top_k_results,
                sort_by=sort_criterion,
                sort_order=sort_order_enum,
            )
        else:
            search = Search(
                query[: self.ARXIV_MAX_QUERY_LENGTH],
                max_results=self.top_k_results,
                sort_by=sort_criterion,
                sort_order=sort_order_enum,
            )
        # Search.results() was removed in arxiv 3.0; Client.results() works on 1.4+.
        # Materialize the lazy generator so all paging happens here, inside the
        # callers' try/except ArxivError blocks.
        return list(Client().results(search))

    def _is_arxiv_identifier(self, query: str) -> bool:
        """
        Check if a query consists only of arxiv identifiers.

        :param query: a plaintext search query
        :return: True when every whitespace-separated token is an arXiv identifier
        """
        arxiv_identifier_pattern = (
            r"(?:\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}(?:v\d+)?"
            r"|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)"
        )
        for query_item in query[: self.ARXIV_MAX_QUERY_LENGTH].split():
            if re.fullmatch(arxiv_identifier_pattern, query_item) is None:
                return False
        return True

    def _get_sort_criterion(self) -> SortCriterion:
        """
        Convert string sort_by to SortCriterion enum.

        :return: the matching SortCriterion; Relevance when `sort_by` is unknown
        """
        mapping = {
            "relevance": SortCriterion.Relevance,
            "lastUpdatedDate": SortCriterion.LastUpdatedDate,
            "submittedDate": SortCriterion.SubmittedDate,
        }
        return mapping.get(self.sort_by, SortCriterion.Relevance)

    def _get_sort_order(self) -> SortOrder:
        """
        Convert string sort_order to SortOrder enum.

        :return: the matching SortOrder; Descending when `sort_order` is unknown
        """
        mapping = {
            "ascending": SortOrder.Ascending,
            "descending": SortOrder.Descending,
        }
        return mapping.get(self.sort_order, SortOrder.Descending)
