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

from neuro_san_studio.coded_tools.file_management.read_file import ReadFile


class TestValidateLineRange(TestCase):
    """Unit tests for ReadFile._validate_line_range."""

    def setUp(self):
        self.tool = ReadFile()

    def _call(self, args):
        """Invoke _validate_line_range with the given args dict and return the result."""
        return self.tool._validate_line_range(args)  # pylint: disable=protected-access

    def test_defaults_to_start_1_and_end_none(self):
        """Tests that omitting both keys returns (1, None)."""
        self.assertEqual(self._call({}), (1, None))

    def test_explicit_values_returned(self):
        """Tests that explicit valid start_line and end_line are returned as-is."""
        self.assertEqual(self._call({"start_line": 2, "end_line": 5}), (2, 5))

    def test_start_equal_to_end_accepted(self):
        """Tests that start_line == end_line is accepted (single-line read)."""
        self.assertEqual(self._call({"start_line": 3, "end_line": 3}), (3, 3))

    def test_zero_start_raises(self):
        """Tests that start_line=0 raises invalid_input (must be positive)."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"start_line": 0})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_negative_start_raises(self):
        """Tests that a negative start_line raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"start_line": -1})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_string_start_raises(self):
        """Tests that a non-integer start_line raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"start_line": "1"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_zero_end_raises(self):
        """Tests that end_line=0 raises invalid_input (must be positive)."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"end_line": 0})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_end_less_than_start_raises(self):
        """Tests that end_line < start_line raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"start_line": 5, "end_line": 3})
        self.assertIn("invalid_input", str(ctx.exception))
