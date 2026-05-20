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

import tempfile
from pathlib import Path
from unittest import TestCase

from neuro_san_studio.coded_tools.file_management.read_file import ReadFile


class TestPathMatchesAny(TestCase):
    """Unit tests for ReadFile._path_matches_any."""

    def setUp(self):
        self.tool = ReadFile()
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()
        (self.tmp_root / "sub").mkdir()
        self.file = self.tmp_root / "sub" / "a.txt"
        self.file.write_text("x", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _call(self, file_path, path_list):
        """Invoke _path_matches_any and return the boolean result."""
        return self.tool._path_matches_any(file_path, path_list)  # pylint: disable=protected-access

    def test_empty_list_returns_false(self):
        """Tests that an empty list matches no paths."""
        self.assertFalse(self._call(self.file, []))

    def test_exact_file_match_returns_true(self):
        """Tests that the file's own path in the list matches."""
        self.assertTrue(self._call(self.file, [str(self.file)]))

    def test_parent_directory_matches(self):
        """Tests that a directory containing the file matches."""
        self.assertTrue(self._call(self.file, [str(self.tmp_root)]))

    def test_grandparent_directory_matches(self):
        """Tests that any ancestor directory matches via descendant relation."""
        self.assertTrue(self._call(self.file, [str(self.tmp_root.parent)]))

    def test_sibling_directory_does_not_match(self):
        """Tests that a directory not containing the file is not a match."""
        other = self.tmp_root / "other"
        other.mkdir()
        self.assertFalse(self._call(self.file, [str(other)]))

    def test_unrelated_path_does_not_match(self):
        """Tests that an unrelated path does not match."""
        self.assertFalse(self._call(self.file, ["/totally/different/place"]))

    def test_one_of_many_matches(self):
        """Tests that the function returns True as soon as any entry matches."""
        self.assertTrue(self._call(self.file, ["/nope", str(self.tmp_root), "/also/nope"]))

    def test_tilde_entry_expanded(self):
        """Tests that an allow-list entry like '~' is expanded to the user home directory."""
        home_file: Path = (Path.home() / "definitely-not-a-real-file.txt").resolve()
        # A path under $HOME should match an allow-list entry of '~' or '~/'.
        self.assertTrue(self._call(home_file, ["~"]))

    def test_invalid_entry_skipped(self):
        """Tests that an unresolvable entry doesn't crash the search."""
        # A null byte in a path is rejected by Path.resolve on most platforms.
        self.assertTrue(self._call(self.file, ["bad\x00entry", str(self.tmp_root)]))
