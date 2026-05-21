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


class TestCheckPathAllowed(TestCase):
    """Unit tests for ReadFile._check_path_allowed access-control logic."""

    def setUp(self):
        self.tool = ReadFile()
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()
        self.file = self.tmp_root / "doc.txt"
        self.file.write_text("x", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _check(self, allowed_paths, allowed_exts=None, blocked_paths=None, blocked_exts=None, path=None):
        """Invoke _check_path_allowed with sensible defaults; returns None or raises."""
        return self.tool._check_path_allowed(  # pylint: disable=protected-access
            path or self.file,
            allowed_paths,
            allowed_exts,
            blocked_paths or [],
            blocked_exts,
        )

    def test_path_outside_allow_list_denied(self):
        """Tests that a file outside every allowed_paths entry is denied."""
        with self.assertRaises(ValueError) as ctx:
            self._check(["/some/other/root"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_path_inside_allowed_dir_passes(self):
        """Tests that a file inside an allowed directory passes the path check."""
        self._check([str(self.tmp_root)])  # should not raise

    def test_exact_file_match_passes(self):
        """Tests that an exact file path in allowed_paths is accepted."""
        self._check([str(self.file)])  # should not raise

    def test_omitted_extensions_passes(self):
        """Tests that omitted allowed_file_extensions (None) skips the extension check."""
        self._check([str(self.tmp_root)], allowed_exts=None)  # should not raise

    def test_empty_extensions_denies_all(self):
        """Tests that an empty allowed_file_extensions list denies the read."""
        with self.assertRaises(ValueError) as ctx:
            self._check([str(self.tmp_root)], allowed_exts=[])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_extension_not_in_allow_list_denied(self):
        """Tests that a file with an extension not in allowed_file_extensions is denied."""
        with self.assertRaises(ValueError) as ctx:
            self._check([str(self.tmp_root)], allowed_exts=[".md"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_extension_in_allow_list_passes(self):
        """Tests that a file with an extension in allowed_file_extensions is accepted."""
        self._check([str(self.tmp_root)], allowed_exts=[".txt"])  # should not raise

    def test_extension_normalized_to_lowercase(self):
        """Tests that case differences in extensions are handled by normalization."""
        upper_file = self.tmp_root / "DOC.TXT"
        upper_file.write_text("x", encoding="utf-8")
        self._check([str(self.tmp_root)], allowed_exts=[".TXT"], path=upper_file)  # should not raise

    def test_blocked_path_denies_even_when_allowed(self):
        """Tests that a blocked path overrides an allow-listed parent directory."""
        with self.assertRaises(ValueError) as ctx:
            self._check([str(self.tmp_root)], blocked_paths=[str(self.file)])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_blocked_extension_denies_even_when_allowed(self):
        """Tests that a blocked extension overrides an allow-listed extension."""
        with self.assertRaises(ValueError) as ctx:
            self._check([str(self.tmp_root)], allowed_exts=[".txt"], blocked_exts=[".txt"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_dotfile_matched_by_full_name(self):
        """Tests that a dotfile like '.env' is matched using the full filename as its extension."""
        env_file = self.tmp_root / ".env"
        env_file.write_text("x", encoding="utf-8")
        self._check([str(self.tmp_root)], allowed_exts=[".env"], path=env_file)  # should not raise

    def test_dotfile_blocked_by_full_name(self):
        """Tests that a dotfile '.env' is blocked when listed in blocked_file_extensions."""
        env_file = self.tmp_root / ".env"
        env_file.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._check([str(self.tmp_root)], allowed_exts=None, blocked_exts=[".env"], path=env_file)
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_extensionless_file_matched_by_name(self):
        """Tests that an extensionless file like 'Dockerfile' can be whitelisted by name."""
        dockerfile = self.tmp_root / "Dockerfile"
        dockerfile.write_text("x", encoding="utf-8")
        # Accept the bare name with or without a leading dot; normalization handles both.
        self._check([str(self.tmp_root)], allowed_exts=["Dockerfile"], path=dockerfile)  # should not raise

    def test_extensionless_file_blocked_by_name(self):
        """Tests that an extensionless file like 'Makefile' can be blocked by name."""
        makefile = self.tmp_root / "Makefile"
        makefile.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._check([str(self.tmp_root)], allowed_exts=None, blocked_exts=["Makefile"], path=makefile)
        self.assertIn("path_not_allowed", str(ctx.exception))
