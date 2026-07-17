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
from asyncio import TimeoutError as AsyncTimeoutError
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from aiohttp import ClientError

# pylint: disable=import-error
from arxiv import ArxivError
from arxiv import SortCriterion
from arxiv import SortOrder
from langchain_core.documents import Document
from pypdf.errors import PyPdfError

from neuro_san_studio.coded_tools.modified_arxiv_retriever import ModifiedArxivRetriever

# Patch names in the module under test, not their origin packages.
MODULE = "neuro_san_studio.coded_tools.modified_arxiv_retriever"


# pylint: disable=too-many-public-methods
class TestModifiedArxivRetriever:
    """Behavioral tests for ModifiedArxivRetriever.

    External systems are mocked at the module boundary: the synchronous `arxiv`
    client (Search/Client), the aiohttp session, and PdfUtils.parse_pdf_bytes.
    Async methods are driven with asyncio.run so no pytest-asyncio plugin is
    needed. Tests cover the sync/async entry-point branching, full-document
    download orchestration, per-result download handling, metadata construction,
    summary building, arXiv query construction, identifier detection, and the
    sort enum mappings.
    """

    # --- helpers ---------------------------------------------------------- #
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    @staticmethod
    def _make_result(
        entry_id="http://arxiv.org/abs/2301.01234v1",
        title="A Title",
        summary="A concise summary.",
        authors=("Ada Lovelace", "Alan Turing"),
        pdf_url="http://arxiv.org/pdf/2301.01234v1",
        updated=datetime(2023, 1, 15, 12, 0),
        published=datetime(2023, 1, 10, 9, 0),
        comment="7 pages",
        journal_ref="J. Ref 2023",
        doi="10.1000/xyz",
        primary_category="cs.AI",
        categories=("cs.AI", "cs.LG"),
        links=("http://link/a", "http://link/b"),
    ):
        """Return a fake arxiv.Result with the attributes the retriever reads."""
        return MagicMock(
            entry_id=entry_id,
            title=title,
            summary=summary,
            authors=[_named(n) for n in authors],
            pdf_url=pdf_url,
            updated=updated,
            published=published,
            comment=comment,
            journal_ref=journal_ref,
            doi=doi,
            primary_category=primary_category,
            categories=list(categories),
            links=[_href(h) for h in links],
        )

    @staticmethod
    @asynccontextmanager
    async def _acm(value):
        """Wrap a value in a single-use async context manager."""
        yield value

    @staticmethod
    def _response(read_bytes=b"%PDF-fake", raise_status_exc=None, read_exc=None):
        """Build a fake aiohttp response for use inside an async `with` block."""
        resp = MagicMock(name="response")
        resp.raise_for_status = MagicMock(side_effect=raise_status_exc)
        resp.read = AsyncMock(return_value=read_bytes, side_effect=read_exc)
        return resp

    def _session_returning(self, response):
        """Build a fake ClientSession whose .get() yields the given response."""
        session = MagicMock(name="session")
        session.get = MagicMock(return_value=self._acm(response))
        return session

    # --- entry-point branching (sync) ------------------------------------ #
    def test_get_relevant_documents_full_uses_load(self):
        """The sync entry point delegates to load() when get_full_documents is True."""
        retriever = ModifiedArxivRetriever(get_full_documents=True)
        with patch.object(ModifiedArxivRetriever, "load", return_value=["FULL"]) as m_load:
            out = retriever._get_relevant_documents("q", run_manager=MagicMock())
        assert out == ["FULL"]
        m_load.assert_called_once_with("q")

    def test_get_relevant_documents_summary_uses_summaries(self):
        """The sync entry point delegates to summaries when get_full_documents is False."""
        retriever = ModifiedArxivRetriever(get_full_documents=False)
        with patch.object(ModifiedArxivRetriever, "_get_summaries_as_docs", return_value=["SUM"]) as m_sum:
            out = retriever._get_relevant_documents("q", run_manager=MagicMock())
        assert out == ["SUM"]
        m_sum.assert_called_once_with("q")

    # --- entry-point branching (async) ----------------------------------- #
    def test_aget_relevant_documents_full_uses_aload(self):
        """The async entry point awaits aload() when get_full_documents is True."""
        retriever = ModifiedArxivRetriever(get_full_documents=True)
        with patch.object(ModifiedArxivRetriever, "aload", new=AsyncMock(return_value=["FULL"])):
            out = asyncio.run(retriever._aget_relevant_documents("q", run_manager=MagicMock()))
        assert out == ["FULL"]

    def test_aget_relevant_documents_summary_offloads_to_thread(self):
        """The async entry point runs the sync summary path in a worker thread."""
        retriever = ModifiedArxivRetriever(get_full_documents=False)
        with patch.object(ModifiedArxivRetriever, "_get_summaries_as_docs", return_value=["SUM"]) as m_sum:
            out = asyncio.run(retriever._aget_relevant_documents("q", run_manager=MagicMock()))
        assert out == ["SUM"]
        m_sum.assert_called_once_with("q")

    # --- load() ----------------------------------------------------------- #
    def test_load_runs_aload_to_completion(self):
        """The sync load() drives the async aload() and returns its result."""
        retriever = ModifiedArxivRetriever()
        with patch.object(ModifiedArxivRetriever, "aload", new=AsyncMock(return_value=["D"])):
            assert retriever.load("q") == ["D"]

    # --- aload() orchestration ------------------------------------------- #
    def test_aload_returns_empty_on_arxiv_error(self):
        """A failing arXiv search yields an empty list rather than raising."""
        retriever = ModifiedArxivRetriever()
        err = ArxivError("http://x", 0, "boom")
        with patch.object(ModifiedArxivRetriever, "_fetch_results", side_effect=err):
            assert asyncio.run(retriever.aload("q")) == []

    def test_aload_filters_none_and_collects_documents(self):
        """aload keeps successful Documents and drops results that returned None."""
        retriever = ModifiedArxivRetriever()
        results = [self._make_result(), self._make_result(), self._make_result()]
        doc_a, doc_c = Document(page_content="a"), Document(page_content="c")
        with (
            patch.object(ModifiedArxivRetriever, "_fetch_results", return_value=results),
            patch.object(ModifiedArxivRetriever, "_aload_single", new=AsyncMock(side_effect=[doc_a, None, doc_c])),
            patch(f"{MODULE}.ClientSession", return_value=self._acm(MagicMock())),
        ):
            out = asyncio.run(retriever.aload("q"))
        assert out == [doc_a, doc_c]

    def test_aload_reraises_unexpected_exception(self):
        """An unexpected exception captured by gather is re-raised after the session closes."""
        retriever = ModifiedArxivRetriever()
        results = [self._make_result(), self._make_result()]
        with (
            patch.object(ModifiedArxivRetriever, "_fetch_results", return_value=results),
            patch.object(
                ModifiedArxivRetriever,
                "_aload_single",
                new=AsyncMock(side_effect=[Document(page_content="a"), RuntimeError("unexpected")]),
            ),
            patch(f"{MODULE}.ClientSession", return_value=self._acm(MagicMock())),
        ):
            with pytest.raises(RuntimeError, match="unexpected"):
                asyncio.run(retriever.aload("q"))

    # --- _aload_single() -------------------------------------------------- #
    def test_aload_single_returns_none_without_pdf_url(self):
        """A result lacking a PDF link is skipped (returns None)."""
        retriever = ModifiedArxivRetriever()
        result = self._make_result(pdf_url="")
        out = asyncio.run(retriever._aload_single(result, MagicMock(), asyncio.Semaphore(1)))
        assert out is None

    def test_aload_single_builds_truncated_document(self):
        """A successful download yields a Document with content truncated to the cap."""
        retriever = ModifiedArxivRetriever(doc_content_chars_max=5)
        result = self._make_result()
        session = self._session_returning(self._response(read_bytes=b"%PDF"))
        with patch(f"{MODULE}.PdfUtils.parse_pdf_bytes", return_value="0123456789"):
            out = asyncio.run(retriever._aload_single(result, session, asyncio.Semaphore(1)))
        assert isinstance(out, Document)
        assert out.page_content == "01234"  # truncated to doc_content_chars_max
        assert out.metadata["Entry ID"] == result.entry_id

    def test_aload_single_swallows_expected_download_errors(self):
        """Expected client/timeout/pypdf errors are logged and skipped (return None)."""
        retriever = ModifiedArxivRetriever()
        result = self._make_result()

        # HTTP status error
        session = self._session_returning(self._response(raise_status_exc=ClientError()))
        assert asyncio.run(retriever._aload_single(result, session, asyncio.Semaphore(1))) is None

        # read timeout
        session = self._session_returning(self._response(read_exc=AsyncTimeoutError()))
        assert asyncio.run(retriever._aload_single(result, session, asyncio.Semaphore(1))) is None

        # PDF parse error
        session = self._session_returning(self._response())
        with patch(f"{MODULE}.PdfUtils.parse_pdf_bytes", side_effect=PyPdfError("bad")):
            assert asyncio.run(retriever._aload_single(result, session, asyncio.Semaphore(1))) is None

    def test_aload_single_unexpected_error_respects_continue_on_failure(self):
        """An unexpected error returns None when continuing, else propagates."""
        result = self._make_result()
        session = self._session_returning(self._response())

        lenient = ModifiedArxivRetriever(continue_on_failure=True)
        with patch(f"{MODULE}.PdfUtils.parse_pdf_bytes", side_effect=ValueError("weird")):
            assert asyncio.run(lenient._aload_single(result, session, asyncio.Semaphore(1))) is None

        strict = ModifiedArxivRetriever(continue_on_failure=False)
        session = self._session_returning(self._response())
        with patch(f"{MODULE}.PdfUtils.parse_pdf_bytes", side_effect=ValueError("weird")):
            with pytest.raises(ValueError, match="weird"):
                asyncio.run(strict._aload_single(result, session, asyncio.Semaphore(1)))

    # --- _build_metadata() ------------------------------------------------ #
    def test_build_metadata_minimal(self):
        """Default metadata holds only the five core fields with formatted values."""
        retriever = ModifiedArxivRetriever(load_all_available_meta=False)
        meta = retriever._build_metadata(self._make_result())
        assert set(meta) == {"Entry ID", "Published", "Title", "Authors", "Summary"}
        assert meta["Published"] == "2023-01-15"  # from updated, stringified
        assert meta["Authors"] == "Ada Lovelace, Alan Turing"

    def test_build_metadata_extended(self):
        """With load_all_available_meta the extra arXiv fields are included and flattened."""
        retriever = ModifiedArxivRetriever(load_all_available_meta=True)
        meta = retriever._build_metadata(self._make_result())
        assert meta["published_first_time"] == "2023-01-10"  # from published
        assert meta["links"] == ["http://link/a", "http://link/b"]
        assert meta["categories"] == ["cs.AI", "cs.LG"]
        assert meta["doi"] == "10.1000/xyz"

    # --- _get_summaries_as_docs() ---------------------------------------- #
    def test_summaries_builds_documents(self):
        """Each result becomes a Document whose content is the paper summary."""
        retriever = ModifiedArxivRetriever()
        result = self._make_result()
        with patch.object(ModifiedArxivRetriever, "_fetch_results", return_value=[result]):
            docs = retriever._get_summaries_as_docs("q")
        assert len(docs) == 1
        assert docs[0].page_content == "A concise summary."
        assert docs[0].metadata["Title"] == "A Title"

    def test_summaries_returns_error_document_on_arxiv_error(self):
        """An arXiv API error yields a single Document carrying the error text."""
        retriever = ModifiedArxivRetriever()
        err = ArxivError("http://x", 0, "boom")
        with patch.object(ModifiedArxivRetriever, "_fetch_results", side_effect=err):
            docs = retriever._get_summaries_as_docs("q")
        assert len(docs) == 1
        assert "Arxiv exception" in docs[0].page_content

    # --- _fetch_results() ------------------------------------------------- #
    def test_fetch_results_text_query_is_truncated(self):
        """A plaintext query is passed positionally and truncated to the max length."""
        retriever = ModifiedArxivRetriever(top_k_results=2)
        long_query = "x" * 400
        with patch(f"{MODULE}.Search") as m_search, patch(f"{MODULE}.Client") as m_client:
            m_client.return_value.results.return_value = ["r1", "r2"]
            out = retriever._fetch_results(long_query)
        (positional,), kwargs = m_search.call_args
        assert len(positional) == ModifiedArxivRetriever.ARXIV_MAX_QUERY_LENGTH
        assert kwargs["max_results"] == 2
        assert out == ["r1", "r2"]  # generator materialized to a list

    def test_fetch_results_identifier_query_uses_id_list(self):
        """A query of identifiers is passed via id_list rather than the free-text arg."""
        retriever = ModifiedArxivRetriever()
        with patch(f"{MODULE}.Search") as m_search, patch(f"{MODULE}.Client") as m_client:
            m_client.return_value.results.return_value = []
            retriever._fetch_results("2301.01234 2302.05678")
        _args, kwargs = m_search.call_args
        assert kwargs["id_list"] == ["2301.01234", "2302.05678"]

    # --- _is_arxiv_identifier() ------------------------------------------ #
    def test_is_arxiv_identifier_true_cases(self):
        """Modern, versioned, and legacy ids (single or multiple) are all recognized."""
        retriever = ModifiedArxivRetriever()
        assert retriever._is_arxiv_identifier("2301.01234") is True
        assert retriever._is_arxiv_identifier("2301.0123") is True  # pre-2015 4-digit
        assert retriever._is_arxiv_identifier("2301.01234v3") is True
        assert retriever._is_arxiv_identifier("2301.01234 2302.05678") is True
        assert retriever._is_arxiv_identifier("hep-th/9901001") is True  # legacy
        assert retriever._is_arxiv_identifier("math.AG/0309136") is True  # legacy + subject
        assert retriever._is_arxiv_identifier("hep-th/9901001v2") is True  # legacy + version

    def test_is_arxiv_identifier_false_cases(self):
        """Free text, mixed tokens, and bare/junk numeric strings are rejected."""
        retriever = ModifiedArxivRetriever()
        assert retriever._is_arxiv_identifier("machine learning") is False
        assert retriever._is_arxiv_identifier("2301.01234 hello") is False
        assert retriever._is_arxiv_identifier("1234567") is False  # bare 7 digits, no archive
        assert retriever._is_arxiv_identifier("1234567abc") is False  # junk after 7 digits
        assert retriever._is_arxiv_identifier("2313.01234") is False  # month 13 is invalid

    # --- sort mappings ---------------------------------------------------- #
    def test_sort_criterion_mapping_and_default(self):
        """Known sort_by strings map to enums; unknown ones fall back to Relevance."""
        assert ModifiedArxivRetriever(sort_by="submittedDate")._get_sort_criterion() == (SortCriterion.SubmittedDate)
        assert ModifiedArxivRetriever(sort_by="nonsense")._get_sort_criterion() == SortCriterion.Relevance

    def test_sort_order_mapping_and_default(self):
        """Known sort_order strings map to enums; unknown ones fall back to Descending."""
        assert ModifiedArxivRetriever(sort_order="ascending")._get_sort_order() == SortOrder.Ascending
        assert ModifiedArxivRetriever(sort_order="nonsense")._get_sort_order() == SortOrder.Descending


def _named(name):
    """A stand-in author object exposing `.name` (MagicMock treats name specially)."""
    obj = MagicMock()
    obj.name = name
    return obj


def _href(href):
    """A stand-in link object exposing `.href`."""
    obj = MagicMock()
    obj.href = href
    return obj
