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

from unittest import TestCase

from neuro_san_studio.coded_tools.web_fetch import WebFetch


class TestValidateHostnameSafety(TestCase):
    """Unit tests for WebFetch._validate_hostname_safety.

    This method only checks localhost names and IP literals. Non-IP hostnames
    pass through without DNS resolution: their records are validated at
    connection time by GlobalOnlyResolver (see test_global_only_resolver.py).
    """

    def setUp(self):
        self.tool = WebFetch()

    def _call(self, hostname: str) -> None:
        """Invoke _validate_hostname_safety with the given hostname."""
        self.tool._validate_hostname_safety(hostname)  # pylint: disable=protected-access

    def test_non_ip_hostname_allowed_without_dns(self):
        """Tests that a non-IP hostname passes without a DNS lookup (validated later by the resolver)."""
        self._call("example.com")  # should not raise

    def test_public_ip_allowed(self):
        """Tests that a publicly routable IP address does not raise an error."""
        self._call("8.8.8.8")  # should not raise

    def test_localhost_blocked(self):
        """Tests that 'localhost' is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call("localhost")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_localhost_subdomain_blocked(self):
        """Tests that a subdomain of localhost is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call("app.localhost")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_loopback_ipv4_blocked(self):
        """Tests that the IPv4 loopback address 127.0.0.1 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call("127.0.0.1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_private_ipv4_blocked(self):
        """Tests that private IPv4 addresses are blocked with url_not_allowed."""
        for ip in ("10.0.0.1", "192.168.1.1", "172.16.0.1"):
            with self.subTest(ip=ip):
                with self.assertRaises(ValueError) as ctx:
                    self._call(ip)
                self.assertIn("url_not_allowed", str(ctx.exception))

    def test_link_local_blocked(self):
        """Tests that a link-local IP address such as the AWS metadata endpoint is blocked."""
        with self.assertRaises(ValueError) as ctx:
            self._call("169.254.169.254")  # AWS metadata endpoint
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_ipv6_loopback_blocked(self):
        """Tests that the IPv6 loopback address ::1 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call("::1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_unspecified_ipv4_blocked(self):
        """Tests that the unspecified IPv4 address 0.0.0.0 is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call("0.0.0.0")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_unspecified_ipv6_blocked(self):
        """Tests that the unspecified IPv6 address :: is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call("::")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_cgnat_blocked(self):
        """Tests that a CGNAT address (100.64.0.0/10) is blocked with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call("100.64.0.1")
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_zoned_ipv6_link_local_blocked(self):
        """Tests that zoned IPv6 link-local literals (RFC 6874) are blocked with url_not_allowed.

        Covers both the raw zone form and the percent-encoded form as surfaced by
        urlparse().hostname. ip_address() parses zoned literals on Python >= 3.9,
        so these are rejected as non-global addresses.
        """
        for hostname in ("fe80::1%eth0", "fe80::1%25eth0"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError) as ctx:
                    self._call(hostname)
                self.assertIn("url_not_allowed", str(ctx.exception))

    def test_malformed_ip_like_string_blocked(self):
        """Tests that IP-like strings that ip_address() cannot parse fail closed.

        '%' and ':' are illegal in DNS hostnames, so such strings can only be
        malformed or zoned IP literals. They must be rejected rather than deferred
        to the resolver, because aiohttp's literal detection may treat them as IP
        literals and bypass GlobalOnlyResolver.
        """
        for hostname in ("fe80::1%", "gggg::1", "1.2.3.4%zone"):
            with self.subTest(hostname=hostname):
                with self.assertRaises(ValueError) as ctx:
                    self._call(hostname)
                self.assertIn("url_not_allowed", str(ctx.exception))
