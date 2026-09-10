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

"""Tool module for doing RAG from a pdf file"""

import logging
import os
from asyncio import Semaphore
from asyncio import gather
from asyncio import to_thread
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientSession
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.base_rag import BaseRag
from neuro_san_studio.coded_tools.base_rag import PostgresConfig
from neuro_san_studio.coded_tools.utils.pdf_utils import PdfUtils
from neuro_san_studio.coded_tools.utils.safe_fetch import MAX_RESPONSE_BYTES
from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cap on how many PDFs are processed at once (download/read + parse) in one load_documents call.
MAX_CONCURRENT_FETCHES: int = 5


class PdfRag(CodedTool, BaseRag):
    """
    CodedTool implementation which provides a way to do RAG on pdf files.

    Remote PDFs are downloaded through the shared SSRF-hardened fetch path
    (SafeFetch): private/loopback/reserved hosts are rejected, DNS records are
    validated at connection time (anti DNS-rebinding), redirects are not followed,
    and response sizes are capped. Local file paths (a documented input form for
    this tool) are read directly from disk — SafeFetch governs network fetches
    only — subject to the same byte cap as downloads. Items with any other URL
    scheme (file://, s3://, ...) are skipped with a logged message. All PDFs are
    parsed with pypdf via the shared PdfUtils helper, one Document per page so
    page numbers survive into the vector store metadata.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str | list[dict[str, Any]]:
        """
        Load PDFs from URLs or file paths, build a vector store, and query it.

        :param args: Dictionary containing:
          "query": search string
          "urls": list of PDF URLs and/or local file paths
          "save_vector_store": save to JSON file if True
          "vector_store_path": relative path to this file

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool implementation
            adding the data is not invoke()-ed more than once.

            Keys expected for this implementation are:
                None
        :return: Retrieved chunks as a list of {"content", "metadata"} dicts,
            or an error/status message string.
        """
        # Extract arguments from the input dictionary
        query: str = args.get("query", "")
        # Deliberately Any: this comes from the operator's hocon args block (the
        # toolbox schema exposes only 'query' to the LLM) and may be a bare string
        # instead of a list; load_documents normalizes that case.
        urls: Any = args.get("urls")

        # Validate presence of required inputs
        if not query:
            return "❌ Missing required input: 'query'."
        if not urls:
            return "❌ Missing required input: 'urls'."

        # Vector store type
        vector_store_type: str = args.get("vector_store_type", "in_memory")

        # Save the generated vector store as a JSON file if True
        self.save_vector_store = args.get("save_vector_store", False)

        # Configure the vector store path
        self.configure_vector_store_path(args.get("vector_store_path"))

        # For PostgreSQL vector store
        if vector_store_type == "postgres":
            postgres_config = PostgresConfig(
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST"),
                port=os.getenv("POSTGRES_PORT"),
                database=os.getenv("POSTGRES_DB"),
                table_name=args.get("table_name"),
            )
        else:
            postgres_config = None

        # Prepare the vector store
        vector_store: VectorStore = await self.generate_vector_store(
            loader_args={"urls": urls}, postgres_config=postgres_config, vector_store_type=vector_store_type
        )

        # Run the query against the vector store
        results: Any = await self.query_vectorstore(vector_store, query)

        # Every input may have been skipped (unreachable/blocked/unparseable),
        # leaving an empty store whose retriever returns no documents. Surface that
        # plainly instead of handing the agent an empty list it cannot act on. A
        # non-empty store always returns its nearest chunks, so an empty list here
        # means "nothing was ingested", not merely "no strong match".
        if isinstance(results, list) and not results:
            return (
                "❌ No content could be retrieved from the provided PDFs. "
                "They may be unreachable, blocked, missing, or not parseable as PDF."
            )
        return results

    async def load_documents(self, loader_args: dict[str, Any]) -> list[Document]:
        """
        Load PDF documents from URLs and/or local file paths.

        Each item is processed concurrently (download/read + parse, capped at
        MAX_CONCURRENT_FETCHES in flight) — remote items over one shared
        SSRF-protected session, local items straight from disk. An item that fails
        to validate, download, or parse is logged and skipped so one bad input does
        not discard the rest of the corpus. If the surrounding task is cancelled,
        the cancellation is re-raised only after every in-flight item has unwound,
        so the shared session never closes while a download is still using it.

        :param loader_args: Dictionary containing 'urls' (list of PDF URLs or file
            paths, or a single one as a bare string).
        :return: One Document per page of each successfully loaded PDF, in input
                 order.
        """
        urls: Any = loader_args.get("urls")
        # A hand-edited hocon may pass a single URL/path as a bare string instead
        # of a list. A string is itself iterable, so the loop below would "load"
        # it one character at a time, every character failing, and the whole run
        # would come back empty with no hint why. Treat a single string as a
        # one-item list instead.
        if isinstance(urls, str):
            urls = [urls]
        # Nothing to do (or no 'urls' key at all); return early rather than
        # opening a network session just to await an empty gather().
        if not urls:
            return []

        # Concurrency limiter. A Semaphore holds a fixed number of "slots"
        # (MAX_CONCURRENT_FETCHES); a coroutine must acquire one (via `async with
        # semaphore` in _load_single) and holds it for that item's WHOLE processing —
        # download/read and parse — releasing it on block exit. So at most that many
        # PDFs are in flight at any moment, which is polite to servers and bounds
        # peak memory (each raw PDF can be megabytes); the rest wait for a slot.
        semaphore: Semaphore = Semaphore(MAX_CONCURRENT_FETCHES)
        # One protected session is shared by all remote downloads so they reuse the
        # SSRF-validated connector (GlobalOnlyResolver) and its connection pool. It
        # costs nothing until a request is made, so a list of only local paths is
        # fine — the session simply goes unused.
        async with SafeFetch.open_session() as session:
            # Build one coroutine per item but do NOT await them here: awaiting
            # inside the loop would run them one-after-another (sequentially).
            tasks: list[Any] = []
            for url in urls:
                tasks.append(self._load_single(url, session, semaphore))
            # gather() launches all the coroutines on the event loop concurrently
            # and waits for every one to finish, returning results in the SAME
            # order as `tasks`. Each result is a list of per-page Documents, or
            # None for an item that was skipped/failed (_load_single returns None
            # instead of raising, so one bad item cannot make gather abort the rest).
            #
            # return_exceptions=True matters for CANCELLATION, the one thing that
            # can still escape _load_single (CancelledError is a BaseException, so
            # the broad `except Exception` there deliberately does not catch it).
            # Without it, gather() re-raises the FIRST child's CancelledError
            # immediately, while sibling tasks are still unwinding; this
            # `async with` block would then close the shared session under them,
            # and they would die with confusing secondary "session is closed"
            # errors. With it, gather() waits until EVERY child has finished
            # unwinding before completing — and when the gather itself was
            # cancelled, asyncio still re-raises CancelledError to our caller at
            # that point — so the session only closes once nothing is using it.
            results: list[list[Document] | None | BaseException] = await gather(*tasks, return_exceptions=True)

        # Flatten the per-item page lists, dropping skipped items and preserving
        # input order (and page order within each PDF). None entries were already
        # logged by _load_single; anything else is a stray BaseException collected
        # by return_exceptions=True, which bypassed _load_single's logging, so log
        # it here.
        documents: list[Document] = []
        for result in results:
            if isinstance(result, list):
                documents.extend(result)
            elif result is not None:
                logger.error("Skipped a PDF after an unexpected error: %r", result)
        return documents

    async def _load_single(self, url: str, session: ClientSession, semaphore: Semaphore) -> list[Document] | None:
        """
        Load one PDF (remote URL or local path) into per-page Documents.

        Returns None (rather than raising) whenever an item cannot contribute
        documents — an unsupported URL scheme, a policy/validation failure, a
        download or file-read error, or a parse failure — so a single bad input
        never aborts the load.

        :param url: The PDF URL (http/https) or local file path to load.
        :param session: The shared protected session created by open_session.
        :param semaphore: Caps how many PDFs are processed (fetched and parsed) at once.
        :return: One Document per page, or None when the item is skipped.
        """
        try:
            # Route explicitly by URL scheme. http(s) means a remote download
            # through SafeFetch. No scheme at all means a local file path, a
            # documented input form this tool has always accepted (see
            # registries/tools/pdf_rag.hocon). A single-letter "scheme" is a
            # Windows drive letter ("C:\\docs\\file.pdf" parses with scheme "c")
            # only when the rest is path syntax; with URI syntax ("x://host/f.pdf")
            # it is an unsupported scheme like any other. Everything else
            # (file://, s3://, ftp://, or a typo) is skipped with an explicit
            # message — the old negative-space routing handed every non-http
            # string to open(), which failed with a misleading "file not found"
            # for URLs this tool simply does not support. Only network fetches go
            # through the SSRF policy — a local path is operator-supplied
            # configuration, not a URL to validate.
            parsed_scheme: str = urlparse(url).scheme.lower()
            is_drive_letter: bool = len(parsed_scheme) == 1 and "://" not in url
            if parsed_scheme in ("http", "https"):
                validated_url: str = SafeFetch.validate_url(url)
                async with semaphore:
                    data: bytes = await SafeFetch.download_pdf_bytes(validated_url, session)
                    # pypdf parsing is blocking CPU work; to_thread() runs it on a
                    # worker thread so the event loop stays free to drive the other
                    # concurrent downloads (same pattern as SafeFetch.fetch_pdf_text).
                    page_texts: list[str] = await to_thread(PdfUtils.parse_pdf_bytes_per_page, data)
                source: str = validated_url
            elif parsed_scheme and not is_drive_letter:
                logger.warning(
                    "Skipping %s: unsupported URL scheme '%s'. Use an http(s) URL or a local file path.",
                    url,
                    parsed_scheme,
                )
                return None
            else:
                async with semaphore:
                    # File I/O and parsing are both blocking; do the whole read+parse
                    # on a worker thread.
                    page_texts = await to_thread(self._read_local_pdf_pages, url)
                source = url
        # A broad catch keeps the batch resilient: URL-policy failures (ValueError),
        # network/HTTP failures (ClientError), missing/unreadable files (OSError),
        # and pypdf parse failures all mean "skip this one item", never "abort the
        # whole load". The error is logged so nothing fails silently.
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error("Failed to load PDF %s: %s", url, error)
            return None

        logger.info("Successfully loaded PDF file from %s", source)

        # One Document per page, mirroring the granularity of the previous
        # PyMuPDFLoader-based loader so page numbers survive into the vector-store
        # metadata (chunking downstream does not preserve them otherwise).
        total_pages: int = len(page_texts)
        documents: list[Document] = []
        for page_index, page_text in enumerate(page_texts):
            documents.append(
                Document(
                    page_content=page_text,
                    metadata={"source": source, "page": page_index, "total_pages": total_pages},
                )
            )
        return documents

    @staticmethod
    def _read_local_pdf_pages(path: str) -> list[str]:
        """
        Read a local PDF file and extract its text, one string per page.

        Blocking (file I/O + pypdf parse); callers run it via asyncio.to_thread.

        :param path: The local filesystem path of the PDF.
        :return: The extracted text of each page, in page order.
        :raises OSError: When the file is missing or unreadable.
        :raises ValueError: response_too_large when the file exceeds MAX_RESPONSE_BYTES.
        """
        # Apply the same byte cap the remote path enforces, as a bound on the read
        # itself rather than an os.path.getsize() pre-check: a size probe is not a
        # hard cap (special files such as /dev/zero report size 0, and a regular
        # file can grow or be replaced between the probe and the read). Reading at
        # most one byte past the cap is cheap and makes the limit unconditional.
        with open(path, "rb") as pdf_file:
            data: bytes = pdf_file.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError(f"response_too_large: '{path}' exceeds the {MAX_RESPONSE_BYTES}-byte limit.")
        return PdfUtils.parse_pdf_bytes_per_page(data)
