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

"""Tests for the PDF RAG coded tool's SafeFetch-backed document loading."""

import asyncio
import os
import tempfile
from functools import partial
from typing import Any
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from aiohttp import ClientError

from neuro_san_studio.coded_tools.pdf_rag import PdfRag
from neuro_san_studio.coded_tools.utils.pdf_utils import PDF_HEADER_WINDOW
from neuro_san_studio.coded_tools.utils.pdf_utils import PdfUtils
from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch

PDF_BYTES = b"%PDF-1.4 fake body"
# A "PDF" longer than the header sniff window, so the local reader has to fetch it in
# two pieces (head + remainder). Tests built on it pin the byte-budget arithmetic that
# fixtures shorter than PDF_HEADER_WINDOW cannot observe.
BIG_PDF_BYTES: bytes = PDF_BYTES + b"x" * (PDF_HEADER_WINDOW * 3)
PAGE_TEXTS = ["Page one text", "Page two text"]


class TestPdfRag(TestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for PdfRag: SSRF-hardened remote loading, local paths, input guards."""

    def setUp(self):
        # Bypass BaseRag.__init__, which instantiates OpenAIEmbeddings and therefore
        # requires an OPENAI_API_KEY; these tests never embed or build a store.
        self.tool = object.__new__(PdfRag)

    def _load(self, urls: list[str]) -> list:
        """
        Run load_documents with the given items against mocked session and parsing.

        :param urls: The list of URLs/paths to pass to load_documents.
        :return: The list of loaded Documents.
        """
        return asyncio.run(self.tool.load_documents({"urls": urls}))

    @staticmethod
    def _make_session_cm() -> MagicMock:
        """
        Build an async-context-manager mock standing in for SafeFetch.open_session().

        :return: A MagicMock usable as ``async with`` that yields a mock session.
        """
        session = MagicMock()
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        return session_cm

    @staticmethod
    def _write_temp_pdf_file(content: bytes) -> str:
        """
        Write bytes to a fresh temp file carrying a .pdf suffix and return its path.

        The caller is responsible for os.unlink() once the test is done with it.

        :param content: The bytes to store in the file.
        :return: The absolute path of the temp file.
        """
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(content)
            return handle.name

    @staticmethod
    async def _download_failing_bad_urls(url: str, _session: Any) -> bytes:
        """
        Stand in for download_pdf_bytes: return PDF bytes, failing URLs containing 'bad'.

        :param url: The URL being downloaded.
        :param _session: The shared session; unused.
        :return: The stub PDF bytes for any URL not containing 'bad'.
        :raises ClientError: For any URL containing 'bad'.
        """
        if "bad" in url:
            raise ClientError("url_not_accessible: connection reset")
        return PDF_BYTES

    @staticmethod
    async def _record_session_close(order: list[str], *_args: Any) -> bool:
        """
        Stand in for the session context manager's __aexit__, recording when it runs.

        :param order: The shared event-order list the test asserts on.
        :param _args: The (exc_type, exc, tb) triple passed to __aexit__ (plus the mock
            itself, prepended by MagicMock's magic-method plumbing); unused.
        :return: False so any exception keeps propagating.
        """
        order.append("session_closed")
        return False

    @staticmethod
    async def _blocked_download(order: list[str], url: str, _session: Any) -> Any:
        """
        Stand in for download_pdf_bytes: block until cancelled, then record the unwind.

        :param order: The shared event-order list the test asserts on.
        :param url: The URL being downloaded; 'b.pdf' takes several extra event-loop
            ticks to unwind, which is what exposes a premature session close (a single
            tick is absorbed by asyncio's own deferred done-callbacks).
        :param _session: The shared session; unused.
        :return: Never returns normally.
        """
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            if url.endswith("b.pdf"):
                for _ in range(5):
                    await asyncio.sleep(0)
            order.append("child_unwound")
            raise

    @staticmethod
    async def _cancel_mid_flight_load(tool: PdfRag) -> None:
        """
        Start a two-URL load, cancel it once both item tasks are in flight, and await teardown.

        :param tool: The PdfRag instance under test.
        :raises asyncio.CancelledError: always — re-raised from the cancelled load once
            its teardown (children unwound, session closed) has completed.
        """
        task = asyncio.ensure_future(
            tool.load_documents({"urls": ["http://example.com/a.pdf", "http://example.com/b.pdf"]})
        )
        # A few no-op ticks let load_documents start and both children block in the download.
        for _ in range(3):
            await asyncio.sleep(0)
        task.cancel()
        await task

    def test_remote_pdf_produces_per_page_documents(self):
        """A downloaded PDF yields one Document per page with source/page/total_pages metadata."""
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=PDF_BYTES)) as mock_dl,
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=PAGE_TEXTS) as mock_parse,
        ):
            docs = self._load(["http://example.com/report.pdf"])

        mock_dl.assert_awaited_once()
        mock_parse.assert_called_once_with(PDF_BYTES)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].page_content, "Page one text")
        self.assertEqual(docs[0].metadata, {"source": "http://example.com/report.pdf", "page": 0, "total_pages": 2})
        self.assertEqual(docs[1].metadata["page"], 1)

    def test_local_path_reads_file_without_network(self):
        """A local file path is read from disk; no download is attempted."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(PDF_BYTES)
            local_path = handle.name
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock()) as mock_dl,
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["local text"]) as mock_parse,
            ):
                docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        mock_dl.assert_not_awaited()
        # The parser received the actual bytes read from disk.
        mock_parse.assert_called_once_with(PDF_BYTES)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], local_path)

    def test_private_ip_url_skipped_without_download(self):
        """A URL that fails SSRF validation is skipped and never downloaded; others still load."""
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=PDF_BYTES)) as mock_dl,
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]),
        ):
            # validate_url is NOT mocked, so the private-IP URL is rejected for real.
            docs = self._load(["http://192.168.1.1/internal.pdf", "http://example.com/good.pdf"])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/good.pdf")
        mock_dl.assert_awaited_once()  # only the allowed URL reached the network

    def test_failed_download_does_not_discard_other_pdfs(self):
        """One unreachable PDF is logged and skipped; the rest of the corpus survives."""
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(side_effect=self._download_failing_bad_urls)),
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]),
        ):
            docs = self._load(["http://bad.example.com/a.pdf", "http://example.com/good.pdf"])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/good.pdf")

    def test_parse_failure_skips_only_that_item(self):
        """A pypdf parse error skips that item instead of aborting the whole load."""
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=b"not a pdf")),
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", side_effect=ValueError("bad pdf")),
        ):
            docs = self._load(["http://example.com/broken.pdf"])

        self.assertEqual(docs, [])  # skipped, not raised

    def test_missing_local_file_is_skipped(self):
        """A nonexistent local path is logged and skipped rather than raising."""
        with patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()):
            docs = self._load(["/nonexistent/dir/missing.pdf"])

        self.assertEqual(docs, [])

    def test_bare_string_urls_is_treated_as_single_item(self):
        """A single URL passed as a bare string loads as one PDF, not one fetch per character."""
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=PDF_BYTES)) as mock_dl,
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=PAGE_TEXTS),
        ):
            docs = asyncio.run(self.tool.load_documents({"urls": "http://example.com/report.pdf"}))

        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/report.pdf")
        # Exactly one download — not one per character of the string.
        mock_dl.assert_awaited_once()

    def test_unsupported_scheme_is_skipped_with_message(self):
        """file:// and s3:// items are skipped with an explicit message; the corpus survives.

        The old negative-space routing handed every non-http string to open(),
        which failed with a misleading "file not found" for such URLs.
        """
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=PDF_BYTES)) as mock_dl,
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]),
        ):
            with self.assertLogs("neuro_san_studio.coded_tools.pdf_rag", level="WARNING") as logs:
                docs = self._load(
                    [
                        "s3://bucket/key.pdf",
                        "file:///path/to/x.pdf",
                        "x://host/file.pdf",
                        "http://example.com/good.pdf",
                    ]
                )

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/good.pdf")
        mock_dl.assert_awaited_once()  # only the http URL reached the network
        joined_logs: str = "\n".join(logs.output)
        self.assertIn("unsupported URL scheme 's3'", joined_logs)
        self.assertIn("unsupported URL scheme 'file'", joined_logs)
        # A one-letter scheme with URI syntax is NOT mistaken for a drive letter.
        self.assertIn("unsupported URL scheme 'x'", joined_logs)

    def test_whitespace_padded_remote_url_is_routed_as_remote(self):
        """A remote URL with surrounding whitespace is downloaded, not mistaken for a local path.

        SafeFetch.validate_url strips padding, so the routing decision must be made
        on the stripped candidate too; parsing the raw string would see no scheme.
        """
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=PDF_BYTES)) as mock_dl,
            patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]),
        ):
            docs = self._load(["  http://example.com/padded.pdf  "])

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], "http://example.com/padded.pdf")
        mock_dl.assert_awaited_once()

    def test_windows_drive_path_is_treated_as_local_file(self):
        """A drive-letter path parses with a one-letter scheme but must route to the local reader."""
        with (
            patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock()) as mock_dl,
        ):
            with self.assertLogs("neuro_san_studio.coded_tools.pdf_rag", level="WARNING") as logs:
                docs = self._load(["C:\\docs\\file.pdf"])

        # The path does not exist on this machine, so it is skipped as a file-read
        # failure — not as an unsupported scheme, and never as a download.
        self.assertEqual(docs, [])
        mock_dl.assert_not_awaited()
        self.assertNotIn("unsupported URL scheme", "\n".join(logs.output))

    def test_oversized_local_file_is_skipped(self):
        """A local file over the byte cap is skipped instead of being read into memory.

        The fixture starts with a real PDF header so the header sniff passes and the
        size cap is the check that rejects it (the log must say response_too_large).
        """
        local_path: str = self._write_temp_pdf_file(PDF_BYTES)
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                # Shrink the cap below the file size so the tiny temp file trips it.
                patch("neuro_san_studio.coded_tools.pdf_rag.MAX_RESPONSE_BYTES", len(PDF_BYTES) - 1),
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]) as mock_parse,
            ):
                with self.assertLogs("neuro_san_studio.coded_tools.pdf_rag", level="ERROR") as logs:
                    docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        self.assertEqual(docs, [])
        mock_parse.assert_not_called()
        joined_logs: str = "\n".join(logs.output)
        self.assertIn("response_too_large", joined_logs)
        self.assertNotIn("not_a_pdf", joined_logs)

    def test_non_pdf_local_file_is_skipped_before_parse(self) -> None:
        """An HTML error page saved as *.pdf is skipped with a not_a_pdf message; pypdf never sees it.

        Previously such a file was read in full and handed to pypdf, whose
        "Stream has ended unexpectedly" pointed nowhere near the real problem.
        """
        local_path: str = self._write_temp_pdf_file(b"<html><body>404</body></html>")
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]) as mock_parse,
            ):
                with self.assertLogs("neuro_san_studio.coded_tools.pdf_rag", level="ERROR") as logs:
                    docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        self.assertEqual(docs, [])
        mock_parse.assert_not_called()
        joined_logs: str = "\n".join(logs.output)
        self.assertIn("not_a_pdf", joined_logs)
        self.assertIn(local_path, joined_logs)

    def test_local_file_with_leading_junk_before_header_still_loads(self) -> None:
        """Junk bytes ahead of the %PDF- marker (within the sniff window) do not cause a skip.

        Adobe's implementation notes allow the header anywhere in the first 1024
        bytes and pypdf parses such files, so the sniff must not be a strict prefix
        check. The parser receives the FULL bytes, junk included; pypdf handles it.
        """
        junk_then_pdf: bytes = b"j" * 300 + PDF_BYTES
        local_path: str = self._write_temp_pdf_file(junk_then_pdf)
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]) as mock_parse,
            ):
                # A skip is reported via logger.error, so no ERROR record means no skip.
                with self.assertNoLogs("neuro_san_studio.coded_tools.pdf_rag", level="ERROR"):
                    docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        mock_parse.assert_called_once_with(junk_then_pdf)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].metadata["source"], local_path)

    def test_header_check_runs_before_full_read(self) -> None:
        """The header sniff rejects a non-PDF before the size cap is even reached.

        With the cap shrunk below the file size, a size-check-first implementation
        would report response_too_large; seeing not_a_pdf instead proves the sniff
        runs before the size check. The fixture is longer than PDF_HEADER_WINDOW so
        the head read alone cannot cover the file.
        """
        non_pdf: bytes = b"<html>" + b"x" * (PDF_HEADER_WINDOW * 2) + b"</html>"
        local_path: str = self._write_temp_pdf_file(non_pdf)
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                # Cap below THIS fixture's size: a full read would report response_too_large.
                patch("neuro_san_studio.coded_tools.pdf_rag.MAX_RESPONSE_BYTES", len(non_pdf) - 1),
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]) as mock_parse,
            ):
                with self.assertLogs("neuro_san_studio.coded_tools.pdf_rag", level="ERROR") as logs:
                    docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        self.assertEqual(docs, [])
        mock_parse.assert_not_called()
        joined_logs: str = "\n".join(logs.output)
        self.assertIn("not_a_pdf", joined_logs)
        self.assertNotIn("response_too_large", joined_logs)

    def test_local_file_larger_than_header_window_reaches_parser_intact(self) -> None:
        """A local PDF longer than the sniff window is handed to the parser whole, not truncated.

        The reader fetches the head and the remainder separately; dropping or
        mis-sizing the remainder read would silently truncate every real PDF to its
        first PDF_HEADER_WINDOW bytes.
        """
        local_path: str = self._write_temp_pdf_file(BIG_PDF_BYTES)
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]) as mock_parse,
            ):
                docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        mock_parse.assert_called_once_with(BIG_PDF_BYTES)
        self.assertEqual(len(docs), 1)

    def test_oversized_local_file_larger_than_header_window_is_skipped(self) -> None:
        """A local PDF longer than the sniff window still trips the byte cap when it exceeds it.

        The head already spent part of the byte budget, so the remainder read must be
        shortened by exactly that amount for the cap to stay exact.
        """
        local_path: str = self._write_temp_pdf_file(BIG_PDF_BYTES)
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                # One byte under the file size: exactly the smallest cap that must reject it.
                patch("neuro_san_studio.coded_tools.pdf_rag.MAX_RESPONSE_BYTES", len(BIG_PDF_BYTES) - 1),
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]) as mock_parse,
            ):
                with self.assertLogs("neuro_san_studio.coded_tools.pdf_rag", level="ERROR") as logs:
                    docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        self.assertEqual(docs, [])
        mock_parse.assert_not_called()
        self.assertIn("response_too_large", "\n".join(logs.output))

    def test_local_file_exactly_at_cap_larger_than_header_window_loads(self) -> None:
        """A local PDF whose size equals the cap is accepted whole (the limit is inclusive).

        Together with the one-byte-over sibling this pins both sides of the boundary,
        so an off-by-one in the remainder read cannot hide.
        """
        local_path: str = self._write_temp_pdf_file(BIG_PDF_BYTES)
        try:
            with (
                patch.object(SafeFetch, "open_session", return_value=self._make_session_cm()),
                patch("neuro_san_studio.coded_tools.pdf_rag.MAX_RESPONSE_BYTES", len(BIG_PDF_BYTES)),
                patch.object(PdfUtils, "parse_pdf_bytes_per_page", return_value=["ok"]) as mock_parse,
            ):
                with self.assertNoLogs("neuro_san_studio.coded_tools.pdf_rag", level="ERROR"):
                    docs = self._load([local_path])
        finally:
            os.unlink(local_path)

        mock_parse.assert_called_once_with(BIG_PDF_BYTES)
        self.assertEqual(len(docs), 1)

    def test_cancellation_closes_session_only_after_children_unwind(self):
        """Cancelling the load lets every in-flight item unwind before the session closes.

        Without return_exceptions=True on the gather, the first child's CancelledError
        propagates as soon as that child finishes unwinding, and the shared session is
        closed while the slower sibling is still using it.
        """
        order: list[str] = []

        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        # partial() binds the shared order list; the helpers are static methods of this class.
        session_cm.__aexit__ = partial(self._record_session_close, order)

        with (
            patch.object(SafeFetch, "open_session", return_value=session_cm),
            patch.object(SafeFetch, "download_pdf_bytes", new=partial(self._blocked_download, order)),
        ):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(self._cancel_mid_flight_load(self.tool))

        self.assertEqual(order, ["child_unwound", "child_unwound", "session_closed"])

    def test_empty_url_list_returns_empty_without_session(self):
        """An empty item list returns [] without ever opening a network session."""
        with patch.object(SafeFetch, "open_session") as mock_session:
            docs = self._load([])

        self.assertEqual(docs, [])
        mock_session.assert_not_called()

    def test_all_items_skipped_returns_clear_message(self):
        """When nothing is ingested, async_invoke returns a clear message, not an empty list."""
        with (
            patch.object(PdfRag, "generate_vector_store", new=AsyncMock(return_value=MagicMock())),
            patch.object(PdfRag, "query_vectorstore", new=AsyncMock(return_value=[])),
        ):
            result = asyncio.run(self.tool.async_invoke({"query": "q", "urls": ["http://example.com/x.pdf"]}, {}))

        self.assertIn("No content could be retrieved", result)

    def test_non_list_urls_is_refused_without_network(self):
        """A non-list, non-string 'urls' (e.g. an int from a hand-edited hocon) is refused, not crashed on."""
        with patch.object(SafeFetch, "open_session") as mock_session:
            result = asyncio.run(self.tool.async_invoke({"query": "q", "urls": 123}, {}))
            docs = asyncio.run(self.tool.load_documents({"urls": 123}))

        self.assertIn("Invalid input: 'urls' must be a list", result)
        self.assertIn("got int", result)
        self.assertEqual(docs, [])  # the loader refuses it too, for direct callers
        mock_session.assert_not_called()

    def test_missing_query_or_urls_returns_error_without_network(self):
        """async_invoke reports missing inputs before any session is opened."""
        with patch.object(SafeFetch, "open_session") as mock_session:
            no_query = asyncio.run(self.tool.async_invoke({"urls": ["http://example.com/x.pdf"]}, {}))
            no_urls = asyncio.run(self.tool.async_invoke({"query": "hello"}, {}))

        self.assertIn("Missing required input: 'query'", no_query)
        self.assertIn("Missing required input: 'urls'", no_urls)
        mock_session.assert_not_called()
