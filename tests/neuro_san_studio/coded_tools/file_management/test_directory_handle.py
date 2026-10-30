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

import os
import stat as stat_module
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest import skipIf
from unittest import skipUnless
from unittest.mock import patch

from neuro_san_studio.coded_tools.file_management import directory_handle as directory_handle_module
from neuro_san_studio.coded_tools.file_management.directory_handle import DirectoryHandle


class TestDirectoryHandle(TestCase):
    """Unit tests for DirectoryHandle in descriptor mode and in the path-mode fallback."""

    def setUp(self) -> None:
        """Create a temp root with a file, a subdirectory, and a symlink to the file."""
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()
        (self.tmp_root / "a.txt").write_text("hello", encoding="utf-8")
        (self.tmp_root / "sub").mkdir()
        (self.tmp_root / "link").symlink_to(self.tmp_root / "a.txt")

    def tearDown(self) -> None:
        """Remove the temp root."""
        self.tmpdir.cleanup()

    def _assert_queries_work(self, handle: DirectoryHandle) -> None:
        """
        Assert the name and metadata queries agree with the fixture.

        :param handle: An open handle on the temp root.
        """
        self.assertTrue(handle.is_open)
        self.assertEqual(handle.directory, self.tmp_root)
        names: list[str] = []
        kinds: dict[str, tuple[bool, bool]] = {}
        for entry in handle.scan_entries():
            names.append(entry.name)
            kinds[entry.name] = (entry.is_dir(follow_symlinks=False), entry.is_symlink())
        self.assertEqual(sorted(names), ["a.txt", "link", "sub"])
        # d_type-derived hints: a real directory, a plain file, and a symlink (not a directory itself).
        self.assertEqual(kinds, {"a.txt": (False, False), "sub": (True, False), "link": (False, True)})
        self.assertTrue(stat_module.S_ISREG(handle.lstat("a.txt").st_mode))
        self.assertTrue(stat_module.S_ISDIR(handle.lstat("sub").st_mode))
        # lstat sees the link itself; stat follows it to the regular file.
        self.assertTrue(stat_module.S_ISLNK(handle.lstat("link").st_mode))
        self.assertTrue(stat_module.S_ISREG(handle.stat("link").st_mode))
        self.assertTrue(handle.is_searchable())
        with self.assertRaises(FileNotFoundError):
            handle.lstat("missing")

    @skipUnless(directory_handle_module.HAS_DESCRIPTOR_CALLS, "descriptor mode needs dir_fd support")
    def test_descriptor_mode_queries(self) -> None:
        """Tests that descriptor mode opens, answers queries relative to the descriptor, and closes."""
        with DirectoryHandle(self.tmp_root) as handle:
            self.assertTrue(handle.uses_descriptor)
            self._assert_queries_work(handle)
        self.assertFalse(handle.is_open)
        self.assertFalse(handle.uses_descriptor)

    @skipUnless(directory_handle_module.HAS_DESCRIPTOR_CALLS, "descriptor mode needs dir_fd support")
    def test_descriptor_mode_refuses_symlink_component(self) -> None:
        """Tests that a symlink anywhere in the path fails the open instead of being followed."""
        real = self.tmp_root / "real"
        (real / "inner").mkdir(parents=True)
        (self.tmp_root / "dirlink").symlink_to(real)
        with self.assertRaises(OSError):
            DirectoryHandle(self.tmp_root / "dirlink" / "inner").open()

    def test_path_mode_queries(self) -> None:
        """Tests that the path-mode fallback answers the same queries without a descriptor."""
        with patch.object(directory_handle_module, "HAS_DESCRIPTOR_CALLS", False):
            with DirectoryHandle(self.tmp_root) as handle:
                self.assertFalse(handle.uses_descriptor)
                self._assert_queries_work(handle)
            self.assertFalse(handle.is_open)

    def test_path_mode_refuses_symlink_component_and_missing_directory(self) -> None:
        """Tests that path mode re-verifies the path strictly at open time."""
        real = self.tmp_root / "real"
        (real / "inner").mkdir(parents=True)
        (self.tmp_root / "dirlink").symlink_to(real)
        with patch.object(directory_handle_module, "HAS_DESCRIPTOR_CALLS", False):
            with self.assertRaises(OSError):
                DirectoryHandle(self.tmp_root / "dirlink" / "inner").open()
            with self.assertRaises(FileNotFoundError):
                DirectoryHandle(self.tmp_root / "nope").open()

    @skipIf(os.name == "nt", "POSIX permission bits")
    def test_is_searchable_false_for_unsearchable_directory(self) -> None:
        """Tests that a readable-but-unsearchable directory reports unsearchable in both modes."""
        locked = self.tmp_root / "locked"
        locked.mkdir()
        os.chmod(locked, 0o444)
        try:
            with DirectoryHandle(locked) as handle:
                self.assertFalse(handle.is_searchable())
            with patch.object(directory_handle_module, "HAS_DESCRIPTOR_CALLS", False):
                with DirectoryHandle(locked) as handle:
                    self.assertFalse(handle.is_searchable())
        finally:
            os.chmod(locked, 0o700)

    def test_open_verifies_identity_when_expected_stat_given(self) -> None:
        """Tests that open() accepts the directory it was checked as and refuses a different inode, in both modes."""
        other = self.tmp_root / "other"
        other.mkdir()
        for descriptor_mode in [directory_handle_module.HAS_DESCRIPTOR_CALLS, False]:
            with self.subTest(descriptor_mode=descriptor_mode):
                with patch.object(directory_handle_module, "HAS_DESCRIPTOR_CALLS", descriptor_mode):
                    with DirectoryHandle(self.tmp_root, self.tmp_root.stat()) as handle:
                        self.assertTrue(handle.is_open)
                    stale = DirectoryHandle(self.tmp_root, other.stat())
                    with self.assertRaises(OSError):
                        stale.open()
                    self.assertFalse(stale.is_open)
                    self.assertFalse(stale.uses_descriptor)

    def test_close_is_idempotent(self) -> None:
        """Tests that closing twice (or without opening) is harmless."""
        handle = DirectoryHandle(self.tmp_root)
        handle.close()
        handle.open()
        handle.close()
        handle.close()
        self.assertFalse(handle.is_open)
