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

# This is the consolidated one-class test module for SafeFetch (one file per module,
# per the repo convention), so it legitimately exceeds pylint's default line limit.
# pylint: disable=too-many-lines

import asyncio
from io import BytesIO
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from aiohttp import ClientError
from aiohttp import ClientResponseError
from aiohttp import ClientSession
from aiohttp import TCPConnector
from pypdf import PdfWriter

from neuro_san_studio.coded_tools.utils.global_only_resolver import GlobalOnlyResolver
from neuro_san_studio.coded_tools.utils.safe_fetch import MAX_RESPONSE_BYTES
from neuro_san_studio.coded_tools.utils.safe_fetch import MAX_URL_LENGTH
from neuro_san_studio.coded_tools.utils.safe_fetch import SafeFetch

MODULE = "neuro_san_studio.coded_tools.utils.safe_fetch"


def make_request_info(url: str = "http://example.com") -> MagicMock:
    """Minimal RequestInfo mock required by ClientResponseError constructor."""
    info = MagicMock()
    info.url = url
    info.method = "HEAD"
    info.headers = {}
    info.real_url = url
    return info


def make_response_error(status: int, url: str = "http://example.com") -> ClientResponseError:
    """Build a minimal ClientResponseError with the given HTTP status code."""
    return ClientResponseError(request_info=make_request_info(url), history=(), status=status)


def make_head_session(
    status: int = 200,
    content_type: str = "text/html",
    content_length: int | None = None,
    raise_for_status_exc: Exception | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (mock_session, mock_head_response) for HEAD-only tests."""
    headers: dict[str, str] = {"Content-Type": content_type}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    if extra_headers:
        headers.update(extra_headers)

    head_response = MagicMock()
    head_response.status = status
    head_response.headers = headers
    head_response.raise_for_status = MagicMock(side_effect=raise_for_status_exc if raise_for_status_exc else None)

    head_cm = MagicMock()
    head_cm.__aenter__ = AsyncMock(return_value=head_response)
    head_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.head = MagicMock(return_value=head_cm)

    return session, head_response


def make_stream_session(
    chunks: list[bytes],
    status: int = 200,
    content_type: str = "application/pdf",
    content_length: int | None = None,
    raise_for_status_exc: Exception | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (mock_session, mock_response) whose body streams via content.iter_chunked.

    :param chunks: Byte chunks yielded by response.content.iter_chunked.
    """
    headers: dict[str, str] = {"Content-Type": content_type}
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    response = MagicMock()
    response.status = status
    response.headers = headers
    response.raise_for_status = MagicMock(side_effect=raise_for_status_exc if raise_for_status_exc else None)

    async def iter_chunked(_chunk_size: int):
        for chunk in chunks:
            yield chunk

    response.content.iter_chunked = iter_chunked

    response_cm = MagicMock()
    response_cm.__aenter__ = AsyncMock(return_value=response)
    response_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=response_cm)

    return session, response


def make_get_response(
    status: int = 200,
    content_type: str = "text/html",
    body: str = "",
    charset: str = "utf-8",
    raise_for_status_exc: Exception | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (mock_session, mock_get_response) for GET-only tests (fetch_raw/fetch_text)."""
    response = MagicMock()
    response.status = status
    response.headers = {"Content-Type": content_type}
    response.charset = charset
    response.raise_for_status = MagicMock(side_effect=raise_for_status_exc if raise_for_status_exc else None)
    response.text = AsyncMock(return_value=body)

    # fetch_raw streams the body via response.content.iter_chunked and decodes it
    # with response.charset, so provide the body as a single encoded chunk.
    body_bytes = body.encode(charset)

    async def iter_chunked(_chunk_size: int):
        yield body_bytes

    response.content.iter_chunked = iter_chunked

    response_cm = MagicMock()
    response_cm.__aenter__ = AsyncMock(return_value=response)
    response_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=response_cm)

    return session, response


def make_pdf_bytes(pages: int = 1) -> bytes:
    """Build a minimal valid PDF with the given number of blank pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def open_session_user_agent() -> str | None:
    """
    Open a real SafeFetch session and return its User-Agent header, closing the session.

    :return: The session's User-Agent header value, or None when absent.
    """
    session = SafeFetch.open_session()
    try:
        return session.headers.get("User-Agent")
    finally:
        await session.close()


class TestSafeFetch(TestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for the SafeFetch shared SSRF-hardened fetch utility.

    Validation performs no DNS lookups; DNS records are validated at connection
    time by GlobalOnlyResolver (see test_global_only_resolver.py). Network-facing
    methods are exercised with mocked aiohttp sessions built by the helpers above.
    """

    def test_open_session_wires_ssrf_connector(self):
        """Tests that open_session builds a session whose connector enforces the SSRF policy.

        Guards the central guarantee: the connector must use GlobalOnlyResolver (anti
        DNS-rebinding) with the DNS cache disabled, so swapping it for a default
        connector cannot silently drop the protection while the rest of the suite,
        which only uses mocked sessions, still passes.
        """

        async def check():
            session = SafeFetch.open_session()
            try:
                connector = session.connector
                self.assertIsInstance(connector, TCPConnector)
                # Private attributes are the only offline way to assert the wiring.
                self.assertIsInstance(connector._resolver, GlobalOnlyResolver)  # pylint: disable=protected-access
                self.assertFalse(connector._use_dns_cache)  # pylint: disable=protected-access
            finally:
                await session.close()

        asyncio.run(check())

    def test_network_methods_reject_unprotected_session(self):
        """Tests that network methods refuse a session not created by open_session.

        A default ClientSession has no GlobalOnlyResolver, so accepting it would let a
        hostname resolve to a private address and reopen the SSRF hole. Each method
        must reject the unmarked session up front, before any request.
        """

        async def check():
            session = ClientSession()
            try:
                with self.assertRaises(ValueError) as ctx:
                    await SafeFetch.get_content_type("http://example.com", session)
                self.assertIn("open_session", str(ctx.exception))
                with self.assertRaises(ValueError):
                    await SafeFetch.fetch_raw("http://example.com", session)
                with self.assertRaises(ValueError):
                    await SafeFetch.download_pdf_bytes("http://example.com", session)
            finally:
                await session.close()

        asyncio.run(check())

    def _call_validate_url(self, args):
        """Invoke validate_url with the given args dict and return the result."""
        return SafeFetch.validate_url(args.get("url", ""), args.get("allowed_domains"), args.get("blocked_domains"))

    def test_validate_url_valid_http_url(self):
        """Tests that a valid HTTP URL is accepted."""
        self.assertEqual(self._call_validate_url({"url": "http://example.com/page"}), "http://example.com/page")

    def test_validate_url_valid_https_url(self):
        """Tests that a valid HTTPS URL is accepted."""
        self.assertEqual(self._call_validate_url({"url": "https://example.com"}), "https://example.com")

    def test_validate_url_strips_whitespace(self):
        """Tests that leading and trailing whitespace is stripped from the URL."""
        self.assertEqual(self._call_validate_url({"url": "  https://example.com  "}), "https://example.com")

    def test_validate_url_missing_url_key(self):
        """Tests that a missing 'url' key raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_empty_url(self):
        """Tests that an empty URL string raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": ""})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_non_string_url(self):
        """Tests that a non-string URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": 42})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_none_url(self):
        """Tests that a None URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": None})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_ftp_scheme_rejected(self):
        """Tests that an FTP scheme URL is rejected with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "ftp://example.com"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_url_too_long(self):
        """Tests that a URL exceeding the maximum length raises ValueError with url_too_long."""
        long_url = "https://example.com/" + "a" * MAX_URL_LENGTH
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": long_url})
        self.assertIn("url_too_long", str(ctx.exception))

    def test_validate_url_url_at_max_length_is_accepted(self):
        """Tests that a URL exactly at the maximum allowed length is accepted."""
        prefix = "https://test.co/"
        url = prefix + "a" * (MAX_URL_LENGTH - len(prefix))
        self.assertEqual(self._call_validate_url({"url": url}), url)

    def test_validate_url_missing_hostname(self):
        """Tests that a URL with no hostname raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https:///no-host"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_allowed_domains_pass(self):
        """Tests that a URL matching an allowed domain passes validation."""
        url = self._call_validate_url({"url": "https://api.example.com/data", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://api.example.com/data")

    def test_validate_url_allowed_domains_exact_match(self):
        """Tests that a URL exactly matching an allowed domain passes validation."""
        url = self._call_validate_url({"url": "https://example.com/", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com/")

    def test_validate_url_allowed_domains_rejects_unrelated(self):
        """Tests that a URL not matching any allowed domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-other.com/", "allowed_domains": ["test-example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_allowed_domains_does_not_match_partial_prefix(self):
        """Tests that a hostname sharing a suffix but not a domain boundary is rejected."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-badexample.com/", "allowed_domains": ["test-example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_blocked_domains_rejects(self):
        """Tests that a URL exactly matching a blocked domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-blocked.com/", "blocked_domains": ["test-blocked.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_blocked_domains_subdomain_rejected(self):
        """Tests that a subdomain of a blocked domain is also rejected."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-sub.blocked.com/", "blocked_domains": ["blocked.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_blocked_domains_partial_prefix_not_blocked(self):
        """Tests that a domain sharing a suffix with a blocked domain but not a boundary is allowed."""
        url = self._call_validate_url({"url": "https://test-notblocked.com/", "blocked_domains": ["test-blocked.com"]})
        self.assertEqual(url, "https://test-notblocked.com/")

    def test_validate_url_url_with_port_matches_domain(self):
        """Tests that a URL with a port number still matches the allowed domain correctly."""
        url = self._call_validate_url({"url": "https://example.com:8080/path", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com:8080/path")

    def test_validate_url_blocked_domain_checked_against_hostname(self):
        """Tests that blocked domains are enforced on the hostname itself."""
        # Regression test: the hostname must never be replaced by a resolved IP
        # before domain checks run.
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-blocked.com/x", "blocked_domains": ["test-blocked.com"]})
        self.assertIn("Domain 'test-blocked.com' is blocked", str(ctx.exception))

    def test_validate_url_trailing_dot_host_still_blocked(self):
        """Tests that a trailing-dot FQDN cannot bypass a block-list entry.

        'example.com.' is DNS-equivalent to 'example.com'; without canonicalizing
        the hostname it would evade blocked_domains=['example.com'].
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://example.com./x", "blocked_domains": ["example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_trailing_dot_host_matches_allowed(self):
        """Tests that a trailing-dot FQDN still matches an allowed_domains entry."""
        url = self._call_validate_url({"url": "https://example.com./data", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com./data")

    def test_validate_url_trailing_dot_localhost_blocked(self):
        """Tests that 'localhost.' cannot dodge the loopback guard via a trailing dot."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "http://localhost./"})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_idn_unicode_host_matches_punycode_block(self):
        """Tests that a Unicode IDN host is blocked by its punycode blocked_domains entry.

        aiohttp connects to the IDNA-ASCII form, so 'münchen.de' must match a
        blocked 'xn--mnchen-3ya.de' or the block is bypassed by spelling.
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://münchen.de/x", "blocked_domains": ["xn--mnchen-3ya.de"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_idn_punycode_host_matches_unicode_block(self):
        """Tests the inverse spelling: a punycode host is blocked by a Unicode blocked_domains entry."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://xn--mnchen-3ya.de/x", "blocked_domains": ["münchen.de"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_invalid_port_rejected(self):
        """Tests that a non-numeric port raises invalid_input rather than failing later in aiohttp."""
        # Assembled from parts so the CI link checker (lychee) does not extract and
        # fail to parse this deliberately-invalid port.
        bad_port_url = "https://example.com" + ":not-a-port/x"
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": bad_port_url})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_unmatched_ipv6_bracket_rejected(self):
        """Tests that a malformed IPv6 authority (unmatched bracket) raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://[::1/x"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_unicode_dot_separator_host_still_blocked(self):
        """Tests that a Unicode dot separator (U+3002) cannot bypass a block-list entry.

        IDNA encoding maps 'example.com。' to the trailing-dot form of 'example.com',
        so it must be blocked by blocked_domains=['example.com'].
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://example.com。/x", "blocked_domains": ["example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_unicode_dot_separator_localhost_blocked(self):
        """Tests that 'localhost。' (U+3002) cannot dodge the loopback guard."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "http://localhost。/"})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_trailing_dot_block_entry_matches_bare_host(self):
        """Tests that a fully-qualified block-list entry ('example.com.') blocks the bare host."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://example.com/x", "blocked_domains": ["example.com."]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_uts46_mapping_matches_yarl(self):
        """Tests that canonicalization uses UTS#46 (like yarl), not IDNA2003.

        IDNA2003 maps 'faß.de' to 'fass.de', but aiohttp/yarl connect to
        'xn--fa-hia.de'; a UTS#46 block entry in that punycode form must therefore
        block the Unicode host, which IDNA2003 would let bypass.
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://faß.de/x", "blocked_domains": ["xn--fa-hia.de"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_root_only_host_rejected(self):
        """Tests that a root-only authority canonicalizing to an empty host is rejected.

        'http://./' and 'http://../' have a non-empty parsed.hostname that reduces to
        '' after IDNA encoding and trailing-dot stripping; they must raise
        invalid_input rather than be returned as valid and reach DNS.
        """
        for url in ("http://./", "http://../"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError) as ctx:
                    self._call_validate_url({"url": url})
                self.assertIn("invalid_input", str(ctx.exception))

    def _call_validate_hostname_safety(self, hostname: str) -> None:
        """Invoke validate_hostname_safety with the given hostname."""
        SafeFetch.validate_hostname_safety(hostname)

    def test_validate_hostname_safety_non_ip_hostname_allowed_without_dns(self):
        """Tests that a non-IP hostname passes without a DNS lookup (validated later by the resolver)."""
        self._call_validate_hostname_safety("example.com")  # should not raise

    def test_validate_hostname_safety_public_ip_allowed(self):
        """Tests that a publicly routable IP address does not raise an error."""
        self._call_validate_hostname_safety("8.8.8.8")  # should not raise

    def test_validate_hostname_safety_localhost_blocked(self):
        """Tests that 'localhost' is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("localhost")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_localhost_subdomain_blocked(self):
        """Tests that a subdomain of localhost is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("app.localhost")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_loopback_ipv4_blocked(self):
        """Tests that the IPv4 loopback address 127.0.0.1 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("127.0.0.1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_private_ipv4_blocked(self):
        """Tests that private IPv4 addresses are blocked with url_not_allowed."""
        for ip in ("10.0.0.1", "192.168.1.1", "172.16.0.1"):
            with self.subTest(ip=ip):
                with self.assertRaises(ValueError) as ctx:
                    self._call_validate_hostname_safety(ip)
                self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_link_local_blocked(self):
        """Tests that a link-local IP address such as the AWS metadata endpoint is blocked."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("169.254.169.254")  # AWS metadata endpoint
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_integer_and_shorthand_ipv4_literals_blocked(self):
        """Tests that IPv4 forms aiohttp treats as literals but ip_address() rejects are blocked.

        The 32-bit integer form '2130706433' and dotted-shorthand '127.1' both
        resolve to 127.0.0.1 and are treated as IP literals by aiohttp, so aiohttp
        skips GlobalOnlyResolver for them; validate_hostname_safety must reject them
        up front rather than defer to a resolver that never runs.
        """
        for host in ("2130706433", "127.1", "0177.0.0.1"):
            with self.subTest(host=host):
                with self.assertRaises(ValueError) as ctx:
                    self._call_validate_hostname_safety(host)
                self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_ipv6_loopback_blocked(self):
        """Tests that the IPv6 loopback address ::1 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("::1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_unspecified_ipv4_blocked(self):
        """Tests that the unspecified IPv4 address 0.0.0.0 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("0.0.0.0")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_unspecified_ipv6_blocked(self):
        """Tests that the unspecified IPv6 address :: is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("::")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_cgnat_blocked(self):
        """Tests that a CGNAT address (100.64.0.0/10) is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("100.64.0.1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_zoned_ipv6_link_local_blocked(self):
        """Tests that zoned IPv6 link-local literals (RFC 6874) are blocked with url_not_allowed.

        Covers both the raw zone form and the percent-encoded form as surfaced by
        urlparse().hostname. ip_address() parses zoned literals on Python >= 3.9,
        so these are rejected as non-global addresses.
        """
        for hostname in ("fe80::1%eth0", "fe80::1%25eth0"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError) as ctx:
                    self._call_validate_hostname_safety(hostname)
                self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_malformed_ip_like_string_blocked(self):
        """Tests that IP-like strings that ip_address() cannot parse fail closed.

        '%' and ':' are illegal in DNS hostnames, so such strings can only be
        malformed or zoned IP literals. They must be rejected rather than deferred
        to the resolver, because aiohttp's literal detection may treat them as IP
        literals and bypass GlobalOnlyResolver.
        """
        for hostname in ("fe80::1%", "gggg::1", "1.2.3.4%zone"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError) as ctx:
                    self._call_validate_hostname_safety(hostname)
                self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_malformed_chars_rejected(self):
        """Tests that a genuine hostname with characters invalid in a DNS name is rejected.

        IDNA cannot canonicalize a host containing a space or '$', so _to_ascii_host
        leaves it unchanged; it must surface as invalid_input rather than pass through
        and fail later inside aiohttp with an off-contract error.
        """
        for hostname in ("exa mple.com", "ex$mple.com"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError) as ctx:
                    self._call_validate_hostname_safety(hostname)
                self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_hostname_safety_underscore_label_allowed(self):
        """Tests that underscore labels are tolerated (aiohttp/yarl accept them), not over-rejected."""
        self._call_validate_hostname_safety("a_b.example.com")  # should not raise

    def _call_validate_domain_list(self, value, param_name="test_param"):
        """Invoke validate_domain_list with the given value and return the result."""
        return SafeFetch.validate_domain_list(value, param_name)

    def test_validate_domain_list_none_returns_empty_list(self):
        """Tests that passing None returns an empty list."""
        self.assertEqual(self._call_validate_domain_list(None), [])

    def test_validate_domain_list_single_string_coerced_to_list(self):
        """Tests that a single string domain is coerced into a one-element list."""
        self.assertEqual(self._call_validate_domain_list("example.com"), ["example.com"])

    def test_validate_domain_list_valid_list_returned_unchanged(self):
        """Tests that a valid list of domain strings is returned unchanged."""
        domains = ["example.com", "other.org"]
        self.assertEqual(self._call_validate_domain_list(domains), domains)

    def test_validate_domain_list_non_list_non_string_raises(self):
        """Tests that a non-list, non-string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_domain_list(123)
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_domain_list_list_with_non_string_element_raises(self):
        """Tests that a list containing a non-string element raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_domain_list(["example.com", 42])
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_domain_list_dict_raises(self):
        """Tests that passing a dict raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_domain_list({"domain": "example.com"})
        self.assertIn("invalid_input", str(ctx.exception))

    def _call_check_content_length(self, header, url="http://example.com"):
        """Invoke check_content_length with the given Content-Length header value."""
        SafeFetch.check_content_length(header, url)

    def test_check_content_length_none_header_does_not_raise(self):
        """Tests that a missing (None) Content-Length header does not raise."""
        self._call_check_content_length(None)  # should not raise

    def test_check_content_length_within_limit_does_not_raise(self):
        """Tests that a Content-Length below the limit does not raise."""
        self._call_check_content_length(str(MAX_RESPONSE_BYTES - 1))

    def test_check_content_length_exactly_at_limit_does_not_raise(self):
        """Tests that a Content-Length exactly at the limit does not raise."""
        self._call_check_content_length(str(MAX_RESPONSE_BYTES))

    def test_check_content_length_over_limit_raises(self):
        """Tests that a Content-Length exceeding the limit raises ValueError with response_too_large."""
        with self.assertRaises(ValueError) as ctx:
            self._call_check_content_length(str(MAX_RESPONSE_BYTES + 1))
        self.assertIn("response_too_large", str(ctx.exception))

    def test_check_content_length_non_numeric_header_does_not_raise(self):
        """Tests that a non-numeric Content-Length header value does not raise."""
        self._call_check_content_length("chunked")  # should not raise

    def test_get_content_type_head_success_returns_content_type(self):
        """Tests that a successful HEAD response returns the Content-Type header value with no prefetched body."""
        session, _ = make_head_session(status=200, content_type="text/html; charset=utf-8")
        content_type, body = asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertEqual(content_type, "text/html; charset=utf-8")
        self.assertIsNone(body)

    def test_get_content_type_head_405_falls_back_to_get_pdf(self):
        """Tests that a 405 HEAD response falls back to GET and returns content type without body for PDF."""
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 200
        get_response.headers = {"Content-Type": "application/pdf"}
        get_response.raise_for_status = MagicMock()
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        content_type, body = asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertEqual(content_type, "application/pdf")
        self.assertIsNone(body)
        session.get.assert_called_once()

    def test_get_content_type_head_405_falls_back_to_get_text_returns_body(self):
        """Tests that a 405 HEAD response falls back to GET and returns the body for text content types."""
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 200
        get_response.headers = {"Content-Type": "text/html"}
        get_response.charset = "utf-8"
        get_response.raise_for_status = MagicMock()

        async def iter_chunked(_chunk_size):
            yield b"<html>Hello</html>"

        get_response.content.iter_chunked = iter_chunked
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        content_type, body = asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertEqual(content_type, "text/html")
        self.assertEqual(body, "<html>Hello</html>")

    def test_get_content_type_head_405_non_text_type_skips_body_read(self):
        """Tests that a 405 fallback GET does not read the body for non-text content types.

        A binary/unsupported type is returned with body None so the caller rejects it
        without downloading a body that would only be discarded.
        """
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 200
        get_response.headers = {"Content-Type": "image/png"}
        get_response.raise_for_status = MagicMock()
        get_response.text = AsyncMock(return_value="binary-should-not-be-read")
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        content_type, body = asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertEqual(content_type, "image/png")
        self.assertIsNone(body)
        get_response.text.assert_not_awaited()

    def test_get_content_type_405_pdf_with_text_param_not_prefetched(self):
        """Tests that only the base media type drives the text prefetch, not the parameters.

        'application/pdf; profile="text/html"' is a PDF; scanning the whole header
        would misread it as text and stream the body here only for it to be
        downloaded again as a PDF, so no body must be prefetched.
        """
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 200
        get_response.headers = {"Content-Type": 'application/pdf; profile="text/html"'}
        get_response.raise_for_status = MagicMock()

        async def iter_chunked(_chunk_size):
            yield b"should-not-be-read"

        get_response.content.iter_chunked = iter_chunked
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        content_type, body = asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertEqual(content_type, 'application/pdf; profile="text/html"')
        self.assertIsNone(body)

    def test_get_content_type_head_405_text_body_over_limit_raises(self):
        """Tests that the 405 text prefetch enforces the streamed byte cap, not just Content-Length.

        No Content-Length header is set, so only the running byte count on the
        streamed body can catch an oversized response (the server-lies case).
        """
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 200
        get_response.headers = {"Content-Type": "text/html"}
        get_response.charset = "utf-8"
        get_response.raise_for_status = MagicMock()

        async def iter_chunked(_chunk_size):
            yield b"x" * 50

        get_response.content.iter_chunked = iter_chunked
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        with patch(f"{MODULE}.MAX_RESPONSE_BYTES", 10):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertIn("response_too_large", str(ctx.exception))

    def test_open_session_honors_user_agent_env(self):
        """Tests that open_session applies the USER_AGENT env value as the session's User-Agent.

        The langchain WebBaseLoader honored USER_AGENT; some sites answer 403 to
        aiohttp's default User-Agent, so the hardened session keeps that operator
        knob. Without the variable, no explicit User-Agent header is set. The unset
        case asserts session-level configuration only: session.headers reflects
        just constructor-supplied headers — aiohttp injects its default User-Agent
        per request, never onto the session — so assertIsNone is deterministic.
        """
        with patch.dict("os.environ", {"USER_AGENT": "studio-test-agent/1.0"}):
            self.assertEqual(asyncio.run(open_session_user_agent()), "studio-test-agent/1.0")
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(asyncio.run(open_session_user_agent()))

    def test_get_content_type_head_403_falls_back_to_get(self):
        """Tests that a HEAD failure other than 429 still falls back to GET.

        Presigned S3/Azure URLs sign only the GET method and answer 403 to HEAD;
        the probe must not report such a resource inaccessible when a plain GET
        (through the same redirect/size checks) succeeds.
        """
        session, _ = make_head_session(status=403)
        get_response = MagicMock()
        get_response.status = 200
        get_response.headers = {"Content-Type": "application/pdf"}
        get_response.raise_for_status = MagicMock()
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        content_type, body = asyncio.run(SafeFetch.get_content_type("http://example.com/presigned", session))
        self.assertEqual(content_type, "application/pdf")
        self.assertIsNone(body)
        session.get.assert_called_once()

    def test_get_content_type_head_and_get_both_failing_raises_url_not_accessible(self):
        """Tests that when HEAD fails and the fallback GET also fails, the GET error surfaces.

        A HEAD failure alone no longer raises — it only triggers the GET fallback —
        so the inaccessible verdict must come from the GET.
        """
        session, _ = make_head_session(status=404)
        exc = make_response_error(404)
        get_response = MagicMock()
        get_response.status = 404
        get_response.headers = {}
        get_response.raise_for_status = MagicMock(side_effect=exc)
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        with self.assertRaises(ClientResponseError) as ctx:
            asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertIn("url_not_accessible", ctx.exception.message)
        self.assertEqual(ctx.exception.status, 404)

    def test_get_content_type_429_raises_with_too_many_requests_prefix(self):
        """Tests that a 429 response raises ClientResponseError with too_many_requests prefix."""
        exc = make_response_error(429)
        session, _ = make_head_session(status=429, raise_for_status_exc=exc)
        with self.assertRaises(ClientResponseError) as ctx:
            asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertIn("too_many_requests", ctx.exception.message)

    def test_get_content_type_connection_error_raises_with_url_not_accessible_prefix(self):
        """Tests that a connection error raises ClientError with url_not_accessible prefix."""
        head_cm = MagicMock()
        head_cm.__aenter__ = AsyncMock(side_effect=ClientError("DNS failure"))
        head_cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.head = MagicMock(return_value=head_cm)

        with self.assertRaises(ClientError) as ctx:
            asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_get_content_type_timeout_raises_with_url_not_accessible_prefix(self):
        """Tests that a request timeout raises ClientError with url_not_accessible prefix."""
        head_cm = MagicMock()
        head_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        head_cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.head = MagicMock(return_value=head_cm)

        with self.assertRaises(ClientError) as ctx:
            asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_get_content_type_content_length_over_limit_raises_response_too_large(self):
        """Tests that a Content-Length header exceeding the limit raises ValueError with response_too_large."""
        session, _ = make_head_session(status=200, content_type="text/html", content_length=MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        self.assertIn("response_too_large", str(ctx.exception))

    def test_get_content_type_head_redirect_raises_url_not_allowed(self):
        """Tests that a 3xx HEAD response raises ValueError containing url_not_allowed and the Location URL."""
        session, _ = make_head_session(status=301, extra_headers={"Location": "http://other.com/"})
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        error = str(ctx.exception)
        self.assertIn("url_not_allowed", error)
        self.assertIn("http://other.com/", error)

    def test_get_content_type_405_get_redirect_raises_url_not_allowed(self):
        """Tests that a 405 HEAD + 3xx GET raises ValueError with url_not_allowed and the Location URL."""
        session, _ = make_head_session(status=405)
        get_response = MagicMock()
        get_response.status = 302
        get_response.headers = {"Location": "http://other.com/"}
        get_cm = MagicMock()
        get_cm.__aenter__ = AsyncMock(return_value=get_response)
        get_cm.__aexit__ = AsyncMock(return_value=False)
        session.get = MagicMock(return_value=get_cm)

        with self.assertRaises(ValueError) as ctx:
            asyncio.run(SafeFetch.get_content_type("http://example.com", session))
        error = str(ctx.exception)
        self.assertIn("url_not_allowed", error)
        self.assertIn("http://other.com/", error)

    def test_fetch_text_plain_text_returned_as_is(self):
        """Tests that plain text body content is returned unchanged."""
        session, _ = make_get_response(body="just plain text")
        result = asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertEqual(result, "just plain text")

    def test_fetch_text_html_is_stripped(self):
        """Tests that HTML tags, scripts, and styles are stripped from the fetched content."""
        html = "<html><head><style>body{}</style></head><body><p>Hello</p><script>alert(1)</script></body></html>"
        session, _ = make_get_response(body=html)
        result = asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertIn("Hello", result)
        self.assertNotIn("<p>", result)
        self.assertNotIn("alert", result)
        self.assertNotIn("body{}", result)

    def test_fetch_text_bom_prefixed_html_is_still_stripped(self):
        """Tests that a UTF-8 BOM before the markup does not defeat the HTML sniff.

        A BOM decodes to a leading U+FEFF, which str.lstrip() does not remove
        (it is not whitespace), so without the decode-time strip the body would
        come back as raw markup instead of extracted text.
        """
        html = "\ufeff<html><body><p>Hello</p></body></html>"
        session, _ = make_get_response(body=html)
        result = asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertIn("Hello", result)
        self.assertNotIn("<p>", result)

    def test_fetch_text_bom_prefixed_plain_text_loses_only_the_bom(self):
        """Tests that a BOM on a non-HTML body is dropped while the text is otherwise unchanged."""
        session, _ = make_get_response(body="\ufeffjust plain text")
        result = asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertEqual(result, "just plain text")

    def test_fetch_text_non_2xx_raises_client_response_error_with_prefix(self):
        """Tests that a non-2xx HTTP error raises ClientResponseError with url_not_accessible prefix."""
        exc = make_response_error(503)
        session, _ = make_get_response(status=503, raise_for_status_exc=exc)
        with self.assertRaises(ClientResponseError) as ctx:
            asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertIn("url_not_accessible", ctx.exception.message)

    def test_fetch_text_429_raises_with_too_many_requests_prefix(self):
        """Tests that a 429 response raises ClientResponseError with too_many_requests prefix."""
        exc = make_response_error(429)
        session, _ = make_get_response(status=429, raise_for_status_exc=exc)
        with self.assertRaises(ClientResponseError) as ctx:
            asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertIn("too_many_requests", ctx.exception.message)

    def test_fetch_text_redirect_raises_url_not_allowed(self):
        """Tests that a 3xx GET response raises ValueError with url_not_allowed and the Location URL."""
        session, response = make_get_response(status=301)
        response.headers["Location"] = "http://other.com/"

        with self.assertRaises(ValueError) as ctx:
            asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        error = str(ctx.exception)
        self.assertIn("url_not_allowed", error)
        self.assertIn("http://other.com/", error)

    def test_fetch_text_connection_error_raises_client_error_with_prefix(self):
        """Tests that a connection error raises ClientError with url_not_accessible prefix."""
        response_cm = MagicMock()
        response_cm.__aenter__ = AsyncMock(side_effect=ClientError("connection reset"))
        response_cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get = MagicMock(return_value=response_cm)

        with self.assertRaises(ClientError) as ctx:
            asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_fetch_text_body_over_limit_raises_response_too_large(self):
        """Tests that a text body exceeding MAX_RESPONSE_BYTES raises response_too_large.

        Guards the text path's own streamed size cap, independent of the HEAD probe
        in get_content_type — the gap a direct fetch_text caller would otherwise hit.
        """
        session, _ = make_get_response(body="x" * 50)
        with patch(f"{MODULE}.MAX_RESPONSE_BYTES", 10):
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertIn("response_too_large", str(ctx.exception))

    def test_fetch_text_private_ip_url_rejected_without_network(self):
        """Tests that fetch_text validates the URL itself, blocking SSRF even without a prior validate_url call.

        The session's get is a MagicMock that would 'succeed' if reached; the raised
        url_not_allowed confirms validation happens at the fetch boundary.
        """
        session = MagicMock()
        session.get = MagicMock()
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(SafeFetch.fetch_text("http://169.254.169.254/latest/meta-data/", session))
        self.assertIn("url_not_allowed", str(ctx.exception))
        session.get.assert_not_called()

    def test_fetch_text_invalid_charset_falls_back_to_utf8(self):
        """Tests that a malformed Content-Type charset never escapes as an untranslated LookupError.

        A server may declare a codec Python does not know; bytes.decode() then raises
        LookupError at codec lookup, before errors="replace" can apply. That error is
        neither ClientError nor a timeout, so it would bypass the fetch methods'
        translation and break their url_not_accessible contract. The decode must fall
        back to utf-8 and return the body instead of raising.
        """
        response = MagicMock()
        response.status = 200
        response.headers = {"Content-Type": "text/plain; charset=not-a-real-codec"}
        response.charset = "not-a-real-codec"
        response.raise_for_status = MagicMock()

        async def iter_chunked(_chunk_size):
            # Valid utf-8 bytes; only the declared charset token is bogus.
            yield "héllo".encode("utf-8")

        response.content.iter_chunked = iter_chunked
        response_cm = MagicMock()
        response_cm.__aenter__ = AsyncMock(return_value=response)
        response_cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.get = MagicMock(return_value=response_cm)

        result = asyncio.run(SafeFetch.fetch_text("http://example.com", session))
        self.assertEqual(result, "héllo")

    def _call_fetch_pdf(self, url: str, session) -> str:
        """Invoke fetch_pdf_text with the given URL and session."""
        return asyncio.run(SafeFetch.fetch_pdf_text(url, session))

    def test_fetch_pdf_returns_joined_page_text(self):
        """Tests that text from all PDF pages is joined into a single newline-separated string."""
        pages = [MagicMock(), MagicMock()]
        pages[0].extract_text.return_value = "Page one"
        pages[1].extract_text.return_value = "Page two"
        mock_reader = MagicMock()
        mock_reader.pages = pages

        with (
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=b"%PDF-fake")),
            patch("neuro_san_studio.coded_tools.utils.pdf_utils.PdfReader", return_value=mock_reader),
        ):
            result = self._call_fetch_pdf("http://example.com/doc.pdf", MagicMock())

        self.assertEqual(result, "Page one\nPage two")

    def test_fetch_pdf_none_page_text_coerced_to_empty(self):
        """Tests that a page whose extract_text() returns None is treated as empty text."""
        pages = [MagicMock(), MagicMock(), MagicMock()]
        pages[0].extract_text.return_value = "Page one"
        pages[1].extract_text.return_value = None
        pages[2].extract_text.return_value = "Page three"
        mock_reader = MagicMock()
        mock_reader.pages = pages

        with (
            patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=b"%PDF-fake")),
            patch("neuro_san_studio.coded_tools.utils.pdf_utils.PdfReader", return_value=mock_reader),
        ):
            result = self._call_fetch_pdf("http://example.com/doc.pdf", MagicMock())

        self.assertEqual(result, "Page one\n\nPage three")

    def test_fetch_pdf_real_pdf_bytes_parse_successfully(self):
        """Tests that genuine PDF bytes are parsed by real pypdf without errors."""
        data = make_pdf_bytes(pages=2)
        with patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=data)):
            result = self._call_fetch_pdf("http://example.com/doc.pdf", MagicMock())
        self.assertIsInstance(result, str)

    def test_fetch_pdf_invalid_pdf_bytes_raise_client_error_with_prefix(self):
        """Tests that unparseable PDF bytes raise ClientError with url_not_accessible prefix."""
        with patch.object(SafeFetch, "download_pdf_bytes", new=AsyncMock(return_value=b"not a pdf")):
            with self.assertRaises(ClientError) as ctx:
                self._call_fetch_pdf("http://example.com/doc.pdf", MagicMock())
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_fetch_pdf_download_uses_provided_session(self):
        """Tests that the PDF download goes through the session passed by async_invoke."""
        data = make_pdf_bytes()
        session, _ = make_stream_session([data])
        self._call_fetch_pdf("http://example.com/doc.pdf", session)
        session.get.assert_called_once()
        self.assertEqual(session.get.call_args.args[0], "http://example.com/doc.pdf")
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    def _call_download_pdf_bytes(self, session, url: str = "http://example.com/doc.pdf") -> bytes:
        """Invoke download_pdf_bytes with the given mocked session."""
        return asyncio.run(SafeFetch.download_pdf_bytes(url, session))

    def test_download_pdf_bytes_joins_streamed_chunks(self):
        """Tests that streamed chunks are concatenated into the full body."""
        session, _ = make_stream_session([b"%PDF", b"-1.4", b" body"])
        self.assertEqual(self._call_download_pdf_bytes(session), b"%PDF-1.4 body")

    def test_download_pdf_bytes_redirect_raises_url_not_allowed(self):
        """Tests that a 3xx response raises ValueError with url_not_allowed."""
        session, _ = make_stream_session([], status=302)
        with self.assertRaises(ValueError) as ctx:
            self._call_download_pdf_bytes(session)
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_download_pdf_bytes_429_maps_to_too_many_requests(self):
        """Tests that HTTP 429 raises ClientResponseError with too_many_requests prefix."""
        session, _ = make_stream_session([], status=429, raise_for_status_exc=make_response_error(429))
        with self.assertRaises(ClientResponseError) as ctx:
            self._call_download_pdf_bytes(session)
        self.assertIn("too_many_requests", str(ctx.exception))

    def test_download_pdf_bytes_http_error_maps_to_url_not_accessible(self):
        """Tests that a non-2xx response raises ClientResponseError with url_not_accessible prefix."""
        session, _ = make_stream_session([], status=500, raise_for_status_exc=make_response_error(500))
        with self.assertRaises(ClientResponseError) as ctx:
            self._call_download_pdf_bytes(session)
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_download_pdf_bytes_content_length_header_over_limit_raises(self):
        """Tests that a Content-Length header above MAX_RESPONSE_BYTES raises response_too_large."""
        session, _ = make_stream_session([b"x"], content_length=MAX_RESPONSE_BYTES + 1)
        with self.assertRaises(ValueError) as ctx:
            self._call_download_pdf_bytes(session)
        self.assertIn("response_too_large", str(ctx.exception))

    def test_download_pdf_bytes_streamed_body_over_limit_raises(self):
        """Tests that a body exceeding MAX_RESPONSE_BYTES on the wire raises response_too_large.

        This covers the server-lies-about-Content-Length case: the header is absent,
        so only the running byte count can enforce the cap.
        """
        session, _ = make_stream_session([b"x" * 8, b"y" * 8])
        with patch("neuro_san_studio.coded_tools.utils.safe_fetch.MAX_RESPONSE_BYTES", 10):
            with self.assertRaises(ValueError) as ctx:
                self._call_download_pdf_bytes(session)
        self.assertIn("response_too_large", str(ctx.exception))

    def test_download_pdf_bytes_connection_error_wrapped_as_url_not_accessible(self):
        """Tests that a connection-level ClientError is wrapped with url_not_accessible prefix."""
        session = MagicMock()
        session.get = MagicMock(side_effect=ClientError("connection reset"))
        with self.assertRaises(ClientError) as ctx:
            self._call_download_pdf_bytes(session)
        self.assertIn("url_not_accessible", str(ctx.exception))

    def test_is_pdf_detects_suffix_despite_query_or_fragment(self):
        """Tests that a .pdf path is detected even with a query string or fragment after it."""
        self.assertTrue(SafeFetch.is_pdf("", "https://example.com/file.pdf?download=1"))
        self.assertTrue(SafeFetch.is_pdf("", "https://example.com/file.PDF#page=2"))
        self.assertTrue(SafeFetch.is_pdf("application/pdf", "https://example.com/report"))
        # A .pdf that is not the path suffix must not match.
        self.assertFalse(SafeFetch.is_pdf("text/html", "https://example.com/file.pdf.html"))
        self.assertFalse(SafeFetch.is_pdf("text/html", "https://example.com/page?name=file.pdf"))

    def test_is_pdf_trusts_concrete_declared_type_over_url_suffix(self):
        """Tests that a concrete declared type beats the ".pdf" suffix; generic types defer to the URL.

        A .pdf path serving declared text/html is an error page or a moved document
        and must not be force-fed to the PDF parser. Generic download types carry no
        format information, so there the URL decides — including a filename that only
        appears in the query string ("/download?name=report.pdf"), which download
        endpoints commonly use.
        """
        # Concrete declared types win over the path suffix.
        self.assertFalse(SafeFetch.is_pdf("text/html", "https://example.com/file.pdf"))
        self.assertFalse(SafeFetch.is_pdf("application/zip", "https://example.com/file.pdf"))
        # Generic download types defer to the URL.
        self.assertTrue(SafeFetch.is_pdf("application/octet-stream", "https://example.com/file.pdf"))
        self.assertTrue(SafeFetch.is_pdf("binary/octet-stream", "https://example.com/file.pdf"))
        # With a generic type, a filename in the query string is still recognized.
        self.assertTrue(SafeFetch.is_pdf("application/octet-stream", "https://example.com/download?name=report.pdf"))
        # A generic type with no .pdf anywhere in the URL is not a PDF.
        self.assertFalse(SafeFetch.is_pdf("application/octet-stream", "https://example.com/download?name=report.zip"))

    def test_is_text_content_type_rejects_images_including_svg(self):
        """Tests that declared image types are not text, even XML-based ones like image/svg+xml."""
        self.assertFalse(SafeFetch.is_text_content_type("image/svg+xml"))
        self.assertFalse(SafeFetch.is_text_content_type("image/png"))
        # Genuinely textual types remain accepted.
        self.assertTrue(SafeFetch.is_text_content_type("application/xml"))
        self.assertTrue(SafeFetch.is_text_content_type("application/json"))
        self.assertTrue(SafeFetch.is_text_content_type("text/markdown"))
        self.assertTrue(SafeFetch.is_text_content_type("TEXT/HTML; charset=utf-8"))

    def test_is_text_content_type_rejects_binary_vendor_types_containing_xml(self):
        """Tests that ZIP-container vendor types whose names contain 'xml' are not treated as text.

        Guards against the old substring scan: .docx/.xlsx/.pptx media types contain
        "xml" (openxmlformats) but are binary ZIP containers, while genuine XML types
        are recognized by the RFC 6839 "+xml" structured suffix.
        """
        self.assertFalse(
            SafeFetch.is_text_content_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        )
        self.assertFalse(
            SafeFetch.is_text_content_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        )
        # Real XML feed/document types keep matching via the "+xml" suffix.
        self.assertTrue(SafeFetch.is_text_content_type("application/rss+xml"))
        self.assertTrue(SafeFetch.is_text_content_type("application/atom+xml"))
        self.assertTrue(SafeFetch.is_text_content_type("application/xhtml+xml"))
