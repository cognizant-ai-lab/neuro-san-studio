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

from neuro_san_studio.coded_tools.file_management.read_file import ReadFile


class TestAsyncInvoke(TestCase):
    """Integration-level tests for ReadFile.async_invoke using a real temp directory."""

    def setUp(self):
        self.tool = ReadFile()
        self.sly_data: dict = {}
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write(self, name: str, content: str) -> Path:
        """Write a file under the temp root and return its absolute path."""
        path = self.tmp_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_reads_file_within_allowed_path(self):
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

    def test_omitted_allowed_paths_raises_invalid_input(self):
        """Tests that omitting the required allowed_paths raises invalid_input."""
        path = self._write("a.txt", "x")
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"file_path": str(path)}, self.sly_data))
        self.assertIn("invalid_input", str(ctx.exception))

    def test_path_outside_allowed_root_denied(self):
        """Tests that a file outside any allowed_paths entry is denied."""
        path = self._write("a.txt", "x")
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke({"file_path": str(path), "allowed_paths": ["/some/other/root"]}, self.sly_data)
            )
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_extension_not_in_allowlist_denied(self):
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

    def test_blocked_path_denies_even_when_allowed(self):
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

    def test_blocked_extension_denies_even_when_allowed(self):
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

    def test_line_range_slices_content(self):
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

    def test_max_content_chars_truncates(self):
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

    def test_missing_path_raises(self):
        """Tests that an empty 'file_path' raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.tool.async_invoke({"file_path": ""}, self.sly_data))
        self.assertIn("invalid_input", str(ctx.exception))

    def test_nonexistent_path_raises(self):
        """Tests that a missing path inside the allowed area raises path_not_found."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {"file_path": str(self.tmp_root / "nope.txt"), "allowed_paths": [str(self.tmp_root)]},
                    self.sly_data,
                )
            )
        self.assertIn("path_not_found", str(ctx.exception))

    def test_nonexistent_path_outside_allowed_returns_not_allowed(self):
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

    def test_directory_path_raises(self):
        """Tests that pointing 'file_path' at a directory raises is_a_directory."""
        with self.assertRaises(ValueError) as ctx:
            asyncio.run(
                self.tool.async_invoke(
                    {"file_path": str(self.tmp_root), "allowed_paths": [str(self.tmp_root)]}, self.sly_data
                )
            )
        self.assertIn("is_a_directory", str(ctx.exception))

    def test_dotfile_matched_by_full_name(self):
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

    def test_sly_data_history_records_read_paths(self):
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

    def test_sly_data_history_not_written_on_failure(self):
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
