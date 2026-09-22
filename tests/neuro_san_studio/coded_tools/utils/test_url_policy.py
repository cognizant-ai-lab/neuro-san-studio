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

"""Unit tests for UrlPolicy, the URL-level SSRF policy split out of SafeFetch in #1442."""

from typing import Any
from unittest import TestCase

from neuro_san_studio.coded_tools.utils.url_policy import MAX_URL_LENGTH
from neuro_san_studio.coded_tools.utils.url_policy import UrlPolicy


class TestUrlPolicy(TestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for UrlPolicy, the URL-level SSRF policy split out of SafeFetch (#1442).

    Everything here is pure and synchronous: no session, no network, no DNS lookups.
    DNS records are validated at connection time by GlobalOnlyResolver (see
    test_global_only_resolver.py); SafeFetch's delegations to this class are
    covered in test_safe_fetch.py.
    """

    @staticmethod
    def _call_validate_url(args: dict[str, Any]) -> str:
        """
        Invoke UrlPolicy.validate_url with a tool-style args dict and return the result.

        :param args: Dict holding "url" and optionally "allowed_domains" / "blocked_domains".
        :return: The validated URL.
        """
        return UrlPolicy.validate_url(args.get("url", ""), args.get("allowed_domains"), args.get("blocked_domains"))

    def test_validate_url_valid_http_url(self) -> None:
        """Tests that a valid HTTP URL is accepted."""
        self.assertEqual(self._call_validate_url({"url": "http://example.com/page"}), "http://example.com/page")

    def test_validate_url_valid_https_url(self) -> None:
        """Tests that a valid HTTPS URL is accepted."""
        self.assertEqual(self._call_validate_url({"url": "https://example.com"}), "https://example.com")

    def test_validate_url_strips_whitespace(self) -> None:
        """Tests that leading and trailing whitespace is stripped from the URL."""
        self.assertEqual(self._call_validate_url({"url": "  https://example.com  "}), "https://example.com")

    def test_validate_url_missing_url_key(self) -> None:
        """Tests that a missing 'url' key raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_empty_url(self) -> None:
        """Tests that an empty URL string raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": ""})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_non_string_url(self) -> None:
        """Tests that a non-string URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": 42})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_none_url(self) -> None:
        """Tests that a None URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": None})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_ftp_scheme_rejected(self) -> None:
        """Tests that an FTP scheme URL is rejected with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "ftp://example.com"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_url_too_long(self) -> None:
        """Tests that a URL exceeding the maximum length raises ValueError with url_too_long."""
        long_url = "https://example.com/" + "a" * MAX_URL_LENGTH
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": long_url})
        self.assertIn("url_too_long", str(ctx.exception))

    def test_validate_url_url_at_max_length_is_accepted(self) -> None:
        """Tests that a URL exactly at the maximum allowed length is accepted."""
        prefix = "https://test.co/"
        url = prefix + "a" * (MAX_URL_LENGTH - len(prefix))
        self.assertEqual(self._call_validate_url({"url": url}), url)

    def test_validate_url_missing_hostname(self) -> None:
        """Tests that a URL with no hostname raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https:///no-host"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_allowed_domains_pass(self) -> None:
        """Tests that a URL matching an allowed domain passes validation."""
        url = self._call_validate_url({"url": "https://api.example.com/data", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://api.example.com/data")

    def test_validate_url_allowed_domains_exact_match(self) -> None:
        """Tests that a URL exactly matching an allowed domain passes validation."""
        url = self._call_validate_url({"url": "https://example.com/", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com/")

    def test_validate_url_allowed_domains_rejects_unrelated(self) -> None:
        """Tests that a URL not matching any allowed domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-other.com/", "allowed_domains": ["test-example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_allowed_domains_does_not_match_partial_prefix(self) -> None:
        """Tests that a hostname sharing a suffix but not a domain boundary is rejected."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-badexample.com/", "allowed_domains": ["test-example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_blocked_domains_rejects(self) -> None:
        """Tests that a URL exactly matching a blocked domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-blocked.com/", "blocked_domains": ["test-blocked.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_blocked_domains_subdomain_rejected(self) -> None:
        """Tests that a subdomain of a blocked domain is also rejected."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-sub.blocked.com/", "blocked_domains": ["blocked.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_blocked_domains_partial_prefix_not_blocked(self) -> None:
        """Tests that a domain sharing a suffix with a blocked domain but not a boundary is allowed."""
        url = self._call_validate_url({"url": "https://test-notblocked.com/", "blocked_domains": ["test-blocked.com"]})
        self.assertEqual(url, "https://test-notblocked.com/")

    def test_validate_url_url_with_port_matches_domain(self) -> None:
        """Tests that a URL with a port number still matches the allowed domain correctly."""
        url = self._call_validate_url({"url": "https://example.com:8080/path", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com:8080/path")

    def test_validate_url_blocked_domain_checked_against_hostname(self) -> None:
        """Tests that blocked domains are enforced on the hostname itself."""
        # Regression test: the hostname must never be replaced by a resolved IP
        # before domain checks run.
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://test-blocked.com/x", "blocked_domains": ["test-blocked.com"]})
        self.assertIn("Domain 'test-blocked.com' is blocked", str(ctx.exception))

    def test_validate_url_trailing_dot_host_still_blocked(self) -> None:
        """Tests that a trailing-dot FQDN cannot bypass a block-list entry.

        'example.com.' is DNS-equivalent to 'example.com'; without canonicalizing
        the hostname it would evade blocked_domains=['example.com'].
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://example.com./x", "blocked_domains": ["example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_trailing_dot_host_matches_allowed(self) -> None:
        """Tests that a trailing-dot FQDN still matches an allowed_domains entry."""
        url = self._call_validate_url({"url": "https://example.com./data", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com./data")

    def test_validate_url_trailing_dot_localhost_blocked(self) -> None:
        """Tests that 'localhost.' cannot dodge the loopback guard via a trailing dot."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "http://localhost./"})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_idn_unicode_host_matches_punycode_block(self) -> None:
        """Tests that a Unicode IDN host is blocked by its punycode blocked_domains entry.

        aiohttp connects to the IDNA-ASCII form, so 'münchen.de' must match a
        blocked 'xn--mnchen-3ya.de' or the block is bypassed by spelling.
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://münchen.de/x", "blocked_domains": ["xn--mnchen-3ya.de"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_idn_punycode_host_matches_unicode_block(self) -> None:
        """Tests the inverse spelling: a punycode host is blocked by a Unicode blocked_domains entry."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://xn--mnchen-3ya.de/x", "blocked_domains": ["münchen.de"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_invalid_port_rejected(self) -> None:
        """Tests that a non-numeric port raises invalid_input rather than failing later in aiohttp."""
        # Assembled from parts so the CI link checker (lychee) does not extract and
        # fail to parse this deliberately-invalid port.
        bad_port_url = "https://example.com" + ":not-a-port/x"
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": bad_port_url})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_unmatched_ipv6_bracket_rejected(self) -> None:
        """Tests that a malformed IPv6 authority (unmatched bracket) raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://[::1/x"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_url_unicode_dot_separator_host_still_blocked(self) -> None:
        """Tests that a Unicode dot separator (U+3002) cannot bypass a block-list entry.

        IDNA encoding maps 'example.com。' to the trailing-dot form of 'example.com',
        so it must be blocked by blocked_domains=['example.com'].
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://example.com。/x", "blocked_domains": ["example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_unicode_dot_separator_localhost_blocked(self) -> None:
        """Tests that 'localhost。' (U+3002) cannot dodge the loopback guard."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "http://localhost。/"})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_trailing_dot_block_entry_matches_bare_host(self) -> None:
        """Tests that a fully-qualified block-list entry ('example.com.') blocks the bare host."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://example.com/x", "blocked_domains": ["example.com."]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_uts46_mapping_matches_yarl(self) -> None:
        """Tests that canonicalization uses UTS#46 (like yarl), not IDNA2003.

        IDNA2003 maps 'faß.de' to 'fass.de', but aiohttp/yarl connect to
        'xn--fa-hia.de'; a UTS#46 block entry in that punycode form must therefore
        block the Unicode host, which IDNA2003 would let bypass.
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_url({"url": "https://faß.de/x", "blocked_domains": ["xn--fa-hia.de"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_url_root_only_host_rejected(self) -> None:
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

    @staticmethod
    def _call_validate_hostname_safety(hostname: str) -> None:
        """
        Invoke UrlPolicy.validate_hostname_safety with the given hostname.

        :param hostname: The already-lower-cased host to check.
        """
        UrlPolicy.validate_hostname_safety(hostname)

    def test_validate_hostname_safety_non_ip_hostname_allowed_without_dns(self) -> None:
        """Tests that a non-IP hostname passes without a DNS lookup (validated later by the resolver)."""
        self._call_validate_hostname_safety("example.com")  # should not raise

    def test_validate_hostname_safety_public_ip_allowed(self) -> None:
        """Tests that a publicly routable IP address does not raise an error."""
        self._call_validate_hostname_safety("8.8.8.8")  # should not raise

    def test_validate_hostname_safety_localhost_blocked(self) -> None:
        """Tests that 'localhost' is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("localhost")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_localhost_subdomain_blocked(self) -> None:
        """Tests that a subdomain of localhost is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("app.localhost")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_loopback_ipv4_blocked(self) -> None:
        """Tests that the IPv4 loopback address 127.0.0.1 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("127.0.0.1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_private_ipv4_blocked(self) -> None:
        """Tests that private IPv4 addresses are blocked with url_not_allowed."""
        for ip in ("10.0.0.1", "192.168.1.1", "172.16.0.1"):
            with self.subTest(ip=ip):
                with self.assertRaises(ValueError) as ctx:
                    self._call_validate_hostname_safety(ip)
                self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_link_local_blocked(self) -> None:
        """Tests that a link-local IP address such as the AWS metadata endpoint is blocked."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("169.254.169.254")  # AWS metadata endpoint
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_integer_and_shorthand_ipv4_literals_blocked(self) -> None:
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

    def test_validate_hostname_safety_ipv6_loopback_blocked(self) -> None:
        """Tests that the IPv6 loopback address ::1 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("::1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_unspecified_ipv4_blocked(self) -> None:
        """Tests that the unspecified IPv4 address 0.0.0.0 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("0.0.0.0")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_unspecified_ipv6_blocked(self) -> None:
        """Tests that the unspecified IPv6 address :: is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("::")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_cgnat_blocked(self) -> None:
        """Tests that a CGNAT address (100.64.0.0/10) is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_hostname_safety("100.64.0.1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_validate_hostname_safety_zoned_ipv6_link_local_blocked(self) -> None:
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

    def test_validate_hostname_safety_malformed_ip_like_string_blocked(self) -> None:
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

    def test_validate_hostname_safety_malformed_chars_rejected(self) -> None:
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

    def test_validate_hostname_safety_underscore_label_allowed(self) -> None:
        """Tests that underscore labels are tolerated (aiohttp/yarl accept them), not over-rejected."""
        self._call_validate_hostname_safety("a_b.example.com")  # should not raise

    @staticmethod
    def _call_validate_domain_list(value: Any, param_name: str = "test_param") -> list[str]:
        """
        Invoke UrlPolicy.validate_domain_list with the given value and return the result.

        :param value: The candidate domain-list parameter.
        :param param_name: The parameter name to report in error messages.
        :return: The coerced list of domains.
        """
        return UrlPolicy.validate_domain_list(value, param_name)

    def test_validate_domain_list_none_returns_empty_list(self) -> None:
        """Tests that passing None returns an empty list."""
        self.assertEqual(self._call_validate_domain_list(None), [])

    def test_validate_domain_list_single_string_coerced_to_list(self) -> None:
        """Tests that a single string domain is coerced into a one-element list."""
        self.assertEqual(self._call_validate_domain_list("example.com"), ["example.com"])

    def test_validate_domain_list_valid_list_returned_unchanged(self) -> None:
        """Tests that a valid list of domain strings is returned unchanged."""
        domains = ["example.com", "other.org"]
        self.assertEqual(self._call_validate_domain_list(domains), domains)

    def test_validate_domain_list_non_list_non_string_raises(self) -> None:
        """Tests that a non-list, non-string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_domain_list(123)
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_domain_list_list_with_non_string_element_raises(self) -> None:
        """Tests that a list containing a non-string element raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_domain_list(["example.com", 42])
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_domain_list_dict_raises(self) -> None:
        """Tests that passing a dict raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_domain_list({"domain": "example.com"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_redact_for_log_replaces_query_and_drops_fragment(self) -> None:
        """Tests that a presigned-style URL is logged with its query replaced by a marker and no fragment."""
        url: str = "https://files.example.com/report.pdf?X-Amz-Signature=secret-token&X-Amz-Expires=300#page=2"
        redacted: str = UrlPolicy.redact_for_log(url)
        self.assertEqual(redacted, "https://files.example.com/report.pdf?[redacted]")
        self.assertNotIn("secret-token", redacted)

    def test_redact_for_log_drops_userinfo_and_keeps_port(self) -> None:
        """Tests that credentials in userinfo are removed while the host and a non-default port survive."""
        self.assertEqual(
            UrlPolicy.redact_for_log("https://user:pass@example.com:8443/path/doc"),
            "https://example.com:8443/path/doc",
        )

    def test_redact_for_log_leaves_plain_url_unchanged(self) -> None:
        """Tests that a URL without query, fragment or userinfo is returned as it was."""
        self.assertEqual(UrlPolicy.redact_for_log("http://example.com/page"), "http://example.com/page")

    def test_redact_for_log_keeps_ipv6_brackets(self) -> None:
        """Tests that an IPv6 literal host keeps its brackets so the log line is still a URL."""
        self.assertEqual(
            UrlPolicy.redact_for_log("http://[2001:db8::1]:8080/x?y=1"), "http://[2001:db8::1]:8080/x?[redacted]"
        )

    def test_redact_for_log_reports_unparseable_url(self) -> None:
        """Tests that a URL urlparse rejects is replaced by a fixed marker rather than logged raw."""
        self.assertEqual(UrlPolicy.redact_for_log("https://[::1/"), "[unparseable url]")

    def test_redact_urls_in_text_redacts_quoted_url_in_error_message(self) -> None:
        """Tests that a SafeFetch-style error message quoting a presigned URL loses the query but keeps its shape."""
        message: str = "url_not_accessible: Could not reach 'https://files.example.com/a.pdf?X-Amz-Signature=secret'."
        redacted: str = UrlPolicy.redact_urls_in_text(message)
        self.assertEqual(redacted, "url_not_accessible: Could not reach 'https://files.example.com/a.pdf?[redacted]'.")
        self.assertNotIn("secret", redacted)

    def test_redact_urls_in_text_handles_several_urls_and_trailing_punctuation(self) -> None:
        """Tests that every embedded URL is redacted and sentence punctuation after a bare URL survives."""
        message: str = "from http://example.com/a?k=1, to http://example.org/b?k=2."
        self.assertEqual(
            UrlPolicy.redact_urls_in_text(message),
            "from http://example.com/a?[redacted], to http://example.org/b?[redacted].",
        )

    def test_redact_urls_in_text_leaves_text_without_urls_unchanged(self) -> None:
        """Tests that text holding no URL is returned as it was."""
        self.assertEqual(UrlPolicy.redact_urls_in_text("connection reset by peer"), "connection reset by peer")

    def test_redact_urls_in_text_matches_upper_case_scheme(self) -> None:
        """Tests that an upper-case scheme, which validate_url accepts and preserves, is still redacted in text."""
        message: str = "url_not_accessible: Could not reach 'HTTPS://files.example.com/a.pdf?token=secret'."
        redacted: str = UrlPolicy.redact_urls_in_text(message)
        self.assertNotIn("secret", redacted)
        self.assertEqual(redacted, "url_not_accessible: Could not reach 'https://files.example.com/a.pdf?[redacted]'.")
