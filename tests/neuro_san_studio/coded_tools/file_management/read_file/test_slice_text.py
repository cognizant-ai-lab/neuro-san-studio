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


class TestSliceText(TestCase):
    """Unit tests for ReadFile._slice_text."""

    def setUp(self):
        self.tool = ReadFile()

    def _call(self, raw_text, start_line=1, end_line=None, max_chars=10_000):
        """Invoke _slice_text with the given args and return the result tuple."""
        return self.tool._slice_text(raw_text, start_line, end_line, max_chars)  # pylint: disable=protected-access

    def test_full_text_returned_with_defaults(self):
        """Tests that start_line=1 and end_line=None return the full file."""
        text = "a\nb\nc\n"
        content, start, end, total = self._call(text)
        self.assertEqual(content, text)
        self.assertEqual((start, end, total), (1, 3, 3))

    def test_line_range_slice(self):
        """Tests that an explicit line range returns only those lines."""
        text = "a\nb\nc\nd\n"
        content, start, end, total = self._call(text, start_line=2, end_line=3)
        self.assertEqual(content, "b\nc\n")
        self.assertEqual((start, end, total), (2, 3, 4))

    def test_end_line_clamped_to_total(self):
        """Tests that end_line beyond the file length is clamped to total_lines."""
        text = "a\nb\n"
        content, start, end, total = self._call(text, start_line=1, end_line=99)
        self.assertEqual(content, text)
        self.assertEqual((start, end, total), (1, 2, 2))

    def test_max_chars_truncates(self):
        """Tests that the content is truncated to max_chars."""
        text = "abcdefghij\n"
        content, _, _, _ = self._call(text, max_chars=5)
        self.assertEqual(content, "abcde")

    def test_empty_text(self):
        """Tests that an empty input returns empty content and zero lines."""
        content, start, end, total = self._call("")
        self.assertEqual(content, "")
        self.assertEqual(total, 0)
        self.assertEqual(start, 1)
        self.assertEqual(end, 0)

    def test_single_line_no_trailing_newline(self):
        """Tests that a one-line file without a trailing newline is handled correctly."""
        content, start, end, total = self._call("hello")
        self.assertEqual(content, "hello")
        self.assertEqual((start, end, total), (1, 1, 1))

    def test_start_line_past_eof_returns_empty(self):
        """Tests that start_line beyond total_lines returns empty content with consistent bounds.

        Bounds satisfy actual_start > actual_end (a well-formed empty range), and we never
        silently return content from a line the caller didn't ask for.
        """
        content, start, end, total = self._call("a\nb\n", start_line=999)
        self.assertEqual(content, "")
        self.assertEqual(total, 2)
        self.assertGreater(start, end)
