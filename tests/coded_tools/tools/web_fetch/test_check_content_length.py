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

from coded_tools.tools.web_fetch import MAX_RESPONSE_BYTES
from coded_tools.tools.web_fetch import WebFetch


class TestCheckContentLength(TestCase):
    """Unit tests for WebFetch._check_content_length."""

    def setUp(self):
        self.tool = WebFetch()

    def _call(self, header, url="http://example.com"):
        """Invoke _check_content_length with the given Content-Length header value."""
        self.tool._check_content_length(header, url)  # pylint: disable=protected-access

    def test_none_header_does_not_raise(self):
        """Tests that a missing (None) Content-Length header does not raise."""
        self._call(None)  # should not raise

    def test_within_limit_does_not_raise(self):
        """Tests that a Content-Length below the limit does not raise."""
        self._call(str(MAX_RESPONSE_BYTES - 1))

    def test_exactly_at_limit_does_not_raise(self):
        """Tests that a Content-Length exactly at the limit does not raise."""
        self._call(str(MAX_RESPONSE_BYTES))

    def test_over_limit_raises(self):
        """Tests that a Content-Length exceeding the limit raises ValueError with response_too_large."""
        with self.assertRaises(ValueError) as ctx:
            self._call(str(MAX_RESPONSE_BYTES + 1))
        self.assertIn("response_too_large", str(ctx.exception))

    def test_non_numeric_header_does_not_raise(self):
        """Tests that a non-numeric Content-Length header value does not raise."""
        self._call("chunked")  # should not raise
