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

from coded_tools.tools.web_fetch import MAX_CHARS
from coded_tools.tools.web_fetch import WebFetch


class TestValidateMaxContentChars(TestCase):
    """Unit tests for WebFetch._validate_max_content_chars."""

    def setUp(self):
        self.tool = WebFetch()

    def _call(self, args):
        """Invoke _validate_max_content_chars with the given args dict and return the result."""
        return self.tool._validate_max_content_chars(args)  # pylint: disable=protected-access

    def test_default_value_used_when_absent(self):
        """Tests that the default MAX_CHARS value is returned when max_content_chars is absent."""
        self.assertEqual(self._call({}), MAX_CHARS)

    def test_valid_positive_int(self):
        """Tests that a valid positive integer is accepted and returned as-is."""
        self.assertEqual(self._call({"max_content_chars": 500}), 500)

    def test_zero_raises(self):
        """Tests that zero raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": 0})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_negative_raises(self):
        """Tests that a negative value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": -1})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_string_raises(self):
        """Tests that a string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": "1000"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_float_raises(self):
        """Tests that a float value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"max_content_chars": 1000.0})
        self.assertIn("invalid_input", str(ctx.exception))
