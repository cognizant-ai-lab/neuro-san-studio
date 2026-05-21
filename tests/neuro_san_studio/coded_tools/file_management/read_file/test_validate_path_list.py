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


class TestValidatePathList(TestCase):
    """Unit tests for ReadFile._validate_path_list."""

    def setUp(self):
        self.tool = ReadFile()

    def _call(self, value, param_name="test_param"):
        """Invoke _validate_path_list with the given value and return the result."""
        return self.tool._validate_path_list(value, param_name)  # pylint: disable=protected-access

    def test_none_returns_empty_list(self):
        """Tests that passing None returns an empty list (deny all)."""
        self.assertEqual(self._call(None), [])

    def test_single_string_coerced_to_list(self):
        """Tests that a single string path is coerced into a one-element list."""
        self.assertEqual(self._call("/some/path"), ["/some/path"])

    def test_valid_list_returned_unchanged(self):
        """Tests that a valid list of path strings is returned unchanged."""
        paths = ["/a", "/b/c"]
        self.assertEqual(self._call(paths), paths)

    def test_empty_list_returned_as_empty(self):
        """Tests that an empty list is returned unchanged (also means deny all)."""
        self.assertEqual(self._call([]), [])

    def test_non_list_non_string_raises(self):
        """Tests that a non-list, non-string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call(123)
        self.assertIn("invalid_input", str(ctx.exception))

    def test_list_with_non_string_element_raises(self):
        """Tests that a list containing a non-string element raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call(["/a", 42])
        self.assertIn("invalid_input", str(ctx.exception))

    def test_dict_raises(self):
        """Tests that passing a dict raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call({"path": "/a"})
        self.assertIn("invalid_input", str(ctx.exception))
