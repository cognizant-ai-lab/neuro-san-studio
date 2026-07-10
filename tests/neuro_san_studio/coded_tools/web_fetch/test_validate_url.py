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

from unittest import IsolatedAsyncioTestCase

from neuro_san_studio.coded_tools.web_fetch import MAX_URL_LENGTH
from neuro_san_studio.coded_tools.web_fetch import WebFetch
from tests.neuro_san_studio.coded_tools.web_fetch.helpers import make_dns_patch


class TestValidateUrl(IsolatedAsyncioTestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for WebFetch._validate_url."""

    def setUp(self):
        self.tool = WebFetch()
        # Resolve every hostname to a public IP so tests never do live DNS lookups.
        dns_patcher = make_dns_patch(["93.184.216.34"])
        dns_patcher.start()
        self.addCleanup(dns_patcher.stop)

    async def _call(self, args):
        """Invoke _validate_url with the given args dict and return the result."""
        return await self.tool._validate_url(args)  # pylint: disable=protected-access

    async def test_valid_http_url(self):
        """Tests that a valid HTTP URL is accepted."""
        self.assertEqual(await self._call({"url": "http://example.com/page"}), "http://example.com/page")

    async def test_valid_https_url(self):
        """Tests that a valid HTTPS URL is accepted."""
        self.assertEqual(await self._call({"url": "https://example.com"}), "https://example.com")

    async def test_strips_whitespace(self):
        """Tests that leading and trailing whitespace is stripped from the URL."""
        self.assertEqual(await self._call({"url": "  https://example.com  "}), "https://example.com")

    async def test_missing_url_key(self):
        """Tests that a missing 'url' key raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({})
        self.assertIn("invalid_input", str(ctx.exception))

    async def test_empty_url(self):
        """Tests that an empty URL string raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": ""})
        self.assertIn("invalid_input", str(ctx.exception))

    async def test_non_string_url(self):
        """Tests that a non-string URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": 42})
        self.assertIn("invalid_input", str(ctx.exception))

    async def test_none_url(self):
        """Tests that a None URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": None})
        self.assertIn("invalid_input", str(ctx.exception))

    async def test_ftp_scheme_rejected(self):
        """Tests that an FTP scheme URL is rejected with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": "ftp://example.com"})
        self.assertIn("invalid_input", str(ctx.exception))

    async def test_url_too_long(self):
        """Tests that a URL exceeding the maximum length raises ValueError with url_too_long."""
        long_url = "https://example.com/" + "a" * MAX_URL_LENGTH
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": long_url})
        self.assertIn("url_too_long", str(ctx.exception))

    async def test_url_at_max_length_is_accepted(self):
        """Tests that a URL exactly at the maximum allowed length is accepted."""
        prefix = "https://test.co/"
        url = prefix + "a" * (MAX_URL_LENGTH - len(prefix))
        self.assertEqual(await self._call({"url": url}), url)

    async def test_missing_hostname(self):
        """Tests that a URL with no hostname raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": "https:///no-host"})
        self.assertIn("invalid_input", str(ctx.exception))

    async def test_allowed_domains_pass(self):
        """Tests that a URL matching an allowed domain passes validation."""
        url = await self._call({"url": "https://api.example.com/data", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://api.example.com/data")

    async def test_allowed_domains_exact_match(self):
        """Tests that a URL exactly matching an allowed domain passes validation."""
        url = await self._call({"url": "https://example.com/", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com/")

    async def test_allowed_domains_rejects_unrelated(self):
        """Tests that a URL not matching any allowed domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": "https://test-other.com/", "allowed_domains": ["test-example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_allowed_domains_does_not_match_partial_prefix(self):
        """Tests that a hostname sharing a suffix but not a domain boundary is rejected."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": "https://test-badexample.com/", "allowed_domains": ["test-example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_blocked_domains_rejects(self):
        """Tests that a URL exactly matching a blocked domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": "https://test-blocked.com/", "blocked_domains": ["test-blocked.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_blocked_domains_subdomain_rejected(self):
        """Tests that a subdomain of a blocked domain is also rejected."""
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": "https://test-sub.blocked.com/", "blocked_domains": ["blocked.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_blocked_domains_partial_prefix_not_blocked(self):
        """Tests that a domain sharing a suffix with a blocked domain but not a boundary is allowed."""
        url = await self._call({"url": "https://test-notblocked.com/", "blocked_domains": ["test-blocked.com"]})
        self.assertEqual(url, "https://test-notblocked.com/")

    async def test_url_with_port_matches_domain(self):
        """Tests that a URL with a port number still matches the allowed domain correctly."""
        url = await self._call({"url": "https://example.com:8080/path", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com:8080/path")

    async def test_hostname_resolving_to_private_ip_rejected(self):
        """Tests that a URL whose hostname resolves to a private IP is rejected with url_not_allowed."""
        with make_dns_patch(["192.168.1.10"]):
            with self.assertRaises(ValueError) as ctx:
                await self._call({"url": "https://internal.example.com/"})
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_blocked_domain_rejected_before_dns(self):
        """Tests that blocked domains are enforced on the hostname, not on a resolved IP."""
        # Regression test: hostname must not be replaced by its resolved IP before domain checks.
        with self.assertRaises(ValueError) as ctx:
            await self._call({"url": "https://test-blocked.com/x", "blocked_domains": ["test-blocked.com"]})
        self.assertIn("Domain 'test-blocked.com' is blocked", str(ctx.exception))
