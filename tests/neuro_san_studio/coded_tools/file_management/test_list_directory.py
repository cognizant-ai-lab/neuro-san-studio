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
import tempfile
from pathlib import Path
from unittest import TestCase

from neuro_san_studio.coded_tools.file_management.list_directory import LIST_DIRECTORY_HISTORY_KEY
from neuro_san_studio.coded_tools.file_management.list_directory import MAX_ENTRIES
from neuro_san_studio.coded_tools.file_management.list_directory import ListDirectory


# One consolidated TestCase per source module, matching the repo test convention.
# pylint: disable=too-many-public-methods
class TestListDirectory(TestCase):
    """Unit and integration tests for the ListDirectory coded tool."""

    def setUp(self):
        self.tool = ListDirectory()
        self.sly_data: dict = {}
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _make(self, name: str, content: str = "x") -> Path:
        """Create a file under the temp root and return its absolute path."""
        path = self.tmp_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _invoke(self, args: dict) -> dict:
        """Invoke the tool with allowed_paths defaulted to the temp root."""
        args.setdefault("directory_path", str(self.tmp_root))
        args.setdefault("allowed_paths", [str(self.tmp_root)])
        return asyncio.run(self.tool.async_invoke(args, self.sly_data))

    def _names(self, result: dict) -> list:
        """Return the entry names from a result."""
        return [entry["name"] for entry in result["entries"]]

    # ------------------------------------------------------------ async_invoke

    def test_async_invoke_lists_files_and_directories_sorted(self):
        """Tests that files and subdirectories are listed with type and size, sorted by name."""
        self._make("b.txt", "hello")
        (self.tmp_root / "a_dir").mkdir()
        result = self._invoke({})
        self.assertEqual(self._names(result), ["a_dir", "b.txt"])
        self.assertEqual(result["entries"][0]["type"], "directory")
        self.assertIsNone(result["entries"][0]["size_bytes"])
        self.assertEqual(result["entries"][1]["type"], "file")
        self.assertEqual(result["entries"][1]["size_bytes"], 5)
        self.assertEqual(result["path"], str(self.tmp_root))
        self.assertEqual(result["total_entries"], 2)
        self.assertFalse(result["truncated"])
        self.assertIn("listed_at", result)

    def test_async_invoke_omitted_allowed_paths_raises_invalid_input(self):
        """Tests that omitting the required allowed_paths raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"directory_path": str(self.tmp_root)}, self.sly_data))
        self.assertIn("invalid_input", str(ctx.exception))

    def test_async_invoke_directory_outside_allowed_root_denied(self):
        """Tests that a directory outside any allowed_paths entry is denied."""
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"allowed_paths": ["/some/other/root"]})
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_access_denied_takes_priority_over_missing_dir(self):
        """Tests that out-of-scope paths surface path_not_allowed, never path_not_found."""
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"directory_path": str(self.tmp_root / "nope"), "allowed_paths": ["/some/other/root"]})
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_missing_directory_raises_path_not_found(self):
        """Tests that a nonexistent directory inside the allowed root raises path_not_found."""
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"directory_path": str(self.tmp_root / "nope")})
        self.assertIn("path_not_found", str(ctx.exception))

    def test_async_invoke_file_target_raises_not_a_directory(self):
        """Tests that pointing the tool at a file raises not_a_directory."""
        path = self._make("a.txt")
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"directory_path": str(path)})
        self.assertIn("not_a_directory", str(ctx.exception))

    def test_async_invoke_directory_target_ignores_extension_rules(self):
        """Tests that extension allow-lists do not deny the directory target itself.

        A directory named 'data' must not be treated as extension '.data'; the
        extension rules only filter the file entries inside.
        """
        data_dir = self.tmp_root / "data"
        data_dir.mkdir()
        self._make("data/keep.txt")
        self._make("data/skip.log")
        result = self._invoke({"directory_path": str(data_dir), "allowed_file_extensions": [".txt"]})
        self.assertEqual(self._names(result), ["keep.txt"])

    def test_async_invoke_hidden_entries_require_opt_in(self):
        """Tests that dotfiles are omitted by default and included with include_hidden=True."""
        self._make("visible.txt")
        self._make(".hidden.txt")
        self.assertEqual(self._names(self._invoke({})), ["visible.txt"])
        self.assertEqual(self._names(self._invoke({"include_hidden": True})), [".hidden.txt", "visible.txt"])

    def test_async_invoke_blocked_subtree_omitted_silently(self):
        """Tests that entries under blocked_paths vanish from the listing without any error."""
        self._make("open.txt")
        secret_dir = self.tmp_root / "secret"
        secret_dir.mkdir()
        result = self._invoke({"blocked_paths": [str(secret_dir)]})
        self.assertEqual(self._names(result), ["open.txt"])
        self.assertFalse(result["truncated"])

    def test_async_invoke_blocked_extension_entries_omitted(self):
        """Tests that files with blocked extensions are omitted while directories remain."""
        self._make("keep.txt")
        self._make("drop.env")
        (self.tmp_root / "sub").mkdir()
        result = self._invoke({"blocked_file_extensions": [".env"]})
        self.assertEqual(self._names(result), ["keep.txt", "sub"])

    def test_async_invoke_symlink_out_of_scope_omitted(self):
        """Tests that a symlink resolving outside the allowed roots is hidden from the listing."""
        outside_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(outside_dir.cleanup)
        outside_file = Path(outside_dir.name) / "target.txt"
        outside_file.write_text("x", encoding="utf-8")
        (self.tmp_root / "escape.txt").symlink_to(outside_file)
        self._make("inside.txt")
        result = self._invoke({})
        self.assertEqual(self._names(result), ["inside.txt"])

    def test_async_invoke_symlink_in_scope_reported_as_symlink(self):
        """Tests that an in-scope symlink is reported with type 'symlink' and no size."""
        target = self._make("target.txt", "hello")
        (self.tmp_root / "link.txt").symlink_to(target)
        result = self._invoke({})
        by_name = {entry["name"]: entry for entry in result["entries"]}
        self.assertEqual(by_name["link.txt"]["type"], "symlink")
        self.assertIsNone(by_name["link.txt"]["size_bytes"])
        self.assertEqual(by_name["target.txt"]["type"], "file")

    def test_async_invoke_max_entries_truncates_deterministically(self):
        """Tests that max_entries caps the listing at the alphabetically-first entries and flags truncation."""
        for name in ["a.txt", "b.txt", "c.txt", "d.txt"]:
            self._make(name)
        result = self._invoke({"max_entries": 2})
        self.assertEqual(self._names(result), ["a.txt", "b.txt"])
        self.assertTrue(result["truncated"])
        self.assertEqual(result["total_entries"], 2)

    def test_async_invoke_truncated_false_when_cap_matches_count(self):
        """Tests that truncated stays False when the qualifying entries exactly fill the cap."""
        self._make("a.txt")
        self._make("b.txt")
        result = self._invoke({"max_entries": 2})
        self.assertEqual(self._names(result), ["a.txt", "b.txt"])
        self.assertFalse(result["truncated"])

    def test_async_invoke_empty_directory_returns_empty_listing(self):
        """Tests that an empty directory yields an empty, non-truncated listing."""
        result = self._invoke({})
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["total_entries"], 0)
        self.assertFalse(result["truncated"])

    def test_async_invoke_listing_history_recorded_and_deduped(self):
        """Tests that listed directories land in sly_data history, deduped and insertion-ordered."""
        sub = self.tmp_root / "sub"
        sub.mkdir()
        self._invoke({})
        self._invoke({"directory_path": str(sub)})
        self._invoke({})
        self.assertEqual(self.sly_data[LIST_DIRECTORY_HISTORY_KEY], [str(self.tmp_root), str(sub)])

    def test_async_invoke_none_sly_data_tolerated(self):
        """Tests that sly_data=None does not fail a successful listing."""
        self._make("a.txt")
        result = asyncio.run(
            self.tool.async_invoke({"directory_path": str(self.tmp_root), "allowed_paths": [str(self.tmp_root)]}, None)
        )
        self.assertEqual(self._names(result), ["a.txt"])

    def test_async_invoke_symlink_to_directory_survives_extension_allow_list(self):
        """Tests that a symlink to an in-scope directory is listed under an extension allow-list.

        Directories are exempt from the extension allow-list whether reached
        directly or via symlink — a symlinked subdir must not vanish as
        pseudo-extension '.docs' (common monorepo/venv layouts).
        """
        docs = self.tmp_root / "docs"
        docs.mkdir()
        (self.tmp_root / "docs_link").symlink_to(docs)
        self._make("plain.txt")
        result = self._invoke({"allowed_file_extensions": [".txt"]})
        self.assertEqual(self._names(result), ["docs", "docs_link", "plain.txt"])

    def test_async_invoke_blocked_extension_applies_to_symlink_display_name(self):
        """Tests that a symlink whose VISIBLE name matches a blocked extension is omitted.

        The operator blocked '.env' names; a symlink displayed as 'prod.env' must
        not appear just because its target resolves to an innocent '.txt' suffix.
        """
        target = self._make("readme.txt")
        (self.tmp_root / "prod.env").symlink_to(target)
        result = self._invoke({"blocked_file_extensions": [".env"]})
        self.assertEqual(self._names(result), ["readme.txt"])

    def test_async_invoke_blocked_extension_applies_to_directory_entries_and_target(self):
        """Tests that block rules always apply to directories: as listing entries and as the target."""
        (self.tmp_root / "prod.env").mkdir()
        self._make("keep.txt")
        result = self._invoke({"blocked_file_extensions": [".env"]})
        self.assertEqual(self._names(result), ["keep.txt"])
        with self.assertRaises(ValueError) as ctx:
            self._invoke({"directory_path": str(self.tmp_root / "prod.env"), "blocked_file_extensions": [".env"]})
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_special_files_omitted(self):
        """Tests that FIFOs are omitted rather than advertised as readable files.

        A FIFO listed as a 0-byte 'file' would pass read_file's prechecks and then
        hang its open() waiting for a writer.
        """
        os.mkfifo(self.tmp_root / "pipe")
        self._make("real.txt")
        result = self._invoke({})
        self.assertEqual(self._names(result), ["real.txt"])
        self.assertEqual(result["unreadable_entries"], 0)

    def test_async_invoke_unsearchable_directory_raises_list_error(self):
        """Tests that a readable-but-unsearchable directory fails instead of looking empty."""
        locked = self.tmp_root / "locked"
        locked.mkdir()
        (locked / "a.txt").write_text("x", encoding="utf-8")
        os.chmod(locked, 0o444)  # r-- : names enumerable, metadata unreadable
        try:
            with self.assertRaises(ValueError) as ctx:
                self._invoke({"directory_path": str(locked)})
            self.assertIn("list_error", str(ctx.exception))
        finally:
            os.chmod(locked, 0o700)

    def test_async_invoke_reports_unreadable_entries(self):
        """Tests that partially unreadable listings self-report their gaps."""
        self._make("fine.txt")
        result = self._invoke({})
        self.assertIn("unreadable_entries", result)
        self.assertEqual(result["unreadable_entries"], 0)

    def test_async_invoke_advertised_names_round_trip(self):
        """Tests that a name emitted by the listing (with trailing space) is directly usable as a target."""
        weird = self.tmp_root / "reports "
        weird.mkdir()
        (weird / "inner.txt").write_text("x", encoding="utf-8")
        listing = self._invoke({})
        self.assertIn("reports ", self._names(listing))
        inner = self._invoke({"directory_path": str(self.tmp_root / "reports ")})
        self.assertEqual(self._names(inner), ["inner.txt"])

    # ---------------------------------------------------- _validate_max_entries

    def test_validate_max_entries_defaults(self):
        """Tests that an omitted max_entries returns the default cap."""
        self.assertEqual(self.tool._validate_max_entries({}), 500)  # pylint: disable=protected-access

    def test_validate_max_entries_rejects_bad_values(self):
        """Tests that zero, negative, boolean, non-int, and over-hard-cap max_entries raise invalid_input.

        The hard MAX_ENTRIES ceiling exists because max_entries is LLM-settable:
        without it a single call against a huge allowed directory could build an
        unbounded response.
        """
        for bad in [0, -1, True, "10", 1.5, None, MAX_ENTRIES + 1, 10**12]:
            with self.assertRaises(ValueError) as ctx:
                self.tool._validate_max_entries({"max_entries": bad})  # pylint: disable=protected-access
            self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_max_entries_accepts_hard_cap(self):
        """Tests that exactly MAX_ENTRIES is accepted (boundary)."""
        result = self.tool._validate_max_entries({"max_entries": MAX_ENTRIES})  # pylint: disable=protected-access
        self.assertEqual(result, MAX_ENTRIES)

    # ------------------------------------------------- _check_directory_target

    def _check_target(self, path: Path, **extra_args) -> None:
        """Invoke _check_directory_target with allowed_paths defaulted to the temp root."""
        args = {"allowed_paths": [str(self.tmp_root)]}
        args.update(extra_args)
        self.tool._check_directory_target(args, path)  # pylint: disable=protected-access

    def test_check_directory_target_passes_for_directory(self):
        """Tests that an existing directory passes the existence check."""
        self._check_target(self.tmp_root)  # should not raise

    def test_check_directory_target_rejects_file_and_missing(self):
        """Tests the not_a_directory and path_not_found error types for unrestricted configs."""
        path = self._make("a.txt")
        with self.assertRaises(ValueError) as ctx:
            self._check_target(path)
        self.assertIn("not_a_directory", str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            self._check_target(self.tmp_root / "nope")
        self.assertIn("path_not_found", str(ctx.exception))

    def test_check_directory_target_no_existence_oracle_for_scoped_out_files(self):
        """Tests that extension-scoped-out targets get path_not_allowed whether they exist or not.

        Without this, comparing not_a_directory (exists) against path_not_found
        (doesn't) would let an agent probe the existence of files the extension
        rules hide from listings.
        """
        self._make("secret.key")
        for name in ["secret.key", "nonexistent.key"]:
            with self.assertRaises(ValueError) as ctx:
                self._check_target(self.tmp_root / name, allowed_file_extensions=[".txt"])
            self.assertIn("path_not_allowed", str(ctx.exception))

    def test_check_directory_target_permission_error_is_list_error(self):
        """Tests that an untraversable parent surfaces as list_error, not a false path_not_found."""
        locked = self.tmp_root / "locked"
        inner = locked / "inner"
        inner.mkdir(parents=True)
        os.chmod(locked, 0o000)
        try:
            with self.assertRaises(ValueError) as ctx:
                self._check_target(inner)
            self.assertIn("list_error", str(ctx.exception))
        finally:
            os.chmod(locked, 0o700)
