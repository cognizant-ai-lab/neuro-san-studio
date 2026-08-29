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
from typing import Any

from aiohttp import ClientError
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.base_rag import BaseRag
from neuro_san_studio.coded_tools.base_rag import PostgresConfig
from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cap on simultaneous downloads within one load_documents call.
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

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
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
        :return: Text result from querying the built vector store,
            or error message
        """
        # Extract arguments from the input dictionary
        query: str = args.get("query", "")
        urls: list[str] = args.get("urls", [])

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
        return await self.query_vectorstore(vector_store, query)

    async def load_documents(self, loader_args: dict[str, Any]) -> list[Document]:
        """
        Load documents from URLs through the SSRF-hardened fetch path.

        Each URL is fetched concurrently (capped by MAX_CONCURRENT_FETCHES) over one
        shared protected session. A URL that fails to validate or download, or whose
        content type is neither PDF nor text, is logged and skipped so one bad URL
        does not discard the rest of the corpus.

        :param loader_args: Dictionary containing 'urls' (list of webpage/PDF URLs).
        :return: One Document per successfully loaded URL, in input order.
        """
        urls: list[str] = loader_args.get("urls", [])

        semaphore: Semaphore = Semaphore(MAX_CONCURRENT_FETCHES)
        # One protected session is shared across all fetches so they reuse the
        # SSRF-validated connector (GlobalOnlyResolver) and its connection pool.
        async with SafeFetch.open_session() as session:
            tasks: list[Any] = []
            for url in urls:
                tasks.append(self._load_single(url, session, semaphore))
            results: list[Document | None] = await gather(*tasks)

        # Drop the None entries (skipped/failed URLs), preserving input order.
        documents: list[Document] = []
        for document in results:
            if document is not None:
                documents.append(document)
        return documents

    async def _load_single(self, url: str, session: ClientSession, semaphore: Semaphore) -> Document | None:
        """
        Fetch one URL, route PDF vs HTML/text, and convert it to a Document.

        Returns None (rather than raising) whenever a URL cannot contribute a
        document — a policy/validation failure, a download error, or a content type
        that is neither PDF nor text — so a single bad URL never aborts the load.

        :param url: The webpage or PDF URL to fetch.
        :param session: The shared protected session created by open_session.
        :param semaphore: Caps how many downloads run concurrently.
        :return: The loaded Document, or None when the URL is skipped.
        """
        try:
            # validate_url is pure (no network); keep it outside the semaphore so a
            # rejected URL does not consume a concurrency slot.
            validated_url: str = SafeFetch.validate_url(url)
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

                if not SafeFetch.is_text_content_type(content_type):
                    # Images, archives, and other binaries would only add noise
                    # chunks to the vector store, so skip them instead of decoding
                    # arbitrary bytes as text.
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
        # ValueError = SafeFetch policy violation (bad scheme, private host,
        # redirect); ClientError = HTTP/network/timeout/PDF-parse failure. Both mean
        # "skip this URL", never "abort the whole load".
        except (ClientError, ValueError) as error:
            logger.error("Failed to load webpage %s: %s", url, error)
            return None

        logger.info("Successfully loaded webpage from %s", validated_url)
        return self._to_document(validated_url, raw)

    @staticmethod
    def _to_document(url: str, raw: str) -> Document:
        """
        Convert a raw HTML page body into a Document with WebBaseLoader-style metadata.

        :param url: The source URL, recorded in the Document metadata.
        :param raw: The raw (unstripped) page body.
        :return: A Document whose content is the stripped page text and whose
                 metadata carries source and any available title/description/language.
        """
        soup = BeautifulSoup(raw, "html.parser")

        metadata: dict[str, Any] = {"source": url}
        # Title, description, and language are best-effort: include each only when
        # the page actually provides it, matching WebBaseLoader's metadata shape.
        if soup.title and soup.title.get_text(strip=True):
            metadata["title"] = soup.title.get_text(strip=True)
        description = soup.find("meta", attrs={"name": "description"})
        if description and description.get("content"):
            metadata["description"] = description["content"].strip()
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            metadata["language"] = html_tag["lang"]

        return Document(page_content=SafeFetch.parse_raw_text(raw), metadata=metadata)
