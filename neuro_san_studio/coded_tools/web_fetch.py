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

from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import to_thread
from datetime import datetime
from datetime import timezone
from http import HTTPStatus
from io import BytesIO
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from ipaddress import ip_address
from logging import Logger
from logging import getLogger
from typing import Any
from urllib.parse import ParseResult
from urllib.parse import urlparse

from aiohttp import ClientError
from aiohttp import ClientResponseError
from aiohttp import ClientSession
from aiohttp import ClientTimeout
from aiohttp import TCPConnector
from bs4 import BeautifulSoup
from neuro_san.interfaces.coded_tool import CodedTool
from pypdf import PdfReader

from neuro_san_studio.coded_tools.global_only_resolver import GlobalOnlyResolver

MAX_CHARS: int = 20_000
MAX_URL_LENGTH: int = 250
# Maximum bytes accepted via Content-Length header before downloading; also the
# running cap enforced on streamed PDF bodies.
MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10 MB
# Read size per iteration when streaming a PDF body.
DOWNLOAD_CHUNK_BYTES: int = 64 * 1024
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
    the response. PDF bodies are parsed with pypdf.

    Note: SSRF protection blocks private/loopback/reserved ranges and localhost.
    Localhost names and IP literals are rejected up front (_validate_hostname_safety);
    other hostnames are validated at connection time by GlobalOnlyResolver, which
    requires every DNS record to be globally routable and closes the DNS-rebinding
    gap. All requests, including PDF downloads, go through the shared protected
    session. Use allowed_domains for stricter control.
    Redirects are not followed; a 3xx response raises url_not_allowed.
    The byte cap (MAX_RESPONSE_BYTES) is enforced via the Content-Length header for
    text fetches (a server that lies about or omits Content-Length can still deliver
    an arbitrarily large body) and on the actual streamed bytes for PDF downloads.

    Error types (raised as ValueError or aiohttp.ClientResponseError or aiohttp.ClientError with the specified message)
        invalid_input            – URL is missing, not a valid http/https URL, or a parameter has an invalid type.
        url_too_long             – URL exceeds MAX_URL_LENGTH characters.
        url_not_allowed          – URL targets a private/reserved host, is blocked by domain rules,
                                    or returns a redirect.
        url_not_accessible       – HTTP error or network failure while fetching the page.
        too_many_requests        – Server returned HTTP 429.
        unsupported_content_type – Content type is not text/HTML or PDF.
        response_too_large       – Content-Length header or streamed PDF body exceeds MAX_RESPONSE_BYTES.
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
        # GlobalOnlyResolver enforces the SSRF policy on the exact addresses the
        # client connects to (anti DNS-rebinding). The connector's DNS cache is
        # disabled so every new connection re-validates instead of reusing a
        # previously cached answer. The session owns the connector and closes it.
        connector = TCPConnector(resolver=GlobalOnlyResolver(), use_dns_cache=False)
        async with ClientSession(timeout=timeout, connector=connector) as session:
            content_type, prefetched_text = await self._get_content_type(url, session)
            is_pdf: bool = "application/pdf" in content_type or url.lower().endswith(".pdf")

            if not is_pdf and not any(ct in content_type for ct in SUPPORTED_CONTENT_TYPES):
                raise ValueError(
                    f"unsupported_content_type: Content type '{content_type}' is not supported. "
                    "Only text/HTML and PDF are accepted."
                )

            retrieved_at: str = datetime.now(timezone.utc).isoformat()
            if is_pdf:
                text: str = await self._fetch_pdf(url, session)
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

        self._validate_hostname_safety(hostname)

        return url

    @staticmethod
    def _validate_hostname_safety(hostname: str) -> None:
        """Reject localhost names and IP literals that are not globally routable.

        Non-IP hostnames are intentionally NOT DNS-resolved here: their records are
        validated at connection time by GlobalOnlyResolver on the session's
        TCPConnector, which checks the exact addresses the client connects to and
        therefore prevents DNS rebinding (a pre-fetch check could be answered with a
        safe address and rebound to an internal one before the connection).

        IP literals must be checked up front because aiohttp short-circuits them in
        TCPConnector._resolve_host and never calls the resolver for them. Zoned IPv6
        literals (e.g. "fe80::1%eth0") are parsed by ip_address() on Python >= 3.9 and
        validated like any other literal; strings that ip_address() cannot parse but
        that contain characters illegal in DNS hostnames ('%' or ':') are rejected
        outright, because aiohttp's own literal detection may still treat them as IP
        literals and bypass the resolver.
        """
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError(f"url_not_allowed: Host '{hostname}' targets a loopback address.")

        addr: IPv4Address | IPv6Address
        try:
            addr = ip_address(hostname)
        except ValueError as parse_exc:
            if "%" in hostname or ":" in hostname:
                # Not parseable as an IP address, yet it cannot be a DNS hostname
                # either: '%' and ':' are illegal in hostnames. Treat it as a
                # malformed or zoned IP literal and fail closed — aiohttp may
                # consider such strings IP literals and skip GlobalOnlyResolver,
                # so anything ip_address() cannot vouch for must not pass.
                raise ValueError(
                    f"url_not_allowed: Host '{hostname}' is not a valid hostname or IP address."
                ) from parse_exc
            # A genuine hostname; GlobalOnlyResolver validates its DNS records at
            # connection time.
            return

        GlobalOnlyResolver.ensure_global_address(hostname, addr)

    @staticmethod
    def _validate_domain_list(value: Any, param_name: str) -> list[str]:
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

    @staticmethod
    def _validate_max_content_chars(args: dict[str, Any]) -> int:
        """Return a validated max_content_chars value, raising invalid_input on bad input."""
        value: int = args.get("max_content_chars", MAX_CHARS)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"invalid_input: 'max_content_chars' must be a positive integer, got {value!r}.")
        return value

    @staticmethod
    def _is_redirection(status: int) -> bool:
        """Return True if the HTTP status code is a 3xx redirection."""
        return 300 <= status <= 399

    def _raise_if_redirect(self, response: Any, url: str) -> None:
        """Raise ValueError with url_not_allowed if the response is a 3xx redirect.

        Must be called explicitly when allow_redirects=False, because raise_for_status()
        only covers 4xx/5xx and silently passes 3xx responses through.
        """
        if self._is_redirection(response.status):
            location: str = response.headers.get("Location", "unknown")
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
                if head.status == HTTPStatus.METHOD_NOT_ALLOWED:
                    # Server does not support HEAD; probe with GET and read the body so
                    # async_invoke can reuse it and avoid a second round-trip.
                    async with session.get(url, allow_redirects=False) as get:
                        self._raise_if_redirect(get, url)
                        get.raise_for_status()
                        self._check_content_length(get.headers.get("Content-Length"), url)
                        content_type: str = get.headers.get("Content-Type", "")
                        # Skip reading body for PDFs; _fetch_pdf downloads the bytes separately.
                        body: str | None = None if "application/pdf" in content_type else await get.text()
                        return content_type, body
                head.raise_for_status()
                self._check_content_length(head.headers.get("Content-Length"), url)
                return head.headers.get("Content-Type", ""), None
        except ClientResponseError as exc:
            prefix: str = "too_many_requests" if exc.status == HTTPStatus.TOO_MANY_REQUESTS else "url_not_accessible"
            raise ClientResponseError(
                exc.request_info,
                exc.history,
                status=exc.status,
                message=f"{prefix}: HTTP {exc.status} for '{url}'.",
                headers=exc.headers,
            ) from exc
        except (ClientError, AsyncTimeoutError) as exc:
            raise ClientError(f"url_not_accessible: Could not reach '{url}': {exc}") from exc

    @staticmethod
    def _check_content_length(content_length_header: str | None, url: str) -> None:
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

    async def _fetch_pdf(self, url: str, session: ClientSession) -> str:
        """Download a PDF through the protected session and extract its text with pypdf.

        The download uses the shared ClientSession, so it inherits the full SSRF
        policy: GlobalOnlyResolver validation at connection time (anti DNS-rebinding),
        no redirects, and the session timeout. The body is streamed with a running
        MAX_RESPONSE_BYTES cap (see _download_pdf_bytes).

        This method is temporary: once neuro-san supports multimodal input, the PDF
        can be passed as base64 directly to the model instead of being parsed to text.
        """
        data: bytes = await self._download_pdf_bytes(url, session)

        try:
            # Text extraction is CPU-bound; run it in a worker thread so a large
            # or complex PDF does not stall the event loop.
            return await to_thread(self._parse_pdf_bytes, data)
        except Exception as exc:
            raise ClientError(f"url_not_accessible: Failed to parse PDF '{url}': {exc}") from exc

    @staticmethod
    def _parse_pdf_bytes(data: bytes) -> str:
        """Extract text from in-memory PDF bytes, joining pages with newlines."""
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() for page in reader.pages)

    async def _download_pdf_bytes(self, url: str, session: ClientSession) -> bytes:
        """Stream a PDF body through the protected session, capping its size.

        Unlike the text path, the MAX_RESPONSE_BYTES cap is enforced on the bytes
        actually received (in addition to the Content-Length pre-check), so a server
        that lies about or omits Content-Length cannot deliver an oversized body.
        Redirects are not followed; a 3xx response raises ValueError with url_not_allowed.
        Raises ClientResponseError with a url_not_accessible / too_many_requests prefix
        on non-2xx, and ClientError with a url_not_accessible prefix on
        connection/DNS/timeout failures.
        """
        try:
            async with session.get(url, allow_redirects=False) as response:
                self._raise_if_redirect(response, url)
                response.raise_for_status()
                self._check_content_length(response.headers.get("Content-Length"), url)

                chunks: list[bytes] = []
                received: int = 0
                async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_BYTES):
                    received += len(chunk)
                    if received > MAX_RESPONSE_BYTES:
                        raise ValueError(
                            f"response_too_large: '{url}' PDF body exceeds the {MAX_RESPONSE_BYTES}-byte limit."
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
        except ClientResponseError as exc:
            prefix: str = "too_many_requests" if exc.status == HTTPStatus.TOO_MANY_REQUESTS else "url_not_accessible"
            raise ClientResponseError(
                exc.request_info,
                exc.history,
                status=exc.status,
                message=f"{prefix}: HTTP {exc.status} for '{url}'.",
                headers=exc.headers,
            ) from exc
        except (ClientError, AsyncTimeoutError) as exc:
            raise ClientError(f"url_not_accessible: Failed to fetch '{url}': {exc}") from exc

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
            prefix: str = "too_many_requests" if exc.status == HTTPStatus.TOO_MANY_REQUESTS else "url_not_accessible"
            raise ClientResponseError(
                exc.request_info,
                exc.history,
                status=exc.status,
                message=f"{prefix}: HTTP {exc.status} for '{url}'.",
                headers=exc.headers,
            ) from exc
        except (ClientError, AsyncTimeoutError) as exc:
            raise ClientError(f"url_not_accessible: Failed to fetch '{url}': {exc}") from exc

        return self._parse_raw_text(raw_content)

    @staticmethod
    def _parse_raw_text(raw: str) -> str:
        """Strip HTML markup from raw text if it looks like HTML; otherwise return as-is."""
        if not raw.lstrip().startswith("<"):
            return raw
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
