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

import logging
import os
from asyncio import Semaphore
from asyncio import gather
from asyncio import to_thread
from typing import Any

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from bs4 import Tag
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.base_rag import BaseRag
from neuro_san_studio.coded_tools.base_rag import PostgresConfig
from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cap on how many URLs are processed at once (download + parse) in one load_documents call.
MAX_CONCURRENT_FETCHES: int = 5


class WebpageRag(CodedTool, BaseRag):
    """
    CodedTool implementation which provides a way to do RAG on webpages.

    Content is downloaded through the shared SSRF-hardened fetch path (SafeFetch):
    private/loopback/reserved hosts are rejected, DNS records are validated at
    connection time (anti DNS-rebinding), redirects are not followed, and response
    sizes are capped. Each URL is routed by content type: PDFs are parsed with pypdf
    (via SafeFetch.fetch_pdf_text) and HTML/text is stripped to plain text, so a PDF
    link is ingested as readable text instead of being embedded as binary garbage.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str | list[dict[str, Any]]:
        """
        Load webpages from URLs, build a vector store, and run a query against it.

        :param args: Dictionary containing:
          "query": search string
          "urls": list of urls
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
        # Deliberately Any: this comes straight from the LLM/hocon and may be a
        # bare string instead of a list; load_documents normalizes that case.
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

        # Every URL may have been skipped (unreachable/blocked/unsupported), leaving
        # an empty store whose retriever returns no documents. Surface that plainly
        # instead of handing the agent an empty list it cannot act on. A non-empty
        # store always returns its nearest chunks, so an empty list here means
        # "nothing was ingested", not merely "no strong match".
        if isinstance(results, list) and not results:
            return (
                "❌ No content could be retrieved from the provided URLs. "
                "They may be unreachable, blocked, or an unsupported content type."
            )
        return results

    async def load_documents(self, loader_args: dict[str, Any]) -> list[Document]:
        """
        Load documents from URLs through the SSRF-hardened fetch path.

        Each URL is processed concurrently (download + parse, capped at
        MAX_CONCURRENT_FETCHES in-flight URLs) over one shared protected session.
        A URL that fails to validate or download, or whose content type is a declared
        non-text binary, is logged and skipped so one bad URL does not discard the
        rest of the corpus. If the surrounding task is cancelled, the cancellation is
        re-raised only after every in-flight URL task has unwound, so the shared
        session never closes while a fetch is still using it.

        :param loader_args: Dictionary containing 'urls' (list of webpage/PDF URLs,
            or a single URL as a bare string).
        :return: One Document per successfully loaded URL, in input order.
        """
        urls: Any = loader_args.get("urls")
        # An LLM (or a hand-edited hocon) may pass a single URL as a bare string
        # instead of a list. A string is itself iterable, so the loop below would
        # "fetch" it one character at a time ("h", "t", "t", "p", ...), every
        # character failing URL validation, and the load would come back empty
        # with no hint why. Treat a single string as a one-item list instead.
        if isinstance(urls, str):
            urls = [urls]
        # Nothing to load (or no 'urls' key at all): return early rather than
        # opening a network session just to await an empty gather().
        if not urls:
            return []

        # Concurrency limiter. A Semaphore holds a fixed number of "slots"
        # (MAX_CONCURRENT_FETCHES); a coroutine must acquire one (via `async with
        # semaphore` in _load_single) and holds it for that URL's WHOLE processing —
        # download and parse — releasing it on block exit. So at most that many URLs
        # are in flight at any moment, which is polite to servers and bounds peak
        # memory (at most that many raw bodies held at once); the rest wait for a slot.
        semaphore: Semaphore = Semaphore(MAX_CONCURRENT_FETCHES)

        # One protected session is shared across all fetches so they reuse the
        # SSRF-validated connector (GlobalOnlyResolver) and its connection pool.
        async with SafeFetch.open_session() as session:
            # Build one coroutine per URL but do NOT await them here: awaiting inside
            # the loop would run the fetches one-after-another (sequentially). We just
            # collect the coroutine objects so gather() can run them together.
            tasks: list[Any] = []
            for url in urls:
                tasks.append(self._load_single(url, session, semaphore))
            # gather() launches all the coroutines on the event loop concurrently and
            # waits for every one to finish. It returns results in the SAME order as
            # `tasks` (input order, not whichever finished first). The semaphore above
            # is what actually caps how many are being processed (downloading or
            # parsing) at any instant.
            # Each result is a Document, or None for a URL that was skipped/failed
            # (_load_single returns None instead of raising, so one bad URL cannot
            # make gather abort the others).
            #
            # return_exceptions=True matters for CANCELLATION, the one thing that can
            # still escape _load_single (CancelledError is a BaseException, so the
            # broad `except Exception` there deliberately does not catch it). Without
            # it, gather() re-raises the FIRST child's CancelledError immediately,
            # while sibling tasks are still unwinding; this `async with` block would
            # then close the shared session under them, and they would die with
            # confusing secondary "session is closed" errors. With it, gather() waits
            # until EVERY child has finished unwinding before completing — and when
            # the gather itself was cancelled, asyncio still re-raises CancelledError
            # to our caller at that point — so the session only closes once nothing
            # is using it.
            results: list[Document | None | BaseException] = await gather(*tasks, return_exceptions=True)

        # Keep only the loaded Documents, preserving input order. None entries are
        # URLs skipped/failed inside _load_single (already logged there); anything
        # else is a stray BaseException collected by return_exceptions=True, which
        # bypassed _load_single's logging, so log it here.
        documents: list[Document] = []
        for result in results:
            if isinstance(result, Document):
                documents.append(result)
            elif result is not None:
                logger.error("Skipped a URL after an unexpected error: %r", result)
        return documents

    async def _load_single(self, url: str, session: ClientSession, semaphore: Semaphore) -> Document | None:
        """
        Fetch one URL, route PDF vs HTML/text, and convert it to a Document.

        Returns None (rather than raising) whenever a URL cannot contribute a
        document — a policy/validation failure, a download error, a declared
        non-text content type, or a parse failure — so a single bad URL never
        aborts the load.

        :param url: The webpage or PDF URL to fetch.
        :param session: The shared protected session created by open_session.
        :param semaphore: Caps how many URLs are processed (downloaded and parsed) at once.
        :return: The loaded Document, or None when the URL is skipped.
        """
        try:
            # validate_url is pure (no network); keep it outside the semaphore so a
            # rejected URL does not consume a concurrency slot.
            validated_url: str = SafeFetch.validate_url(url)
            # Acquire one of the semaphore's slots for the per-URL work below. The slot
            # is deliberately held through both the download AND the parse: that bounds
            # peak memory to a few raw bodies in flight, not just open connections. If
            # all slots are taken, execution pauses here until another coroutine exits
            # its `async with` block and frees one; release is automatic on block exit.
            async with semaphore:
                # A HEAD probe decides PDF vs HTML before any body is downloaded, so
                # a PDF is parsed with pypdf rather than run through the HTML stripper
                # (which would embed the raw %PDF bytes as garbage chunks).
                content_type: str
                prefetched_text: str | None
                content_type, prefetched_text = await SafeFetch.get_content_type(validated_url, session)

                if SafeFetch.is_pdf(content_type, validated_url):
                    pdf_text: str = await SafeFetch.fetch_pdf_text(validated_url, session)
                    # PDFs carry no HTML metadata; record only the source.
                    return Document(page_content=pdf_text, metadata={"source": validated_url})

                # An empty/missing Content-Type is treated as text rather than skipped:
                # WebBaseLoader (the loader this replaces) fetched regardless of type,
                # and _to_document keeps non-HTML bodies verbatim. Only a *declared*
                # non-text type (image, archive, ...) is skipped as noise.
                if content_type and not SafeFetch.is_text_content_type(content_type):
                    logger.warning("Skipping %s: unsupported content type '%s'.", validated_url, content_type)
                    return None

                # get_content_type only returns a body on its 405 GET fallback; reuse
                # it when present to avoid a second request, otherwise fetch the raw
                # markup so _to_document can read page metadata from it.
                raw: str
                if prefetched_text is not None:
                    raw = prefetched_text
                else:
                    raw = await SafeFetch.fetch_raw(validated_url, session)

                # BeautifulSoup parsing is blocking CPU work. Calling it directly would
                # occupy the single event-loop thread for its whole duration and freeze
                # every other coroutine (including the concurrent fetches) until it
                # returned. to_thread() runs _to_document on a background worker thread
                # and awaits its result, so the event loop stays free to drive the other
                # downloads meanwhile (SafeFetch.fetch_pdf_text offloads pypdf the same way).
                document: Document = await to_thread(self._to_document, validated_url, raw)
        # A broad catch keeps the batch resilient: URL-policy failures (ValueError),
        # network/HTTP failures (ClientError), and HTML-parse failures (e.g. a
        # RecursionError on pathologically nested markup) all mean "skip this one
        # URL", never "abort the whole load". The error is logged so nothing fails
        # silently.
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error("Failed to load webpage %s: %s", url, error)
            return None

        logger.info("Successfully loaded webpage from %s", validated_url)
        return document

    @staticmethod
    def _to_document(url: str, raw: str) -> Document:
        """
        Convert a raw page body into a Document, stripping HTML when present.

        An HTML body is parsed exactly once: the same soup yields both the
        WebBaseLoader-style metadata (title/description/language) and the stripped
        text. A non-HTML body (plain text, markdown, CSV, ...) is kept verbatim,
        mirroring SafeFetch.parse_raw_text's passthrough, so its formatting is not
        destroyed by the HTML stripper.

        :param url: The source URL, recorded in the Document metadata.
        :param raw: The raw (unstripped) page body.
        :return: A Document whose content is the page text and whose metadata carries
                 source and any available title/description/language.
        """
        metadata: dict[str, Any] = {"source": url}

        # A body that does not start with a tag is not markup; return it unchanged so
        # newlines/structure (e.g. markdown, CSV) survive. Same guard parse_raw_text uses.
        if not raw.lstrip().startswith("<"):
            return Document(page_content=raw, metadata=metadata)

        # Parse the markup once and reuse the soup for both metadata and text.
        soup: BeautifulSoup = BeautifulSoup(raw, "html.parser")

        # Title/description/language are best-effort: include each only when the page
        # actually provides it, matching WebBaseLoader's metadata shape.
        if soup.title and soup.title.get_text(strip=True):
            metadata["title"] = soup.title.get_text(strip=True)
        # find() by tag name only ever matches Tag nodes (NavigableString results
        # need a `string=` search), so Tag | None is the accurate type here.
        description: Tag | None = soup.find("meta", attrs={"name": "description"})
        if description and description.get("content"):
            metadata["description"] = description["content"].strip()
        html_tag: Tag | None = soup.find("html")
        if html_tag and html_tag.get("lang"):
            metadata["language"] = html_tag["lang"]

        # Drop non-content nodes, then extract text — the same transform
        # SafeFetch.parse_raw_text applies, run on the soup we already built.
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text: str = soup.get_text(separator="\n", strip=True)
        return Document(page_content=text, metadata=metadata)
