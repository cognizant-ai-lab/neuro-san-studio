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


class TestCheckPathExists(TestCase):
    """Unit tests for ReadFile._check_path_exists."""

    def setUp(self):
        self.tool = ReadFile()
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _call(self, path: Path) -> None:
        """Invoke _check_path_exists; returns None or raises."""
        self.tool._check_path_exists(path)  # pylint: disable=protected-access

    def test_existing_file_passes(self):
        """Tests that an existing regular file passes the check."""
        path = self.tmp_root / "a.txt"
        path.write_text("x", encoding="utf-8")
        self._call(path)  # should not raise

    def test_nonexistent_path_raises(self):
        """Tests that a missing path raises path_not_found."""
        with self.assertRaises(ValueError) as ctx:
            self._call(self.tmp_root / "missing.txt")
        self.assertIn("path_not_found", str(ctx.exception))

    def test_directory_raises(self):
        """Tests that a directory raises is_a_directory."""
        with self.assertRaises(ValueError) as ctx:
            self._call(self.tmp_root)
        self.assertIn("is_a_directory", str(ctx.exception))
