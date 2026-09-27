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
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.coded_tools.file_management.read_file import MAX_CHARS
from neuro_san_studio.coded_tools.file_management.read_file import MAX_FILE_BYTES
from neuro_san_studio.coded_tools.file_management.read_file import ReadFile


# One consolidated TestCase per source module means many test methods by design.
class TestReadFile(TestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for ReadFile.

    Covers async_invoke (integration-level, using a real temp directory) plus the
    _check_file_size, _check_path_exists, _slice_text, _validate_line_range, and
    _validate_max_content_chars helpers.
    """

    def setUp(self):
        self.tool = ReadFile()
        self.sly_data: dict = {}
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---------------------------------------------------------------- helpers

    def _write(self, name: str, content: str) -> Path:
        """Write a file under the temp root and return its absolute path."""
        path = self.tmp_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _call_check_file_size(self, path: Path) -> None:
        """Invoke _check_file_size; returns None or raises."""
        self.tool._check_file_size(path)  # pylint: disable=protected-access

    def _call_check_path_exists(self, path: Path) -> None:
        """Invoke _check_path_exists; returns None or raises."""
        self.tool._check_path_exists(path)  # pylint: disable=protected-access

    def _call_slice_text(self, raw_text, start_line=1, end_line=None, max_chars=10_000):
        """Invoke _slice_text with the given args and return the result tuple."""
        return self.tool._slice_text(raw_text, start_line, end_line, max_chars)  # pylint: disable=protected-access

    def _call_validate_line_range(self, args):
        """Invoke _validate_line_range with the given args dict and return the result."""
        return self.tool._validate_line_range(args)  # pylint: disable=protected-access

    def _call_validate_max_content_chars(self, args):
        """Invoke _validate_max_content_chars with the given args dict and return the result."""
        return self.tool._validate_max_content_chars(args)  # pylint: disable=protected-access

    # ----------------------------------------------------------- async_invoke

    def test_async_invoke_reads_file_within_allowed_path(self):
        """Tests that a file inside an allowed directory is read and returns expected keys."""
        path = self._write("a.txt", "hello\nworld\n")
        result = asyncio.run(
            self.tool.async_invoke(
                {
                    "file_path": str(path),
                    "allowed_paths": [str(self.tmp_root)],
                    "allowed_file_extensions": [".txt"],
                },
                self.sly_data,
            )
        )
        self.assertEqual(result["content"], "hello\nworld\n")
        self.assertEqual(result["total_lines"], 2)
        self.assertEqual(result["start_line"], 1)
        self.assertEqual(result["end_line"], 2)
        self.assertIn("read_at", result)
        self.assertEqual(result["path"], str(path.resolve()))

    def test_async_invoke_none_sly_data_tolerated(self):
        """Tests that sly_data=None does not fail a successful read (history is best-effort bookkeeping)."""
        path = self._write("a.txt", "hello\n")
        result = asyncio.run(
            self.tool.async_invoke({"file_path": str(path), "allowed_paths": [str(self.tmp_root)]}, None)
        )
        self.assertEqual(result["content"], "hello\n")

    def test_async_invoke_omitted_allowed_paths_raises_invalid_input(self):
        """Tests that omitting the required allowed_paths raises invalid_input."""
        path = self._write("a.txt", "x")
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"file_path": str(path)}, self.sly_data))
        self.assertIn("invalid_input", str(ctx.exception))

    def test_async_invoke_path_outside_allowed_root_denied(self):
        """Tests that a file outside any allowed_paths entry is denied."""
        path = self._write("a.txt", "x")
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke({"file_path": str(path), "allowed_paths": ["/some/other/root"]}, self.sly_data)
            )
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_extension_not_in_allowlist_denied(self):
        """Tests that a file whose extension is not in allowed_file_extensions is denied."""
        path = self._write("a.hocon", "x")
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {
                        "file_path": str(path),
                        "allowed_paths": [str(self.tmp_root)],
                        "allowed_file_extensions": [".txt"],
                    },
                    self.sly_data,
                )
            )
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_blocked_path_denies_even_when_allowed(self):
        """Tests that a blocked path takes precedence over an allow-listed parent directory."""
        path = self._write("secret.txt", "x")
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {
                        "file_path": str(path),
                        "allowed_paths": [str(self.tmp_root)],
                        "blocked_paths": [str(path)],
                    },
                    self.sly_data,
                )
            )
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_blocked_extension_denies_even_when_allowed(self):
        """Tests that a blocked extension takes precedence over an allow-listed extension."""
        path = self._write("a.txt", "x")
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {
                        "file_path": str(path),
                        "allowed_paths": [str(self.tmp_root)],
                        "allowed_file_extensions": [".txt"],
                        "blocked_file_extensions": [".txt"],
                    },
                    self.sly_data,
                )
            )
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_async_invoke_line_range_slices_content(self):
        """Tests that start_line/end_line return only the requested slice of lines."""
        path = self._write("a.txt", "line1\nline2\nline3\nline4\n")
        result = asyncio.run(
            self.tool.async_invoke(
                {
                    "file_path": str(path),
                    "allowed_paths": [str(self.tmp_root)],
                    "allowed_file_extensions": [".txt"],
                    "start_line": 2,
                    "end_line": 3,
                },
                self.sly_data,
            )
        )
        self.assertEqual(result["content"], "line2\nline3\n")
        self.assertEqual(result["start_line"], 2)
        self.assertEqual(result["end_line"], 3)
        self.assertEqual(result["total_lines"], 4)

    def test_async_invoke_max_content_chars_truncates(self):
        """Tests that returned content is truncated to max_content_chars."""
        path = self._write("a.txt", "x" * 500)
        result = asyncio.run(
            self.tool.async_invoke(
                {
                    "file_path": str(path),
                    "allowed_paths": [str(self.tmp_root)],
                    "allowed_file_extensions": [".txt"],
                    "max_content_chars": 50,
                },
                self.sly_data,
            )
        )
        self.assertEqual(len(result["content"]), 50)

    def test_async_invoke_missing_path_raises(self):
        """Tests that an empty 'file_path' raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"file_path": ""}, self.sly_data))
        self.assertIn("invalid_input", str(ctx.exception))

    def test_async_invoke_nonexistent_path_raises(self):
        """Tests that a missing path inside the allowed area raises path_not_found."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {"file_path": str(self.tmp_root / "nope.txt"), "allowed_paths": [str(self.tmp_root)]},
                    self.sly_data,
                )
            )
        self.assertIn("path_not_found", str(ctx.exception))

    def test_async_invoke_nonexistent_path_outside_allowed_returns_not_allowed(self):
        """Tests that a missing path *outside* the allowed area surfaces path_not_allowed.

        This prevents callers from probing filesystem existence outside their permitted
        scope by distinguishing path_not_found from path_not_allowed.
        """
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {"file_path": "/definitely/not/here.txt", "allowed_paths": [str(self.tmp_root)]},
                    self.sly_data,
                )
            )
        self.assertIn("path_not_allowed", str(ctx.exception))
        self.assertNotIn("path_not_found", str(ctx.exception))

    def test_async_invoke_directory_path_raises(self):
        """Tests that pointing 'file_path' at a directory raises is_a_directory."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {"file_path": str(self.tmp_root), "allowed_paths": [str(self.tmp_root)]}, self.sly_data
                )
            )
        self.assertIn("is_a_directory", str(ctx.exception))

    def test_async_invoke_dotfile_matched_by_full_name(self):
        """Tests that a dotfile like '.env' can be matched by its full name in allowed_file_extensions."""
        path = self._write(".env", "SECRET=1")
        result = asyncio.run(
            self.tool.async_invoke(
                {
                    "file_path": str(path),
                    "allowed_paths": [str(self.tmp_root)],
                    "allowed_file_extensions": [".env"],
                },
                self.sly_data,
            )
        )
        self.assertEqual(result["content"], "SECRET=1")

    def test_async_invoke_sly_data_history_records_read_paths(self):
        """Tests that each successful read appends the resolved path to sly_data, deduped."""
        path_a = self._write("a.txt", "alpha")
        path_b = self._write("b.txt", "beta")
        args = {"allowed_paths": [str(self.tmp_root)], "allowed_file_extensions": [".txt"]}

        # First read of A.
        asyncio.run(self.tool.async_invoke({"file_path": str(path_a), **args}, self.sly_data))
        # Second read of A — should NOT duplicate the entry.
        asyncio.run(self.tool.async_invoke({"file_path": str(path_a), **args}, self.sly_data))
        # Read B — should append a new entry.
        asyncio.run(self.tool.async_invoke({"file_path": str(path_b), **args}, self.sly_data))

        history = self.sly_data.get("read_file_history")
        self.assertEqual(history, [str(path_a.resolve()), str(path_b.resolve())])

    def test_async_invoke_sly_data_history_not_written_on_failure(self):
        """Tests that a failed read does not pollute the history list."""
        path = self._write("a.hocon", "x")
        with self.assertRaises(ValueError):
            asyncio.run(
                self.tool.async_invoke(
                    {
                        "file_path": str(path),
                        "allowed_paths": [str(self.tmp_root)],
                        "allowed_file_extensions": [".txt"],
                    },
                    self.sly_data,
                )
            )
        self.assertNotIn("read_file_history", self.sly_data)

    # ------------------------------------------------------- _check_file_size

    def test_check_file_size_small_file_passes(self):
        """Tests that a small file passes the size check."""
        path = self.tmp_root / "small.txt"
        path.write_text("x" * 100, encoding="utf-8")
        self._call_check_file_size(path)  # should not raise

    def test_check_file_size_file_at_limit_passes(self):
        """Tests that a file exactly at the limit is allowed (boundary)."""
        path = self.tmp_root / "at_limit.txt"
        # Don't actually create a 10MB file — mock stat() instead.
        path.write_text("x", encoding="utf-8")
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = MAX_FILE_BYTES
            self._call_check_file_size(path)  # should not raise

    def test_check_file_size_file_over_limit_raises(self):
        """Tests that a file one byte over the limit raises file_too_large."""
        path = self.tmp_root / "over.txt"
        path.write_text("x", encoding="utf-8")
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value.st_size = MAX_FILE_BYTES + 1
            with self.assertRaises(ValueError) as ctx:
                self._call_check_file_size(path)
        self.assertIn("file_too_large", str(ctx.exception))

    def test_check_file_size_stat_error_surfaces_as_read_error(self):
        """Tests that an OSError from stat() is wrapped as read_error."""
        path = self.tmp_root / "nope.txt"
        with patch.object(Path, "stat", side_effect=OSError("permission denied")):
            with self.assertRaises(ValueError) as ctx:
                self._call_check_file_size(path)
        self.assertIn("read_error", str(ctx.exception))

    # ----------------------------------------------------- _check_path_exists

    def test_check_path_exists_existing_file_passes(self):
        """Tests that an existing regular file passes the check."""
        path = self.tmp_root / "a.txt"
        path.write_text("x", encoding="utf-8")
        self._call_check_path_exists(path)  # should not raise

    def test_check_path_exists_nonexistent_path_raises(self):
        """Tests that a missing path raises path_not_found."""
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_exists(self.tmp_root / "missing.txt")
        self.assertIn("path_not_found", str(ctx.exception))

    def test_check_path_exists_directory_raises(self):
        """Tests that a directory raises is_a_directory."""
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_exists(self.tmp_root)
        self.assertIn("is_a_directory", str(ctx.exception))

    # ------------------------------------------------------------ _slice_text

    def test_slice_text_full_text_returned_with_defaults(self):
        """Tests that start_line=1 and end_line=None return the full file."""
        text = "a\nb\nc\n"
        content, start, end, total = self._call_slice_text(text)
        self.assertEqual(content, text)
        self.assertEqual((start, end, total), (1, 3, 3))

    def test_slice_text_line_range_slice(self):
        """Tests that an explicit line range returns only those lines."""
        text = "a\nb\nc\nd\n"
        content, start, end, total = self._call_slice_text(text, start_line=2, end_line=3)
        self.assertEqual(content, "b\nc\n")
        self.assertEqual((start, end, total), (2, 3, 4))

    def test_slice_text_end_line_clamped_to_total(self):
        """Tests that end_line beyond the file length is clamped to total_lines."""
        text = "a\nb\n"
        content, start, end, total = self._call_slice_text(text, start_line=1, end_line=99)
        self.assertEqual(content, text)
        self.assertEqual((start, end, total), (1, 2, 2))

    def test_slice_text_max_chars_truncates(self):
        """Tests that the content is truncated to max_chars."""
        text = "abcdefghij\n"
        content, _, _, _ = self._call_slice_text(text, max_chars=5)
        self.assertEqual(content, "abcde")

    def test_slice_text_empty_text(self):
        """Tests that an empty input returns empty content and zero lines."""
        content, start, end, total = self._call_slice_text("")
        self.assertEqual(content, "")
        self.assertEqual(total, 0)
        self.assertEqual(start, 1)
        self.assertEqual(end, 0)

    def test_slice_text_single_line_no_trailing_newline(self):
        """Tests that a one-line file without a trailing newline is handled correctly."""
        content, start, end, total = self._call_slice_text("hello")
        self.assertEqual(content, "hello")
        self.assertEqual((start, end, total), (1, 1, 1))

    def test_slice_text_start_line_past_eof_returns_empty(self):
        """Tests that start_line beyond total_lines returns empty content with consistent bounds.

        Bounds satisfy actual_start > actual_end (a well-formed empty range), and we never
        silently return content from a line the caller didn't ask for.
        """
        content, start, end, total = self._call_slice_text("a\nb\n", start_line=999)
        self.assertEqual(content, "")
        self.assertEqual(total, 2)
        self.assertGreater(start, end)

    # -------------------------------------------------- _validate_line_range

    def test_validate_line_range_defaults_to_start_1_and_end_none(self):
        """Tests that omitting both keys returns (1, None)."""
        self.assertEqual(self._call_validate_line_range({}), (1, None))

    def test_validate_line_range_explicit_values_returned(self):
        """Tests that explicit valid start_line and end_line are returned as-is."""
        self.assertEqual(self._call_validate_line_range({"start_line": 2, "end_line": 5}), (2, 5))

    def test_validate_line_range_start_equal_to_end_accepted(self):
        """Tests that start_line == end_line is accepted (single-line read)."""
        self.assertEqual(self._call_validate_line_range({"start_line": 3, "end_line": 3}), (3, 3))

    def test_validate_line_range_zero_start_raises(self):
        """Tests that start_line=0 raises invalid_input (must be positive)."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_line_range({"start_line": 0})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_line_range_negative_start_raises(self):
        """Tests that a negative start_line raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_line_range({"start_line": -1})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_line_range_string_start_raises(self):
        """Tests that a non-integer start_line raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_line_range({"start_line": "1"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_line_range_zero_end_raises(self):
        """Tests that end_line=0 raises invalid_input (must be positive)."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_line_range({"end_line": 0})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_line_range_end_less_than_start_raises(self):
        """Tests that end_line < start_line raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_line_range({"start_line": 5, "end_line": 3})
        self.assertIn("invalid_input", str(ctx.exception))

    # ------------------------------------------- _validate_max_content_chars

    def test_validate_max_content_chars_default_value_used_when_absent(self):
        """Tests that the default MAX_CHARS value is returned when max_content_chars is absent."""
        self.assertEqual(self._call_validate_max_content_chars({}), MAX_CHARS)

    def test_validate_max_content_chars_valid_positive_int(self):
        """Tests that a valid positive integer is accepted and returned as-is."""
        self.assertEqual(self._call_validate_max_content_chars({"max_content_chars": 500}), 500)

    def test_validate_max_content_chars_zero_raises(self):
        """Tests that zero raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_max_content_chars({"max_content_chars": 0})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_max_content_chars_negative_raises(self):
        """Tests that a negative value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_max_content_chars({"max_content_chars": -1})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_max_content_chars_string_raises(self):
        """Tests that a string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_max_content_chars({"max_content_chars": "1000"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_max_content_chars_float_raises(self):
        """Tests that a float value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_max_content_chars({"max_content_chars": 1000.0})
        self.assertIn("invalid_input", str(ctx.exception))
