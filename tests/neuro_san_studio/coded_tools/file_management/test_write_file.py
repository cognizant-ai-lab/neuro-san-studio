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

import asyncio
import os
import stat as stat_module
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.coded_tools.file_management.write_file import WRITE_FILE_HISTORY_KEY
from neuro_san_studio.coded_tools.file_management.write_file import WriteFile


# One consolidated TestCase per source module means many test methods by design.
class TestWriteFile(TestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for WriteFile.

    Covers async_invoke (integration-level, using a real temp directory) plus the
    _check_parent, _check_writable_target, _validate_content, and _write_atomically
    helpers.
    """

    def setUp(self):
        self.tool = WriteFile()
        self.sly_data: dict = {}
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---------------------------------------------------------------- helpers

    def _invoke(self, args: dict) -> dict:
        """Invoke the tool with allowed_paths defaulted to the temp root."""
        args.setdefault("allowed_paths", [str(self.tmp_root)])
        return asyncio.run(self.tool.async_invoke(args, self.sly_data))

    def _call_check_parent(self, path: Path, create_parents: bool) -> None:
        """Invoke _check_parent; returns None or raises."""
        self.tool._check_parent(path, create_parents)  # pylint: disable=protected-access

    def _call_check_writable_target(self, path: Path, overwrite: bool) -> None:
        """Invoke _check_writable_target; returns None or raises."""
        self.tool._check_writable_target(path, overwrite)  # pylint: disable=protected-access

    def _call_validate_content(self, args):
        """Invoke _validate_content with the given args dict and return the encoded bytes."""
        return self.tool._validate_content(args)  # pylint: disable=protected-access

    def _call_write_atomically(
        self, path: Path, content: bytes, overwrite: bool = False, create_parents: bool = False
    ) -> bool:
        """Invoke _write_atomically and return the 'created' flag."""
        return self.tool._write_atomically(  # pylint: disable=protected-access
            path, content, overwrite, create_parents
        )

    def _mode(self, path: Path) -> int:
        """Return the permission bits of a path."""
        return stat_module.S_IMODE(path.stat().st_mode)

    # ----------------------------------------------------------- async_invoke

    def test_async_invoke_writes_new_file_within_allowed_path(self):
        """Tests that a new file is written and the result carries the expected keys."""
        path = self.tmp_root / "out.txt"
        result = self._invoke({"file_path": str(path), "content": "hello"})
        self.assertEqual(path.read_text(encoding="utf-8"), "hello")
        self.assertEqual(result["path"], str(path))
        self.assertEqual(result["bytes_written"], 5)
        self.assertTrue(result["created"])
        self.assertIn("written_at", result)

    def test_async_invoke_overwrite_requires_opt_in(self):
        """Tests that writing over an existing file fails by default and works with overwrite=True."""
        path = self.tmp_root / "out.txt"
        path.write_text("old", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "new"})
        self.assertIn("file_already_exists", str(ctx.exception))
        self.assertEqual(path.read_text(encoding="utf-8"), "old")

        result = self._invoke({"file_path": str(path), "content": "new", "overwrite": True})
        self.assertEqual(path.read_text(encoding="utf-8"), "new")
        self.assertFalse(result["created"])

    def test_async_invoke_create_parents_requires_opt_in(self):
        """Tests that a missing parent fails by default and works with create_parents=True."""
        path = self.tmp_root / "a" / "b" / "out.txt"
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x"})
        self.assertIn("parent_not_found", str(ctx.exception))

        self._invoke({"file_path": str(path), "content": "x", "create_parents": True})
        self.assertEqual(path.read_text(encoding="utf-8"), "x")

    def test_async_invoke_omitted_allowed_paths_raises_invalid_input(self):
        """Tests that omitting the required allowed_paths raises invalid_input."""
        path = self.tmp_root / "out.txt"
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"file_path": str(path), "content": "x"}, self.sly_data))
        self.assertIn("invalid_input", str(ctx.exception))
        self.assertFalse(path.exists())

    def test_async_invoke_path_outside_allowed_root_denied(self):
        """Tests that a path outside any allowed_paths entry is denied before touching disk."""
        path = self.tmp_root / "out.txt"
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x", "allowed_paths": ["/some/other/root"]})
        self.assertIn("path_not_allowed", str(ctx.exception))
        self.assertFalse(path.exists())

    def test_async_invoke_access_denied_takes_priority_over_existing_file(self):
        """Tests that out-of-scope paths surface path_not_allowed, never file_already_exists."""
        path = self.tmp_root / "out.txt"
        path.write_text("secret", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x", "allowed_paths": ["/some/other/root"]})
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_extension_not_in_allowlist_denied(self):
        """Tests that an extension outside allowed_file_extensions is denied."""
        path = self.tmp_root / "out.exe"
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x", "allowed_file_extensions": [".txt"]})
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_blocked_extension_denied(self):
        """Tests that a blocked extension is denied even inside an allowed path."""
        path = self.tmp_root / ".env"
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x", "blocked_file_extensions": [".env"]})
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_directory_target_raises(self):
        """Tests that writing to an existing directory raises is_a_directory."""
        subdir = self.tmp_root / "subdir"
        subdir.mkdir()
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(subdir), "content": "x", "overwrite": True})
        self.assertIn("is_a_directory", str(ctx.exception))

    def test_async_invoke_non_bool_overwrite_raises_invalid_input(self):
        """Tests that a non-boolean overwrite value raises invalid_input."""
        path = self.tmp_root / "out.txt"
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x", "overwrite": "yes"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_async_invoke_write_history_recorded_and_deduped(self):
        """Tests that written paths land in sly_data write history, deduped and insertion-ordered."""
        path_a = self.tmp_root / "a.txt"
        path_b = self.tmp_root / "b.txt"
        self._invoke({"file_path": str(path_a), "content": "1"})
        self._invoke({"file_path": str(path_b), "content": "2"})
        self._invoke({"file_path": str(path_a), "content": "3", "overwrite": True})
        self.assertEqual(self.sly_data[WRITE_FILE_HISTORY_KEY], [str(path_a), str(path_b)])

    def test_async_invoke_none_sly_data_tolerated(self):
        """Tests that sly_data=None (seen from some middleware paths) does not fail a completed write."""
        path = self.tmp_root / "out.txt"
        result = asyncio.run(
            self.tool.async_invoke(
                {"file_path": str(path), "allowed_paths": [str(self.tmp_root)], "content": "x"}, None
            )
        )
        self.assertTrue(result["created"])
        self.assertEqual(path.read_text(encoding="utf-8"), "x")

    def test_async_invoke_blank_allowed_paths_entry_rejected(self):
        """Tests that a blank allowed_paths entry fails closed instead of granting CWD access."""
        path = self.tmp_root / "out.txt"
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x", "allowed_paths": [""]})
        self.assertIn("invalid_input", str(ctx.exception))
        self.assertFalse(path.exists())

    def test_async_invoke_parent_is_a_file_raises_parent_not_a_directory(self):
        """Tests that a parent occupied by a regular file surfaces parent_not_a_directory even with create_parents."""
        blocker = self.tmp_root / "blocker"
        blocker.write_text("x", encoding="utf-8")
        path = blocker / "out.txt"
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"file_path": str(path), "content": "x", "create_parents": True})
        self.assertIn("parent_not_a_directory", str(ctx.exception))

    def test_async_invoke_relative_path_resolved_within_allowed_root(self):
        """Tests that the reported path is the resolved absolute path."""
        path = self.tmp_root / "sub" / ".." / "rel.txt"
        result = self._invoke({"file_path": str(path), "content": "x"})
        self.assertEqual(result["path"], str(self.tmp_root / "rel.txt"))
        self.assertTrue((self.tmp_root / "rel.txt").exists())

    # ---------------------------------------------------------- _check_parent

    def test_check_parent_existing_parent_passes(self):
        """Tests that a file whose parent directory exists passes regardless of create_parents."""
        path = self.tmp_root / "file.txt"
        self._call_check_parent(path, False)  # should not raise
        self._call_check_parent(path, True)  # should not raise

    def test_check_parent_missing_parent_with_create_parents_passes(self):
        """Tests that a missing parent passes when create_parents is True."""
        path = self.tmp_root / "a" / "b" / "file.txt"
        self._call_check_parent(path, True)  # should not raise

    def test_check_parent_missing_parent_without_create_parents_raises(self):
        """Tests that a missing parent raises parent_not_found when create_parents is False."""
        path = self.tmp_root / "a" / "b" / "file.txt"
        with self.assertRaises(ValueError) as ctx:
            self._call_check_parent(path, False)
        self.assertIn("parent_not_found", str(ctx.exception))

    def test_check_parent_parent_is_a_file_raises_even_with_create_parents(self):
        """Tests that a parent path occupied by a regular file raises parent_not_a_directory regardless of flag."""
        blocker = self.tmp_root / "blocker"
        blocker.write_text("x", encoding="utf-8")
        path = blocker / "file.txt"
        for create_parents in (False, True):
            with self.assertRaises(ValueError) as ctx:
                self._call_check_parent(path, create_parents)
            self.assertIn("parent_not_a_directory", str(ctx.exception))

    # ------------------------------------------------- _check_writable_target

    def test_check_writable_target_new_path_passes(self):
        """Tests that a path that does not exist yet passes regardless of overwrite."""
        path = self.tmp_root / "new.txt"
        self._call_check_writable_target(path, False)  # should not raise
        self._call_check_writable_target(path, True)  # should not raise

    def test_check_writable_target_existing_file_with_overwrite_passes(self):
        """Tests that an existing file passes when overwrite is True."""
        path = self.tmp_root / "existing.txt"
        path.write_text("x", encoding="utf-8")
        self._call_check_writable_target(path, True)  # should not raise

    def test_check_writable_target_existing_file_without_overwrite_raises(self):
        """Tests that an existing file raises file_already_exists when overwrite is False."""
        path = self.tmp_root / "existing.txt"
        path.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._call_check_writable_target(path, False)
        self.assertIn("file_already_exists", str(ctx.exception))

    def test_check_writable_target_directory_raises_even_with_overwrite(self):
        """Tests that a directory target raises is_a_directory even when overwrite is True."""
        path = self.tmp_root / "subdir"
        path.mkdir()
        for overwrite in (False, True):
            with self.assertRaises(ValueError) as ctx:
                self._call_check_writable_target(path, overwrite)
            self.assertIn("is_a_directory", str(ctx.exception))

    # ------------------------------------------------------ _validate_content

    def test_validate_content_plain_string_encoded(self):
        """Tests that a plain string is returned UTF-8 encoded."""
        result = self._call_validate_content({"content": "hello"})
        self.assertEqual(result, b"hello")

    def test_validate_content_empty_string_allowed(self):
        """Tests that an empty string is valid content (creates an empty file)."""
        result = self._call_validate_content({"content": ""})
        self.assertEqual(result, b"")

    def test_validate_content_multibyte_characters_encoded(self):
        """Tests that multi-byte characters are measured in encoded bytes, not characters."""
        result = self._call_validate_content({"content": "héllo"})
        self.assertEqual(result, "héllo".encode("utf-8"))
        self.assertEqual(len(result), 6)

    def test_validate_content_missing_content_raises(self):
        """Tests that a missing 'content' key raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_content({})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_content_non_string_content_raises(self):
        """Tests that non-string content raises invalid_input."""
        for bad in [123, b"bytes", ["list"], {"dict": 1}, None]:
            with self.assertRaises(ValueError) as ctx:
                self._call_validate_content({"content": bad})
            self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_content_unencodable_content_raises_invalid_input(self):
        """Tests that content that is not UTF-8 encodable (unpaired surrogate) keeps the error taxonomy."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_content({"content": "bad \ud800 surrogate"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_content_content_at_limit_passes(self):
        """Tests that content exactly at the byte limit is allowed (boundary).

        The limit is patched down so the boundary is exercised without allocating
        a 10 MB string.
        """
        with patch("neuro_san_studio.coded_tools.file_management.write_file.MAX_WRITE_BYTES", 64):
            result = self._call_validate_content({"content": "x" * 64})
        self.assertEqual(len(result), 64)

    def test_validate_content_content_over_limit_raises(self):
        """Tests that content one byte over the limit raises content_too_large."""
        with patch("neuro_san_studio.coded_tools.file_management.write_file.MAX_WRITE_BYTES", 64):
            with self.assertRaises(ValueError) as ctx:
                self._call_validate_content({"content": "x" * 65})
        self.assertIn("content_too_large", str(ctx.exception))

    def test_validate_content_multibyte_content_over_limit_raises(self):
        """Tests that the limit is enforced on encoded bytes so multi-byte chars can't sneak past."""
        # é is 2 bytes in UTF-8, so 33 of them are over the 64-byte limit while
        # well under a 64-character count.
        with patch("neuro_san_studio.coded_tools.file_management.write_file.MAX_WRITE_BYTES", 64):
            with self.assertRaises(ValueError) as ctx:
                self._call_validate_content({"content": "é" * 33})
        self.assertIn("content_too_large", str(ctx.exception))

    # ----------------------------------------------------- _write_atomically

    def test_write_atomically_creates_new_file(self):
        """Tests that a new file is created with the expected content and created=True."""
        path = self.tmp_root / "new.txt"
        created = self._call_write_atomically(path, b"hello")
        self.assertTrue(created)
        self.assertEqual(path.read_bytes(), b"hello")

    def test_write_atomically_overwrites_existing_file(self):
        """Tests that an existing file is replaced when overwrite=True and created=False is reported."""
        path = self.tmp_root / "existing.txt"
        path.write_text("old content", encoding="utf-8")
        created = self._call_write_atomically(path, b"new", overwrite=True)
        self.assertFalse(created)
        self.assertEqual(path.read_bytes(), b"new")

    def test_write_atomically_no_clobber_when_file_appears_after_precheck(self):
        """Tests that overwrite=False is enforced atomically at install time, not just in the precheck."""
        # Simulate the race: the file comes into existence after _check_writable_target
        # passed (i.e. it exists by the time _write_atomically runs).
        path = self.tmp_root / "raced.txt"
        path.write_text("first writer", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._call_write_atomically(path, b"second writer", overwrite=False)
        self.assertIn("file_already_exists", str(ctx.exception))
        self.assertEqual(path.read_text(encoding="utf-8"), "first writer")
        # The losing writer's temp file must not be left behind.
        leftovers = [p.name for p in self.tmp_root.iterdir() if p.name != "raced.txt"]
        self.assertEqual(leftovers, [])

    def test_write_atomically_new_file_honors_umask(self):
        """Tests that a newly created file gets the umask-derived default mode, not mkstemp's 0600."""
        path = self.tmp_root / "modes.txt"
        old_umask = os.umask(0o022)
        try:
            self._call_write_atomically(path, b"x")
        finally:
            os.umask(old_umask)
        self.assertEqual(self._mode(path), 0o644)

    def test_write_atomically_overwrite_preserves_existing_mode(self):
        """Tests that overwriting keeps the target's existing permission bits."""
        path = self.tmp_root / "keep_mode.txt"
        path.write_text("old", encoding="utf-8")
        os.chmod(path, 0o640)
        self._call_write_atomically(path, b"new", overwrite=True)
        self.assertEqual(self._mode(path), 0o640)
        self.assertEqual(path.read_bytes(), b"new")

    def test_write_atomically_writes_empty_content(self):
        """Tests that empty content produces an empty file."""
        path = self.tmp_root / "empty.txt"
        created = self._call_write_atomically(path, b"")
        self.assertTrue(created)
        self.assertEqual(path.read_bytes(), b"")

    def test_write_atomically_creates_missing_parents_when_asked(self):
        """Tests that missing parent directories are created when create_parents=True."""
        path = self.tmp_root / "a" / "b" / "deep.txt"
        created = self._call_write_atomically(path, b"x", create_parents=True)
        self.assertTrue(created)
        self.assertEqual(path.read_bytes(), b"x")

    def test_write_atomically_no_temp_file_left_behind_on_success(self):
        """Tests that the temp file used for atomicity is gone after a successful write."""
        path = self.tmp_root / "clean.txt"
        self._call_write_atomically(path, b"x")
        leftovers = [p.name for p in self.tmp_root.iterdir() if p.name != "clean.txt"]
        self.assertEqual(leftovers, [])

    def test_write_atomically_swapped_symlink_parent_refused(self):
        """Tests that a parent directory swapped for a symlink after the access check is refused."""
        # The authorized (resolved) parent is tmp_root/sub, but by write time that
        # path is a symlink to elsewhere — resolve(strict=True) no longer matches.
        real_dir = self.tmp_root / "sub"
        real_dir.mkdir()
        elsewhere = self.tmp_root / "elsewhere"
        elsewhere.mkdir()
        authorized_path = real_dir / "out.txt"
        real_dir.rmdir()
        real_dir.symlink_to(elsewhere)
        with self.assertRaises(ValueError) as ctx:
            self._call_write_atomically(authorized_path, b"x")
        self.assertIn("path_not_allowed", str(ctx.exception))
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_write_atomically_no_hardlink_filesystem_fails_closed(self):
        """Tests that overwrite=False fails closed as write_error when hard links are unsupported."""
        path = self.tmp_root / "no_links.txt"
        with patch("neuro_san_studio.coded_tools.file_management.write_file.os.link") as mock_link:
            mock_link.side_effect = OSError("Operation not supported")
            with self.assertRaises(ValueError) as ctx:
                self._call_write_atomically(path, b"x", overwrite=False)
        self.assertIn("write_error", str(ctx.exception))
        self.assertFalse(path.exists())
        self.assertEqual(list(self.tmp_root.iterdir()), [])

    def test_write_atomically_failed_replace_raises_write_error_and_cleans_up(self):
        """Tests that a failure during os.replace surfaces as write_error and leaves no temp file."""
        path = self.tmp_root / "fail.txt"
        path.write_text("old", encoding="utf-8")
        with patch("neuro_san_studio.coded_tools.file_management.write_file.os.replace") as mock_replace:
            mock_replace.side_effect = OSError("disk full")
            with self.assertRaises(ValueError) as ctx:
                self._call_write_atomically(path, b"x", overwrite=True)
        self.assertIn("write_error", str(ctx.exception))
        self.assertEqual(path.read_text(encoding="utf-8"), "old")
        self.assertEqual([p.name for p in self.tmp_root.iterdir()], ["fail.txt"])

    def test_write_atomically_permission_error_raises_write_error(self):
        """Tests that a read-only target directory surfaces as write_error."""
        locked_dir = self.tmp_root / "locked"
        locked_dir.mkdir()
        os.chmod(locked_dir, 0o500)  # r-x only: temp file creation must fail
        try:
            path = locked_dir / "file.txt"
            with self.assertRaises(ValueError) as ctx:
                self._call_write_atomically(path, b"x")
            self.assertIn("write_error", str(ctx.exception))
        finally:
            os.chmod(locked_dir, 0o700)

    def test_write_atomically_mkdir_failure_raises_write_error(self):
        """Tests that a parent-creation failure surfaces as write_error."""
        locked_dir = self.tmp_root / "locked"
        locked_dir.mkdir()
        os.chmod(locked_dir, 0o500)  # r-x only: mkdir inside must fail
        try:
            path = locked_dir / "a" / "file.txt"
            with self.assertRaises(ValueError) as ctx:
                self._call_write_atomically(path, b"x", create_parents=True)
            self.assertIn("write_error", str(ctx.exception))
        finally:
            os.chmod(locked_dir, 0o700)
