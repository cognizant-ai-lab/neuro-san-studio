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

from coded_tools.tools.web_fetch import MAX_URL_LENGTH
from coded_tools.tools.web_fetch import WebFetch


class TestValidateUrl(TestCase):
    """Unit tests for WebFetch._validate_url."""

    def setUp(self):
        self.tool = WebFetch()

    def _call(self, args):
        """Invoke _validate_url with the given args dict and return the result."""
        return self.tool._validate_url(args)  # pylint: disable=protected-access

    def test_valid_http_url(self):
        """Tests that a valid HTTP URL is accepted."""
        self.assertEqual(self._call({"url": "http://example.com/page"}), "http://example.com/page")

    def test_valid_https_url(self):
        """Tests that a valid HTTPS URL is accepted."""
        self.assertEqual(self._call({"url": "https://example.com"}), "https://example.com")

    def test_strips_whitespace(self):
        """Tests that leading and trailing whitespace is stripped from the URL."""
        self.assertEqual(self._call({"url": "  https://example.com  "}), "https://example.com")

    def test_missing_url_key(self):
        """Tests that a missing 'url' key raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_empty_url(self):
        """Tests that an empty URL string raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": ""})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_non_string_url(self):
        """Tests that a non-string URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": 42})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_none_url(self):
        """Tests that a None URL value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": None})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_ftp_scheme_rejected(self):
        """Tests that an FTP scheme URL is rejected with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": "ftp://example.com"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_url_too_long(self):
        """Tests that a URL exceeding the maximum length raises ValueError with url_too_long."""
        long_url = "https://example.com/" + "a" * MAX_URL_LENGTH
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": long_url})
        self.assertIn("url_too_long", str(ctx.exception))

    def test_url_at_max_length_is_accepted(self):
        """Tests that a URL exactly at the maximum allowed length is accepted."""
        prefix = "https://x.co/"
        url = prefix + "a" * (MAX_URL_LENGTH - len(prefix))
        self.assertEqual(self._call({"url": url}), url)

    def test_missing_hostname(self):
        """Tests that a URL with no hostname raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": "https:///no-host"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_allowed_domains_pass(self):
        """Tests that a URL matching an allowed domain passes validation."""
        url = self._call({"url": "https://api.example.com/data", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://api.example.com/data")

    def test_allowed_domains_exact_match(self):
        """Tests that a URL exactly matching an allowed domain passes validation."""
        url = self._call({"url": "https://example.com/", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com/")

    def test_allowed_domains_rejects_unrelated(self):
        """Tests that a URL not matching any allowed domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": "https://other.test/", "allowed_domains": ["example.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_allowed_domains_does_not_match_partial_prefix(self):
        """Tests that a hostname sharing a suffix but not a domain boundary is rejected."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": "https://badexample.test/", "allowed_domains": ["example.test"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_blocked_domains_rejects(self):
        """Tests that a URL exactly matching a blocked domain raises ValueError with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": "https://blocked.com/", "blocked_domains": ["blocked.com"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_blocked_domains_subdomain_rejected(self):
        """Tests that a subdomain of a blocked domain is also rejected."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"url": "https://sub.blocked.test/", "blocked_domains": ["blocked.test"]})
        self.assertIn("url_not_allowed", str(ctx.exception))

    def test_blocked_domains_partial_prefix_not_blocked(self):
        """Tests that a domain sharing a suffix with a blocked domain but not a boundary is allowed."""
        url = self._call({"url": "https://notblocked.com/", "blocked_domains": ["blocked.com"]})
        self.assertEqual(url, "https://notblocked.com/")

    def test_url_with_port_matches_domain(self):
        """Tests that a URL with a port number still matches the allowed domain correctly."""
        url = self._call({"url": "https://example.com:8080/path", "allowed_domains": ["example.com"]})
        self.assertEqual(url, "https://example.com:8080/path")
