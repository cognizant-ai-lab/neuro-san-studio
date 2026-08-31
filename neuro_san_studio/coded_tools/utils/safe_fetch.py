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

import os
from asyncio import TimeoutError as AsyncTimeoutError
from asyncio import to_thread
from http import HTTPStatus
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from ipaddress import ip_address
from typing import Any
from typing import NoReturn
from urllib.parse import ParseResult
from urllib.parse import parse_qs
from urllib.parse import urlparse

import idna
from aiohttp import ClientError
from aiohttp import ClientResponseError
from aiohttp import ClientSession
from aiohttp import ClientTimeout
from aiohttp import TCPConnector
from aiohttp.helpers import is_ip_address
from bs4 import BeautifulSoup

from neuro_san_studio.coded_tools.utils.global_only_resolver import GlobalOnlyResolver
from neuro_san_studio.coded_tools.utils.pdf_utils import PdfUtils

# Maximum accepted URL length, shared by every tool on this path (WebFetch and
# the RAG loaders) so they all accept the same URLs. 2000 is what browsers and
# CDNs commonly tolerate, and it leaves room for presigned object-store links
# (S3/Azure SAS), which routinely run 300-1000+ characters; anything longer is
# far more likely malformed or hostile than legitimate.
MAX_URL_LENGTH: int = 2000
# Maximum bytes accepted via Content-Length header before downloading; also the
# running cap enforced on streamed response bodies (text and PDF alike). One
# shared limit for every tool on this path: large enough for real-world PDF
# corpora (tens of MB), while still bounding peak memory — the RAG loaders cap
# how many bodies they hold in flight at once (see their semaphore constants).
MAX_RESPONSE_BYTES: int = 50 * 1024 * 1024  # 50 MB
# Read size per iteration when streaming a response body.
DOWNLOAD_CHUNK_BYTES: int = 64 * 1024
TIMEOUT_SECONDS: int = 15
# Generic "download" media types that carry no real format information. When a server
# declares one of these (or no Content-Type at all), is_pdf falls back to sniffing
# the URL for a ".pdf" filename; any other concrete declared type is trusted as-is.
GENERIC_DOWNLOAD_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "application/octet-stream",
        "binary/octet-stream",
        "application/x-download",
        "application/force-download",
    }
)
# Characters permitted in a canonical (post-IDNA, lower-cased) DNS hostname. IP
# literals are validated separately; a genuine hostname containing anything outside
# this set means IDNA could not canonicalize it and it is not a usable DNS name.
HOSTNAME_ALLOWED_CHARS: frozenset[str] = frozenset("abcdefghijklmnopqrstuvwxyz0123456789.-_")


class SafeFetch:
    """
    Shared SSRF-hardened URL fetching for coded tools that retrieve remote content.

    Currently used by WebFetch; intended for reuse by the RAG tools (webpage RAG,
    PDF RAG) as they migrate onto it.

    SSRF protection blocks private/loopback/reserved ranges and localhost.
    Localhost names and IP literals are rejected up front (validate_hostname_safety);
    other hostnames are validated at connection time by GlobalOnlyResolver, which
    requires every DNS record to be globally routable and closes the DNS-rebinding
    gap. Every network method (get_content_type, fetch_raw, download_pdf_bytes, and
    the fetch_text/fetch_pdf_text wrappers built on them) re-validates the URL at
    entry, so the SSRF policy holds even for a caller that skipped validate_url; all
    requests must still go through a session created by open_session to inherit the
    connection-time resolver check.
    Redirects are not followed; a 3xx response raises url_not_allowed.
    The byte cap (MAX_RESPONSE_BYTES) is enforced both via the Content-Length header
    (pre-check) and on the actual streamed bytes, for text fetches and PDF downloads
    alike, so a server that lies about or omits Content-Length cannot deliver an
    oversized body.

    Error types (raised as ValueError or aiohttp.ClientResponseError or aiohttp.ClientError with the specified message)
        invalid_input            – URL is missing, not a valid http/https URL, or a parameter has an invalid type.
        url_too_long             – URL exceeds MAX_URL_LENGTH characters.
        url_not_allowed          – URL targets a private/reserved host, is blocked by domain rules,
                                    or returns a redirect.
        url_not_accessible       – HTTP error or network failure while fetching the page.
        too_many_requests        – Server returned HTTP 429.
        response_too_large       – Content-Length header or streamed body exceeds MAX_RESPONSE_BYTES.
    """

    @staticmethod
    def open_session() -> ClientSession:
        """
        Create a ClientSession that enforces the SSRF policy on every connection.

        GlobalOnlyResolver enforces the SSRF policy on the exact addresses the
        client connects to (anti DNS-rebinding). The connector's DNS cache is
        disabled so every new connection re-validates instead of reusing a
        previously cached answer.

        :return: A new ClientSession whose connector validates every resolved
                 address and disables DNS caching. The caller owns the session and
                 must close it (use it as an async context manager).
        """
        timeout = ClientTimeout(total=TIMEOUT_SECONDS)
        connector = TCPConnector(resolver=GlobalOnlyResolver(), use_dns_cache=False)
        # Honor the USER_AGENT environment variable, like the langchain
        # WebBaseLoader this path replaced: some sites answer 403 to aiohttp's
        # default "Python/x.y aiohttp/x.y.z" User-Agent, and operators already
        # use this variable to identify their crawlers.
        headers: dict[str, str] | None = None
        user_agent: str | None = os.environ.get("USER_AGENT")
        if user_agent:
            headers = {"User-Agent": user_agent}
        session: ClientSession = ClientSession(timeout=timeout, connector=connector, headers=headers)
        # Mark the session so the network methods can reject a caller-supplied default
        # session, which would skip GlobalOnlyResolver and reopen the SSRF hole.
        # open_session is the only sanctioned constructor and always wires the
        # protected connector above, so the marker reliably implies the resolver is
        # present (see _require_protected_session and the open_session wiring test).
        session._safe_fetch_protected = True  # pylint: disable=protected-access
        return session

    @staticmethod
    def _require_protected_session(session: ClientSession) -> None:
        """
        Reject a session that was not created by open_session.

        SafeFetch's SSRF protection lives entirely in the connector open_session wires
        (GlobalOnlyResolver + no DNS cache); validate_url deliberately defers ordinary
        hostname resolution to that resolver. A caller passing a default ClientSession
        would skip the check and could reach a private address via a hostname that
        resolves to it, so every network method refuses an unmarked session up front.

        :param session: The session handed to a network method.
        :raises ValueError: when the session was not built by SafeFetch.open_session.
        """
        # getattr default is False for a real default session; a marked session
        # (and, harmlessly, a test mock) reports truthy.
        if not getattr(session, "_safe_fetch_protected", False):
            raise ValueError("SafeFetch network methods require a session created by SafeFetch.open_session().")

    @staticmethod
    def validate_url(url_value: Any, allowed_domains: Any = None, blocked_domains: Any = None) -> str:
        """
        Validate a URL's format, length, and domain rules and return the cleaned URL.

        :param url_value: The candidate URL; must be an http/https string.
        :param allowed_domains: Optional allow-list (str or list[str]); if non-empty,
                                the host must equal or be a subdomain of one entry.
        :param blocked_domains: Optional block-list (str or list[str]); the host must
                                not equal or be a subdomain of any entry.
        :return: The stripped, validated URL.
        :raises ValueError: invalid_input, url_too_long, or url_not_allowed when the
                URL fails any format, length, domain, or hostname-safety check.
        """
        if not isinstance(url_value, str):
            raise ValueError(f"invalid_input: 'url' must be a string, got {url_value!r}.")

        url: str = url_value.strip()
        if not url:
            raise ValueError("invalid_input: No 'url' provided.")

        # urlparse itself raises ValueError on some malformed authorities (e.g. an
        # unmatched IPv6 bracket "https://[::1/"); translate it to invalid_input
        # rather than let the raw ValueError escape the documented contract.
        try:
            parsed: ParseResult = urlparse(url)
        except ValueError as exc:
            raise ValueError(f"invalid_input: URL is malformed: {exc}") from exc

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"invalid_input: URL must use http or https scheme, got '{parsed.scheme}'.")

        if len(url) > MAX_URL_LENGTH:
            raise ValueError(f"url_too_long: URL exceeds maximum length of {MAX_URL_LENGTH} characters.")

        raw_hostname: str | None = parsed.hostname
        if not raw_hostname:
            raise ValueError("invalid_input: URL must include a hostname.")

        # urlparse defers port validation until parsed.port is accessed, so a
        # non-numeric or out-of-range port would otherwise slip through and fail
        # later inside aiohttp with an untranslated ValueError.
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError(f"invalid_input: URL has an invalid port: {exc}") from exc

        # Canonicalize the host the same way aiohttp/yarl will before connecting, so
        # every domain and safety check runs on the exact form the request targets.
        # parsed.hostname strips the port/credentials; _to_ascii_host applies IDNA
        # (Unicode IDN -> punycode) and maps Unicode dot separators (U+3002 and
        # friends) to ASCII '.'.
        hostname: str = SafeFetch._to_ascii_host(raw_hostname.lower())
        # Strip the DNS root-label dot only AFTER IDNA encoding: a Unicode trailing
        # dot becomes a strippable ASCII '.' during encoding. Doing this before the
        # domain and hostname-safety checks stops DNS-equivalent spellings
        # ("example.com.", "example.com。", "localhost。") from bypassing the block
        # list or the loopback guard.
        hostname = hostname.rstrip(".")
        # A root-only authority ("http://./", "http://../") has a non-empty
        # parsed.hostname but canonicalizes to an empty string here; reject it as
        # invalid_input rather than let an empty host slip past the checks and reach
        # DNS.
        if not hostname:
            raise ValueError("invalid_input: URL must include a valid hostname.")

        allowed: list[str] = SafeFetch.validate_domain_list(allowed_domains, "allowed_domains")
        if allowed and not SafeFetch._hostname_matches_any(hostname, allowed):
            raise ValueError(f"url_not_allowed: Domain '{hostname}' is not in the allowed_domains list.")

        blocked: list[str] = SafeFetch.validate_domain_list(blocked_domains, "blocked_domains")
        if blocked and SafeFetch._hostname_matches_any(hostname, blocked):
            raise ValueError(f"url_not_allowed: Domain '{hostname}' is blocked.")

        SafeFetch.validate_hostname_safety(hostname)

        return url

    @staticmethod
    def _hostname_matches_any(hostname: str, domains: list[str]) -> bool:
        """
        Return whether a hostname matches any domain under a strict boundary.

        A domain entry "example.com" matches the host "example.com" and any
        subdomain "sub.example.com", but not "badexample.com". Matching is
        case-insensitive.

        :param hostname: The host to test, already canonicalized by validate_url
                (lower-cased, IDNA-ASCII, root-label dot stripped).
        :param domains: The domain entries to test against.
        :return: True if the hostname equals or is a subdomain of any entry.
        """
        # Canonicalize each entry the same way the host was (IDNA-ASCII + trailing
        # dot stripped) so both sides compare in the form aiohttp connects to; a
        # Unicode IDN spelling and its punycode entry (or a "example.com." FQDN
        # entry) would otherwise miss and bypass the configured block/allow rule.
        for domain in domains:
            lowered: str = SafeFetch._to_ascii_host(domain.lower()).rstrip(".")
            if hostname == lowered or hostname.endswith("." + lowered):
                return True
        return False

    @staticmethod
    def _to_ascii_host(host: str) -> str:
        """
        Return the IDNA (punycode) ASCII form of a host for domain-policy matching.

        aiohttp/yarl connect to the IDNA-ASCII form of a Unicode host, and yarl uses
        this same "idna" package, so matching in its UTS#46 form gives exact parity
        with what the request targets. Falls back to the input unchanged when it
        cannot be encoded (IP literals, underscore labels, invalid IDN input), which
        leaves ASCII inputs exactly as the raw comparison saw them and defers those
        cases to the other checks.

        :param host: The already-lower-cased host or domain entry to canonicalize.
        :return: The IDNA-ASCII form, or the input unchanged if it cannot be encoded.
        """
        try:
            return idna.encode(host, uts46=True).decode("ascii")
        except (idna.IDNAError, UnicodeError):
            return host

    @staticmethod
    def validate_hostname_safety(hostname: str) -> None:
        """
        Reject localhost names and IP literals that are not globally routable.

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
        literals and bypass the resolver. For the same reason, a host that aiohttp's
        is_ip_address() accepts but ipaddress.ip_address() cannot parse (e.g. the
        integer form "2130706433" or shorthand "127.1", which resolve to loopback)
        is rejected rather than deferred to a resolver that will never run for it.

        :param hostname: The already-lower-cased host to check.
        :raises ValueError: url_not_allowed when the host is localhost, an
                unparseable/zoned/shorthand IP literal, or a non-global IP literal;
                invalid_input when a genuine hostname holds characters that are not
                valid in a DNS name (IDNA could not canonicalize it).
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
            if is_ip_address(hostname):
                # ip_address() could not parse this, but aiohttp's own literal
                # detection (the exact is_ip_address() check TCPConnector uses to
                # decide whether to skip the resolver) does treat it as an IP
                # literal — e.g. the 32-bit integer form "2130706433" or
                # dotted-shorthand "127.1", both of which the OS resolves to
                # 127.0.0.1. aiohttp will connect to it without ever calling
                # GlobalOnlyResolver, and ip_address() cannot vouch that it is
                # globally routable, so fail closed instead of deferring to a
                # resolver that will never run for it.
                raise ValueError(
                    f"url_not_allowed: Host '{hostname}' is an unsupported IP-literal form."
                ) from parse_exc
            # A genuine (non-IP) hostname. If IDNA could not canonicalize it,
            # _to_ascii_host returned it unchanged, so reject any host still holding
            # characters invalid in a DNS name (e.g. a space or '$'): that is a
            # malformed URL and must surface as invalid_input here rather than fail
            # later inside aiohttp/yarl with an off-contract error. Otherwise
            # GlobalOnlyResolver validates its DNS records at connection time.
            for char in hostname:
                if char not in HOSTNAME_ALLOWED_CHARS:
                    raise ValueError(
                        f"invalid_input: Host '{hostname}' contains characters that are not valid in a hostname."
                    ) from parse_exc
            return

        GlobalOnlyResolver.ensure_global_address(hostname, addr)

    @staticmethod
    def validate_domain_list(value: Any, param_name: str) -> list[str]:
        """
        Coerce and validate a domain-list parameter.

        :param value: The parameter to coerce; accepts None, a single str, or a
                      list[str].
        :param param_name: The parameter's name, used in error messages.
        :return: The domains as a list[str] (empty for None, single-element for a str).
        :raises ValueError: invalid_input when value is neither None, str, nor a
                list of strings.
        """
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
    def is_redirection(status: int) -> bool:
        """
        Report whether an HTTP status code is a 3xx redirection.

        :param status: The HTTP status code.
        :return: True if the status is in the 3xx range.
        """
        return 300 <= status <= 399

    @staticmethod
    def raise_if_redirect(response: Any, url: str) -> None:
        """
        Raise url_not_allowed if the response is a 3xx redirect.

        Must be called explicitly when allow_redirects=False, because
        raise_for_status() only covers 4xx/5xx and silently passes 3xx through.

        :param response: The aiohttp response to inspect.
        :param url: The URL being fetched, included in the raised message.
        :raises ValueError: url_not_allowed when the response status is a 3xx redirect.
        """
        if SafeFetch.is_redirection(response.status):
            location: str = response.headers.get("Location", "unknown")
            raise ValueError(
                f"url_not_allowed: '{url}' redirects to '{location}' ({response.status}); redirects are not followed."
            )

    @staticmethod
    def is_text_content_type(content_type: str) -> bool:
        """
        Report whether a Content-Type is text-like and safe to ingest as text.

        Used both by get_content_type (to decide whether to prefetch the body on
        its GET fallback) and by the RAG loaders (to decide whether a URL's body
        should be stripped to text or skipped as an unsupported binary).

        :param content_type: The raw Content-Type header value (may include params).
        :return: True for text/*, application/json, application/xml, and
                 "+xml"-suffixed types (html is covered by text/html and
                 application/xhtml+xml); False for PDF, images (including
                 image/svg+xml), binary vendor types, or anything else.
        """
        # Match only the base media type, not the parameters: a header such as
        # 'application/pdf; profile="text/html"' is a PDF, and scanning the whole
        # value would misread it as text and stream the body here only for WebFetch
        # to download it again as a PDF.
        base_type: str = content_type.split(";", 1)[0].strip().lower()
        # A declared image is never ingestible text, even when its subtype is
        # XML-based: image/svg+xml would match the "+xml" test below, but SVG markup
        # is path/coordinate noise for RAG and callers advertise this method as
        # skipping images. Check the top-level type first so that policy holds.
        if base_type.startswith("image/"):
            return False
        # JSON is plain text in practice (API responses, JSON document corpora) and
        # the langchain loaders this path replaced ingested it; downstream the
        # HTML-sniff passthrough keeps a JSON body verbatim since it does not start
        # with "<".
        if base_type == "application/json":
            return True
        # Recognize XML types by the RFC 6839 "+xml" structured suffix (or the exact
        # application/xml type), NOT by an "xml"/"html" substring scan: binary vendor
        # types such as .docx's
        # application/vnd.openxmlformats-officedocument.wordprocessingml.document are
        # ZIP containers whose names merely contain "xml" and must not be read as text.
        return base_type.startswith("text/") or base_type == "application/xml" or base_type.endswith("+xml")

    @staticmethod
    def is_pdf(content_type: str, url: str) -> bool:
        """
        Report whether a resource should be parsed as a PDF.

        Kept in one place so WebFetch and the RAG loaders classify PDFs identically.
        A declared base media type of application/pdf is a PDF. Any other concrete
        declared type is trusted and means "not a PDF": a ".pdf" URL serving declared
        text/html is an error page or a moved document, and force-feeding it to the
        PDF parser turns a readable page into a parse failure. Only when the server
        gives no usable type (missing header, or a generic download type from
        GENERIC_DOWNLOAD_CONTENT_TYPES) does the URL decide.

        :param content_type: The raw Content-Type header value (may include params).
        :param url: The already-validated URL, used for the ".pdf" suffix fallback.
        :return: True if the resource should be parsed as a PDF.
        """
        # A Content-Type header has the form "type/subtype[; parameter=value ...]",
        # e.g. "application/pdf" or "application/pdf; qs=0.8". Split at the first ";"
        # and keep only the base "type/subtype" token so trailing parameters never
        # affect the comparison; strip/lower because header tokens are
        # case-insensitive and may carry surrounding whitespace.
        base_type: str = content_type.split(";", 1)[0].strip().lower()
        if base_type == "application/pdf":
            return True
        # A concrete declared type other than application/pdf wins over the URL:
        # the server knows what it is serving, and the suffix is only a filename hint.
        if base_type and base_type not in GENERIC_DOWNLOAD_CONTENT_TYPES:
            return False
        # No usable declared type: sniff the URL for a ".pdf" filename.
        # parsed.path is only the path segment of the URL: for a URL ending in
        # "/file.pdf?download=1#page=2" the path is "/file.pdf", with the
        # "?query" and "#fragment" parts split off. endswith(".pdf") on the path
        # therefore still matches when a query string or fragment follows the
        # filename — the same check on the full url string would miss it.
        parsed: ParseResult = urlparse(url)
        if parsed.path.lower().endswith(".pdf"):
            return True
        # Download endpoints often carry the filename only in the query string
        # instead of the path. Check each query parameter's value so the filename
        # is found wherever it sits ("?name=report.pdf" and "?name=report.pdf&sig=x"
        # alike). parse_qs drops a bare valueless token ("?report.pdf" has no "="),
        # so the query-suffix check below still has a case of its own.
        for values in parse_qs(parsed.query).values():
            for value in values:
                if value.lower().endswith(".pdf"):
                    return True
        # Test the query string, NOT the raw URL: a raw endswith would also match a
        # "#fragment" ending in ".pdf" ("/page#report.pdf"), and fragments are never
        # sent to the server, so they say nothing about what the resource is.
        return parsed.query.lower().endswith(".pdf")

    @staticmethod
    async def get_content_type(url: str, session: ClientSession) -> tuple[str, str | None]:
        """
        Probe the URL with a HEAD request and return (Content-Type, prefetched_body).

        Falls back to a GET request when HEAD fails with any HTTP error except 429:
        many servers reject HEAD while serving GET fine (405 from HEAD-less
        endpoints, 403 from presigned S3/Azure URLs that sign only the GET method),
        so a HEAD failure only proves HEAD is unsupported, not that the resource is
        inaccessible. On the fallback a text-like body is read and returned as the
        second element so the caller can skip a second GET; PDF and other/binary
        content types return None so their bodies are not downloaded here only to
        be discarded.

        :param url: The URL to probe.
        :param session: A session created by open_session (enforces the SSRF policy).
        :return: A (content_type, prefetched_body) tuple; prefetched_body is the text
                 body only on the GET-fallback text-like path, otherwise None.
        :raises ValueError: url_not_allowed on a redirect, or response_too_large when
                the Content-Length header or the streamed fallback text body exceeds
                MAX_RESPONSE_BYTES.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests on a non-2xx response.
        :raises aiohttp.ClientError: url_not_accessible on a connection/DNS/timeout failure.
        """
        # Refuse a session that did not come from open_session, so the SSRF resolver
        # cannot be bypassed by a caller passing a default aiohttp session.
        SafeFetch._require_protected_session(session)
        # Re-validate at the network boundary so the SSRF policy holds even if a
        # caller reached this method without calling validate_url first. Validation
        # is pure and idempotent, so the redundant call on WebFetch's
        # already-validated URL is harmless.
        url = SafeFetch.validate_url(url)
        try:
            async with session.head(url, allow_redirects=False) as head:
                SafeFetch.raise_if_redirect(head, url)
                # Any 2xx success (200 OK up to, but excluding, 300 MULTIPLE_CHOICES —
                # the first 3xx code): HEAD succeeded, so the headers alone answer
                # the probe and there is no body to read.
                if HTTPStatus.OK <= head.status < HTTPStatus.MULTIPLE_CHOICES:
                    SafeFetch.check_content_length(head.headers.get("Content-Length"), url)
                    return head.headers.get("Content-Type", ""), None
                if head.status == HTTPStatus.TOO_MANY_REQUESTS:
                    # 429 is authoritative: the server is rate-limiting us, and an
                    # immediate GET retry would only make that worse. Raise (it is
                    # translated to too_many_requests below).
                    head.raise_for_status()
                # Any other HEAD failure falls through to the GET fallback below,
                # which passes through the exact same redirect/size/SSRF checks.
                # (Redirects were already handled above: a 3xx means the resource
                # moved, and a GET would just see the same redirect.)
            async with session.get(url, allow_redirects=False) as get:
                SafeFetch.raise_if_redirect(get, url)
                get.raise_for_status()
                SafeFetch.check_content_length(get.headers.get("Content-Length"), url)
                content_type: str = get.headers.get("Content-Type", "")
                # Only prefetch text-like bodies: a PDF is downloaded separately by
                # fetch_pdf_text, and any other/binary type is rejected by the
                # caller, so reading it here would download bytes only to discard
                # them.
                if SafeFetch.is_text_content_type(content_type):
                    # Stream with the running byte cap (like fetch_raw); the
                    # Content-Length pre-check above only guards honest servers.
                    body: str | None = await SafeFetch._read_capped_text(get, url)
                else:
                    body = None
                return content_type, body
        except (ClientError, AsyncTimeoutError) as exc:
            SafeFetch._raise_translated(exc, url)

    @staticmethod
    def check_content_length(content_length_header: str | None, url: str) -> None:
        """
        Raise response_too_large if a Content-Length header exceeds MAX_RESPONSE_BYTES.

        :param content_length_header: The Content-Length header value, or None if absent.
        :param url: The URL being fetched, included in the raised message.
        :raises ValueError: response_too_large when the parsed length exceeds the limit.
        """
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

    @staticmethod
    async def fetch_pdf_text(url: str, session: ClientSession) -> str:
        """
        Download a PDF through the protected session and extract its text with pypdf.

        The download uses download_pdf_bytes, so it inherits the full SSRF policy and
        the streamed MAX_RESPONSE_BYTES cap.

        :param url: The PDF URL to fetch.
        :param session: A session created by open_session (enforces the SSRF policy).
        :return: The extracted text of the PDF.
        :raises ValueError: url_not_allowed on a redirect, or response_too_large when
                the body exceeds MAX_RESPONSE_BYTES.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests on a non-2xx response.
        :raises aiohttp.ClientError: url_not_accessible on a download or PDF-parse failure.
        """
        data: bytes = await SafeFetch.download_pdf_bytes(url, session)

        try:
            # Text extraction is CPU-bound; run it in a worker thread so a large
            # or complex PDF does not stall the event loop.
            return await to_thread(PdfUtils.parse_pdf_bytes, data)
        except Exception as exc:
            raise ClientError(f"url_not_accessible: Failed to parse PDF '{url}': {exc}") from exc

    @staticmethod
    async def download_pdf_bytes(url: str, session: ClientSession) -> bytes:
        """
        Stream a PDF body through the protected session, capping its size.

        The MAX_RESPONSE_BYTES cap is enforced on the bytes actually received (in
        addition to the Content-Length pre-check), so a server that lies about or
        omits Content-Length cannot deliver an oversized body.

        :param url: The PDF URL to fetch.
        :param session: A session created by open_session (enforces the SSRF policy).
        :return: The raw PDF bytes.
        :raises ValueError: url_not_allowed on a redirect, or response_too_large when
                the streamed body exceeds MAX_RESPONSE_BYTES.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests on a non-2xx response.
        :raises aiohttp.ClientError: url_not_accessible on a connection/DNS/timeout failure.
        """
        SafeFetch._require_protected_session(session)
        # Re-validate at the network boundary (see get_content_type).
        url = SafeFetch.validate_url(url)
        try:
            async with session.get(url, allow_redirects=False) as response:
                SafeFetch.raise_if_redirect(response, url)
                response.raise_for_status()
                SafeFetch.check_content_length(response.headers.get("Content-Length"), url)
                return await SafeFetch._read_capped_body(response, url)
        except (ClientError, AsyncTimeoutError) as exc:
            SafeFetch._raise_translated(exc, url)

    @staticmethod
    async def fetch_raw(url: str, session: ClientSession) -> str:
        """
        Fetch a URL via aiohttp GET and return its decoded body (not HTML-stripped).

        The body is streamed with the same running MAX_RESPONSE_BYTES cap as
        download_pdf_bytes (in addition to the Content-Length pre-check), so a server
        that lies about or omits Content-Length cannot deliver an oversized body to a
        direct caller that skipped the HEAD probe in get_content_type. The bytes are
        decoded once, after the full (capped) body is in hand, using the response's
        declared charset (falling back to utf-8 and replacing undecodable bytes) so
        multibyte sequences spanning chunk boundaries are never split. A leading
        byte-order mark is dropped from the decoded text.

        :param url: The URL to fetch.
        :param session: A session created by open_session (enforces the SSRF policy).
        :return: The decoded response body (raw markup, not HTML-stripped).
        :raises ValueError: url_not_allowed on a redirect, or response_too_large when
                the streamed body exceeds MAX_RESPONSE_BYTES.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests on a non-2xx response.
        :raises aiohttp.ClientError: url_not_accessible on a connection/DNS/timeout failure.
        """
        SafeFetch._require_protected_session(session)
        # Re-validate at the network boundary (see get_content_type).
        url = SafeFetch.validate_url(url)
        try:
            async with session.get(url, allow_redirects=False) as response:
                # raise_for_status() only covers 4xx/5xx; 3xx passes through silently
                # returning useless redirect-page HTML. Check explicitly so a server
                # that behaves differently on GET vs an earlier HEAD probe is still caught.
                SafeFetch.raise_if_redirect(response, url)
                response.raise_for_status()
                SafeFetch.check_content_length(response.headers.get("Content-Length"), url)
                return await SafeFetch._read_capped_text(response, url)
        except (ClientError, AsyncTimeoutError) as exc:
            SafeFetch._raise_translated(exc, url)

    @staticmethod
    async def _read_capped_body(response: Any, url: str) -> bytes:
        """
        Stream a response body into memory, enforcing the running byte cap.

        :param response: The aiohttp response whose body to stream.
        :param url: The URL being fetched, included in the raised message.
        :return: The full response body as bytes (at most MAX_RESPONSE_BYTES).
        :raises ValueError: response_too_large when the received bytes exceed the limit.
        """
        chunks: list[bytes] = []
        received: int = 0
        async for chunk in response.content.iter_chunked(DOWNLOAD_CHUNK_BYTES):
            received += len(chunk)
            if received > MAX_RESPONSE_BYTES:
                raise ValueError(f"response_too_large: '{url}' body exceeds the {MAX_RESPONSE_BYTES}-byte limit.")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _read_capped_text(response: Any, url: str) -> str:
        """
        Stream a response body with the byte cap, then decode it to text.

        Decoding happens once, after the full (capped) body is in hand, so multibyte
        sequences spanning chunk boundaries are never split. aiohttp's
        response.charset comes from the Content-Type header; fall back to utf-8 and
        replace undecodable bytes rather than raise. A leading byte-order mark is
        dropped from the decoded text.

        :param response: The aiohttp response whose body to stream and decode.
        :param url: The URL being fetched, included in the raised message.
        :return: The decoded response body (at most MAX_RESPONSE_BYTES of raw bytes),
                 without a leading byte-order mark.
        :raises ValueError: response_too_large when the received bytes exceed the limit.
        """
        body: bytes = await SafeFetch._read_capped_body(response, url)
        encoding: str = response.charset or "utf-8"
        try:
            text: str = body.decode(encoding, errors="replace")
        except LookupError:
            # A malformed Content-Type can name a codec Python does not know.
            # bytes.decode() then raises LookupError at codec lookup, before
            # errors="replace" can take effect (that only covers decode errors
            # for a valid codec). LookupError is neither ClientError nor
            # AsyncTimeoutError, so it would escape the fetch methods'
            # translation and break their url_not_accessible contract. Fall back
            # to utf-8 so a bad charset token never leaks past this boundary.
            text = body.decode("utf-8", errors="replace")
        # A UTF-8 byte-order mark survives a plain utf-8 decode as a leading U+FEFF.
        # It is an encoding signature, not content, and str.lstrip() does not treat
        # it as whitespace, so left in place it hides the leading "<" from the HTML
        # sniffs in parse_raw_text and WebpageRag._to_document and plants an
        # invisible character in stored text. Drop it here so every consumer sees
        # the same text a BOM-less copy of the file would produce.
        return text.removeprefix("\ufeff")

    @staticmethod
    async def fetch_text(url: str, session: ClientSession) -> str:
        """
        Fetch a URL via aiohttp GET and return its plain-text body, stripping HTML.

        :param url: The URL to fetch.
        :param session: A session created by open_session (enforces the SSRF policy).
        :return: The response body with HTML markup stripped when present.
        :raises ValueError: url_not_allowed on a redirect, or response_too_large when
                the body exceeds MAX_RESPONSE_BYTES.
        :raises aiohttp.ClientResponseError: url_not_accessible / too_many_requests on a non-2xx response.
        :raises aiohttp.ClientError: url_not_accessible on a connection/DNS/timeout failure.
        """
        raw_content: str = await SafeFetch.fetch_raw(url, session)
        return SafeFetch.parse_raw_text(raw_content)

    @staticmethod
    def parse_raw_text(raw: str) -> str:
        """
        Strip HTML markup from raw text if it looks like HTML; otherwise return as-is.

        :param raw: The raw response body.
        :return: The text with script/style/noscript removed and tags stripped when
                 the body looks like HTML, else the input unchanged.
        """
        if not raw.lstrip().startswith("<"):
            return raw
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    @staticmethod
    def _raise_translated(exc: BaseException, url: str) -> NoReturn:
        """
        Re-raise an aiohttp fetch error under the tool's error-prefix contract.

        Consolidates the translation shared by get_content_type, fetch_raw, and
        download_pdf_bytes: a non-2xx response becomes a ClientResponseError tagged
        too_many_requests (HTTP 429) or url_not_accessible, and any other transport
        error (connection failure, DNS failure, timeout) becomes a ClientError tagged
        url_not_accessible.

        :param exc: The caught aiohttp ClientError (possibly a ClientResponseError)
                    or asyncio timeout to translate.
        :param url: The URL being fetched, included in the raised message.
        :raises aiohttp.ClientResponseError: when exc is a ClientResponseError, tagged
                too_many_requests or url_not_accessible.
        :raises aiohttp.ClientError: for any other transport failure, tagged url_not_accessible.
        """
        if isinstance(exc, ClientResponseError):
            prefix: str = "too_many_requests" if exc.status == HTTPStatus.TOO_MANY_REQUESTS else "url_not_accessible"
            raise ClientResponseError(
                exc.request_info,
                exc.history,
                status=exc.status,
                message=f"{prefix}: HTTP {exc.status} for '{url}'.",
                headers=exc.headers,
            ) from exc
        raise ClientError(f"url_not_accessible: Could not reach '{url}': {exc}") from exc
