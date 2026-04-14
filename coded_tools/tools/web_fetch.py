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
import ipaddress
from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from typing import Any
from urllib.parse import ParseResult
from urllib.parse import urlparse

from aiohttp import ClientError
from aiohttp import ClientResponseError
from aiohttp import ClientSession
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from neuro_san.interfaces.coded_tool import CodedTool

MAX_CHARS: int = 20_000
MAX_URL_LENGTH: int = 250
# Maximum bytes accepted via Content-Length header before downloading
MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10 MB
SUPPORTED_CONTENT_TYPES: set[str] = {
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/pdf",
}
TIMEOUT_SECONDS: int = 15


class WebFetch(CodedTool):
    """
    CodedTool implementation that fetches a URL and returns its plain-text body.

    Uses aiohttp for HTTP requests and BeautifulSoup to strip HTML markup from
    the response. PDF URLs are handled via PyPDFLoader.

    Note: IP-literal SSRF protection blocks private/loopback/reserved ranges and localhost, but
    non-IP hostnames are not DNS-resolved. Use allowed_domains for stricter control.
    Redirects are not followed; a 3xx response raises url_not_allowed.
    The byte cap (MAX_RESPONSE_BYTES) is enforced via the Content-Length header only (checked
    before download). A server that lies about or omits Content-Length can still deliver an
    arbitrarily large body.

    Error types (raised as ValueError or aiohttp.ClientResponseError or aiohttp.ClientError with the specified message)
        invalid_input            – URL is missing, not a valid http/https URL, or a parameter has an invalid type.
        url_too_long             – URL exceeds MAX_URL_LENGTH characters.
        url_not_allowed          – URL targets a private/reserved host, is blocked by domain rules,
                                    or returns a redirect.
        url_not_accessible       – HTTP error or network failure while fetching the page.
        too_many_requests        – Server returned HTTP 429.
        unsupported_content_type – Content type is not text/HTML or PDF.
        response_too_large       – Content-Length header exceeds MAX_RESPONSE_BYTES.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "url"               (str, required): The URL to fetch.
                    "allowed_domains"   (list[str], optional): Only fetch from these domains.
                    "blocked_domains"   (list[str], optional): Refuse to fetch from these domains.
                    "max_content_chars" (int, optional): Character cap on returned text.
                                        Defaults to MAX_CHARS. Must be a positive integer.

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
                            unsupported_content_type, response_too_large.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests (non-2xx response).
        :raises aiohttp.ClientError: url_not_accessible when PDF or text fetch fails.
        """
        url: str = self._validate_url(args)
        max_chars: int = self._validate_max_content_chars(args)

        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("WebFetch: fetching %s", url)

        timeout = ClientTimeout(total=TIMEOUT_SECONDS)
        async with ClientSession(timeout=timeout) as session:
            content_type, prefetched_text = await self._get_content_type(url, session)
            is_pdf: bool = "application/pdf" in content_type or url.lower().endswith(".pdf")

            if not is_pdf and not any(ct in content_type for ct in SUPPORTED_CONTENT_TYPES):
                raise ValueError(
                    f"unsupported_content_type: Content type '{content_type}' is not supported. "
                    "Only text/HTML and PDF are accepted."
                )

            retrieved_at: str = datetime.now(timezone.utc).isoformat()
            if is_pdf:
                text: str = await self._fetch_pdf(url)
            elif prefetched_text is not None:
                # Body was already fetched during the 405 HEAD fallback GET; no second request needed.
                text = self._parse_raw_text(prefetched_text)
            else:
                text = await self._fetch_text(url, session)

        text = text[:max_chars]

        logger.info("WebFetch: returned %d characters from %s", len(text), url)

        # return format taken from Anthropic's webfetch tool
        return {
            "url": url,
            "content": text,
            "retrieved_at": retrieved_at,
        }

    def _validate_url(self, args: dict[str, Any]) -> str:
        """Validate URL format, length, and domain rules. Returns the cleaned URL."""
        url_value: Any = args.get("url", "")
        if not isinstance(url_value, str):
            raise ValueError(f"invalid_input: 'url' must be a string, got {url_value!r}.")

        url: str = url_value.strip()
        if not url:
            raise ValueError("invalid_input: No 'url' provided.")

        parsed: ParseResult = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"invalid_input: URL must use http or https scheme, got '{parsed.scheme}'.")

        if len(url) > MAX_URL_LENGTH:
            raise ValueError(f"url_too_long: URL exceeds maximum length of {MAX_URL_LENGTH} characters.")

        raw_hostname: str | None = parsed.hostname
        if not raw_hostname:
            raise ValueError("invalid_input: URL must include a hostname.")

        # Use parsed.hostname (strips port/credentials) and enforce a strict domain boundary:
        # an allowed/blocked entry "example.com" matches "example.com" and "sub.example.com"
        # but not "badexample.com".
        hostname: str = raw_hostname.lower()

        self._validate_hostname_safety(hostname)

        allowed_domains: list[str] = self._validate_domain_list(args.get("allowed_domains"), "allowed_domains")
        if allowed_domains and not any(
            hostname == domain.lower() or hostname.endswith("." + domain.lower()) for domain in allowed_domains
        ):
            raise ValueError(f"url_not_allowed: Domain '{hostname}' is not in the allowed_domains list.")

        blocked_domains: list[str] = self._validate_domain_list(args.get("blocked_domains"), "blocked_domains")
        if blocked_domains and any(
            hostname == domain.lower() or hostname.endswith("." + domain.lower()) for domain in blocked_domains
        ):
            raise ValueError(f"url_not_allowed: Domain '{hostname}' is blocked.")

        return url

    def _validate_hostname_safety(self, hostname: str) -> None:
        """Reject IP literals in private/loopback/link-local/multicast/reserved ranges and localhost.

        Note: non-IP hostnames are not DNS-resolved here; use allowed_domains for stricter control.
        """
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError(f"url_not_allowed: Host '{hostname}' targets a loopback address.")

        try:
            addr = ipaddress.ip_address(hostname)
        except ValueError:
            # Not an IP literal; DNS-based checks are out of scope
            return

        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast or addr.is_reserved:
            raise ValueError(
                f"url_not_allowed: IP address '{hostname}' is in a private, loopback, "
                "link-local, multicast, or reserved range."
            )

    def _validate_domain_list(self, value: Any, param_name: str) -> list[str]:
        """Coerce and validate a domain list parameter. Accepts None, list[str], or a single str."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if not isinstance(value, list):
            raise ValueError(f"invalid_input: '{param_name}' must be a list of strings, got {value!r}.")
        for item in value:
            if not isinstance(item, str):
                raise ValueError(
                    f"invalid_input: '{param_name}' must be a list of strings, "
                    f"but contains non-string element {item!r}."
                )
        return value

    def _validate_max_content_chars(self, args: dict[str, Any]) -> int:
        """Return a validated max_content_chars value, raising invalid_input on bad input."""
        value: int = args.get("max_content_chars", MAX_CHARS)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"invalid_input: 'max_content_chars' must be a positive integer, got {value!r}.")
        return value

    def _raise_if_redirect(self, response: Any, url: str) -> None:
        """Raise ValueError with url_not_allowed if the response is a 3xx redirect.

        Must be called explicitly when allow_redirects=False, because raise_for_status()
        only covers 4xx/5xx and silently passes 3xx responses through.
        """
        if response.status in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "unknown")
            raise ValueError(
                f"url_not_allowed: '{url}' redirects to '{location}' ({response.status}); redirects are not followed."
            )

    async def _get_content_type(self, url: str, session: ClientSession) -> tuple[str, str | None]:
        """Probe the URL with a HEAD request and return (Content-Type, prefetched_body).

        Falls back to a GET request if the server returns 405 (Method Not Allowed).
        In the 405 case the response body is read and returned as the second element so
        async_invoke can skip a second GET for text content types.
        Redirects are not followed; a 3xx response raises ValueError with url_not_allowed.
        Raises ClientResponseError with a url_not_accessible / too_many_requests prefix on non-2xx,
        and ClientError with a url_not_accessible prefix on connection/DNS/timeout failures.
        Raises ValueError with a response_too_large prefix when Content-Length exceeds MAX_RESPONSE_BYTES.
        """
        try:
            async with session.head(url, allow_redirects=False) as head:
                self._raise_if_redirect(head, url)
                if head.status == 405:
                    # Server does not support HEAD; probe with GET and read the body so
                    # async_invoke can reuse it and avoid a second round-trip.
                    async with session.get(url, allow_redirects=False) as get:
                        self._raise_if_redirect(get, url)
                        get.raise_for_status()
                        self._check_content_length(get.headers.get("Content-Length"), url)
                        content_type: str = get.headers.get("Content-Type", "")
                        # Skip reading body for PDFs; PyPDFLoader handles those separately.
                        body: str | None = None if "application/pdf" in content_type else await get.text()
                        return content_type, body
                head.raise_for_status()
                self._check_content_length(head.headers.get("Content-Length"), url)
                return head.headers.get("Content-Type", ""), None
        except ClientResponseError as exc:
            prefix: str = "too_many_requests" if exc.status == 429 else "url_not_accessible"
            raise ClientResponseError(
                exc.request_info,
                exc.history,
                status=exc.status,
                message=f"{prefix}: HTTP {exc.status} for '{url}'.",
                headers=exc.headers,
            ) from exc
        except (ClientError, asyncio.TimeoutError) as exc:
            raise ClientError(f"url_not_accessible: Could not reach '{url}': {exc}") from exc

    def _check_content_length(self, content_length_header: str | None, url: str) -> None:
        """Raise ValueError if Content-Length exceeds MAX_RESPONSE_BYTES."""
        if content_length_header is not None:
            try:
                size = int(content_length_header)
            except ValueError:
                return
            if size > MAX_RESPONSE_BYTES:
                raise ValueError(
                    f"response_too_large: '{url}' reports Content-Length {size} bytes, "
                    f"which exceeds the {MAX_RESPONSE_BYTES}-byte limit."
                )

    async def _fetch_pdf(self, url: str) -> str:
        """Download and extract text from a PDF URL.

        Note: PyPDFLoader manages its own HTTP session internally, so the shared
        ClientSession from async_invoke is not used here. This method is temporary:
        once neuro-san supports multimodal input, the PDF can be passed as base64
        directly to the model instead of being parsed to text.
        """
        try:
            docs: list[Document] = await PyPDFLoader(url).aload()
        except Exception as exc:
            raise ClientError(f"url_not_accessible: Failed to load PDF '{url}': {exc}") from exc
        return "\n".join(doc.page_content for doc in docs)

    async def _fetch_text(self, url: str, session: ClientSession) -> str:
        """Fetch a URL via aiohttp GET and return its plain-text body, stripping HTML if needed."""
        try:
            async with session.get(url, allow_redirects=False) as response:
                # raise_for_status() only covers 4xx/5xx; 3xx passes through silently
                # returning useless redirect-page HTML. Check explicitly so a server
                # that behaves differently on GET vs the earlier HEAD probe is still caught.
                self._raise_if_redirect(response, url)
                response.raise_for_status()
                raw_content: str = await response.text()
        except ClientResponseError as exc:
            prefix: str = "too_many_requests" if exc.status == 429 else "url_not_accessible"
            raise ClientResponseError(
                exc.request_info,
                exc.history,
                status=exc.status,
                message=f"{prefix}: HTTP {exc.status} for '{url}'.",
                headers=exc.headers,
            ) from exc
        except (ClientError, asyncio.TimeoutError) as exc:
            raise ClientError(f"url_not_accessible: Failed to fetch '{url}': {exc}") from exc

        return self._parse_raw_text(raw_content)

    def _parse_raw_text(self, raw: str) -> str:
        """Strip HTML markup from raw text if it looks like HTML; otherwise return as-is."""
        if not raw.lstrip().startswith("<"):
            return raw
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
