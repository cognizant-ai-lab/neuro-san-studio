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

from logging import getLogger
from logging import Logger
from datetime import datetime
from datetime import timezone
from typing import Any
from urllib.parse import ParseResult
from urllib.parse import urlparse

from aiohttp import ClientError
from aiohttp import ClientSession
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.tools.requests.tool import RequestsGetTool
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_core.documents import Document
from neuro_san.interfaces.coded_tool import CodedTool

MAX_CHARS: int = 20_000
MAX_URL_LENGTH: int = 250
SUPPORTED_CONTENT_TYPES: set[str] = {"text/html", "text/plain", "application/xhtml", "application/pdf"}
TIMEOUT_SECONDS: int = 15


class WebFetch(CodedTool):
    """
    CodedTool implementation that fetches a URL and returns its plain-text body.

    Uses LangChain's RequestsGetTool for the HTTP request and BeautifulSoup
    to strip HTML markup from the response. PDF URLs are handled via PyPDFLoader.

    Error types (raised as ValueError or aiohttp.ClientResponseError or aiohttp.ClientError with the specified message)
        invalid_input            – URL is missing or not a valid http/https URL.
        url_too_long             – URL exceeds MAX_URL_LENGTH characters.
        url_not_allowed          – URL blocked by domain filtering rules.
        url_not_accessible       – HTTP error while fetching the page.
        too_many_requests        – Server returned HTTP 429.
        unsupported_content_type – Content type is not text/HTML or PDF.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "url"               (str, required): The URL to fetch.
                    "allowed_domains"   (list, optional): Only fetch from these domains.
                    "blocked_domains"   (list, optional): Refuse to fetch from these domains.
                    "max_content_chars" (int, optional): Character cap on returned text.
                                        Defaults to MAX_CHARS.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None

        :return:
            A dictionary with the following keys:
                "url"          (str): The URL that was fetched.
                "content"      (str): Plain-text body of the fetched page.
                "retrieved_at" (str): ISO-8601 UTC timestamp when the content was retrieved.

        :raises ValueError: invalid_input, url_too_long, url_not_allowed,
                            unsupported_content_type.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests (non-2xx HEAD).
        :raises aiohttp.ClientError: url_not_accessible when PDF or text fetch fails.
        """
        # --- invalid_input: missing or non-http(s) URL ---
        url: str = args.get("url", "").strip()
        if not url:
            raise ValueError("invalid_input: No 'url' provided.")
        parsed: ParseResult = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"invalid_input: URL must use http or https scheme, got '{parsed.scheme}'.")

        # --- url_too_long ---
        if len(url) > MAX_URL_LENGTH:
            raise ValueError(f"url_too_long: URL exceeds maximum length of {MAX_URL_LENGTH} characters.")

        # --- url_not_allowed: domain filtering ---
        domain: str = parsed.netloc.lower()
        allowed_domains: list[str] = args.get("allowed_domains", [])
        if allowed_domains and not any(domain.endswith(d.lower()) for d in allowed_domains):
            raise ValueError(f"url_not_allowed: Domain '{domain}' is not in the allowed_domains list.")
        blocked_domains: list[str] = args.get("blocked_domains", [])
        if blocked_domains and any(domain.endswith(d.lower()) for d in blocked_domains):
            raise ValueError(f"url_not_allowed: Domain '{domain}' is blocked.")

        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("WebFetch: fetching %s", url)

        # Probe content type with an async HEAD request before downloading.
        timeout = ClientTimeout(total=TIMEOUT_SECONDS)
        async with ClientSession(timeout=timeout) as session:
            async with session.head(url, allow_redirects=True) as head:
                # --- url_not_accessible / too_many_requests: raise on any non-2xx ---
                head.raise_for_status()
                content_type: str = head.headers.get("Content-Type", "")

        is_pdf: bool = "application/pdf" in content_type or url.lower().endswith(".pdf")

        # --- unsupported_content_type ---
        if not is_pdf and not any(ct in content_type for ct in SUPPORTED_CONTENT_TYPES):
            raise ValueError(
                f"unsupported_content_type: Content type '{content_type}' is not supported. "
                "Only text/HTML and PDF are accepted."
            )

        retrieved_at: str = datetime.now(timezone.utc).isoformat()

        if is_pdf:
            try:
                docs: list[Document] = await PyPDFLoader(url).aload()
            except Exception as exc:
                raise ClientError(f"url_not_accessible: Failed to load PDF '{url}': {exc}") from exc
            text: str = "\n".join(doc.page_content for doc in docs)
        else:
            requests_tool = RequestsGetTool(
                requests_wrapper=TextRequestsWrapper(),
                allow_dangerous_requests=True,
            )
            try:
                raw_content: str = await requests_tool.ainvoke(url)
            except Exception as exc:
                raise ClientError(f"url_not_accessible: Failed to fetch '{url}': {exc}") from exc

            if raw_content.lstrip().startswith("<"):
                soup = BeautifulSoup(raw_content, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                text: str = soup.get_text(separator="\n", strip=True)
            else:
                text = raw_content

        max_chars: int = args.get("max_content_chars", MAX_CHARS)
        text = text[:max_chars]

        logger.info("WebFetch: returned %d characters from %s", len(text), url)

        # return format taken from Anthropic's webfetch tool
        return {
            "url": url,
            "content": text,
            "retrieved_at": retrieved_at,
        }
