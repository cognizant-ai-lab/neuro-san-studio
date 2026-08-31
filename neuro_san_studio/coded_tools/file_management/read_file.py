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
from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from pathlib import Path
from typing import Any

from leaf_common.serialization.util.text_file_reader import TextFileReader
from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.file_management.path_access import PathAccess
from neuro_san_studio.coded_tools.file_management.sly_data_history import SlyDataHistory

MAX_CHARS: int = 20_000
MAX_FILE_BYTES: int = 10 * 1024 * 1024  # 10 MB hard cap on files read into memory
READ_FILE_HISTORY_KEY: str = "read_file_history"  # sly_data key for the list of read file paths


class ReadFile(CodedTool):
    """
    CodedTool implementation that reads a local file and returns its contents.

    By default the tool cannot read any file. Access must be explicitly granted
    via allow-lists in the tool arguments:
        - allowed_paths   : specific file paths or directories that may be read
        - allowed_file_extensions: file extensions (e.g. ".py", ".txt") that may be read

    allowed_paths is required and must be non-empty; allowed_file_extensions is
    optional (an empty list denies all extensions, omitting it skips extension filtering).
    Block-lists are evaluated after allow-lists; a match in a block-list always denies access.

    Error types (raised as ValueError with the specified message prefix):
        invalid_input    – required parameter is missing, wrong type, or invalid value.
        path_not_allowed – the resolved path is outside every allowed_paths entry,
                           or its extension is not in allowed_file_extensions.
        path_not_found   – the file does not exist.
        is_a_directory   – the path points to a directory, not a file.
        file_too_large   – the file exceeds MAX_FILE_BYTES (10 MB).
        read_error       – the file could not be read (permission error, I/O failure, etc.).
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any] | None) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "file_path"          (str, required): Absolute or relative path to the file.
                    "allowed_paths"      (list[str], required): One or more file paths or
                                         directory paths the tool is permitted to read from.
                                         A file is allowed when its resolved path equals or
                                         is a descendant of at least one entry. Must be
                                         non-empty; omitting it raises invalid_input.
                    "allowed_file_extensions" (list[str], optional): Whitelist of file extensions
                                         including the leading dot (e.g. [".py", ".txt"]).
                                         When omitted, no extension filtering is applied.
                                         An empty list denies all extensions.
                    "blocked_paths"      (list[str], optional): File paths or directories that
                                         are always denied, even if listed in allowed_paths.
                    "blocked_file_extensions" (list[str], optional): File extensions that are always
                                         denied, even if listed in allowed_file_extensions.
                    "start_line"         (int, optional): 1-based line number to start reading
                                         from. Defaults to 1.
                    "end_line"           (int, optional): 1-based line number to stop reading
                                         at (inclusive). Defaults to reading to end of file.
                    "max_content_chars"  (int, optional): Character cap on returned text.
                                         Defaults to MAX_CHARS. Must be a positive integer.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None. May be None.

                Side effect: on success, the resolved path is appended to the
                "read_file_history" list in sly_data (deduped, insertion-ordered),
                guarded by a "read_file_history_lock" entry. Best-effort
                bookkeeping — skipped when sly_data is None.

        :return:
            A dictionary with the following keys:
                "path"        (str): The resolved absolute path that was read.
                "content"     (str): The (possibly line-filtered) text content of the file.
                "start_line"  (int): First line returned (1-based).
                "end_line"    (int): Last line returned (1-based), or the actual last line
                              of the file when no end_line was specified.
                "total_lines" (int): Total number of lines in the file.
                "read_at"     (str): ISO-8601 UTC timestamp when the file was read.

        :raises ValueError: invalid_input, path_not_allowed, path_not_found,
                            is_a_directory, file_too_large, read_error.
        """
        file_path, start_line, end_line, max_chars = await self._async_precheck(args)
        content, actual_start, actual_end, total_lines = await self._async_read_file(
            file_path, start_line, end_line, max_chars
        )
        await self._async_cache_read(sly_data, file_path)

        return {
            "path": str(file_path),
            "content": content,
            "start_line": actual_start,
            "end_line": actual_end,
            "total_lines": total_lines,
            "read_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Async phases — async_invoke is just orchestration over these three.
    # ------------------------------------------------------------------

    async def _async_precheck(self, args: dict[str, Any]) -> tuple[Path, int, int | None, int]:
        """Run all pre-read validation and access checks. Returns (file_path, start_line, end_line, max_chars).

        Order matters: resolve → access → existence → size. Access checks run before
        the filesystem is touched so out-of-scope paths never surface path_not_found
        (which would leak filesystem layout).
        """
        file_path: Path = await PathAccess.async_resolve_path(args)
        await PathAccess.async_validate_and_check_access(args, file_path)
        await self._async_check_path_exists(file_path)
        await self._async_check_file_size(file_path)
        start_line, end_line = self._validate_line_range(args)
        max_chars: int = self._validate_max_content_chars(args)
        return file_path, start_line, end_line, max_chars

    async def _async_read_file(
        self, file_path: Path, start_line: int, end_line: int | None, max_chars: int
    ) -> tuple[str, int, int, int]:
        """Read the file's contents and slice to the requested line range / char cap.

        Returns (content, actual_start, actual_end, total_lines). Raises read_error
        on permission / I/O failures.
        """
        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("ReadFile: reading %s", file_path)
        try:
            raw_text: str = await TextFileReader.async_read_text_file(str(file_path))
        except PermissionError as exc:
            raise ValueError(f"read_error: Permission denied reading '{file_path}'.") from exc
        except OSError as exc:
            raise ValueError(f"read_error: Could not read '{file_path}': {exc}") from exc

        content, actual_start, actual_end, total_lines = self._slice_text(raw_text, start_line, end_line, max_chars)
        logger.info(
            "ReadFile: returned %d characters from %s (lines %d-%d of %d)",
            len(content),
            file_path,
            actual_start,
            actual_end,
            total_lines,
        )
        return content, actual_start, actual_end, total_lines

    async def _async_cache_read(self, sly_data: dict[str, Any] | None, file_path: Path) -> None:
        """Append the resolved file path to the session-scoped read history in sly_data.

        Only the resolved path is recorded (deduped, insertion-ordered). Contents are
        intentionally NOT cached:
          - Staleness risk: the same file could be edited (now or once a write_file tool
            exists) between reads, so a content cache could silently return outdated bytes.
          - Memory: with MAX_FILE_BYTES = 10 MB, caching contents would let a single
            conversation accumulate hundreds of megabytes in sly_data.
          - Cache-key complexity: each call can specify different start_line / end_line /
            max_content_chars, so the cache key would need to encode all of those — or
            cache the full file and re-slice — neither buys much over reading from disk.
          - Limited reuse: most agent file reads are one-shot; the content already lives
            in the chat context after the first read.
        """
        await SlyDataHistory.async_record(sly_data, "read_file_history_lock", READ_FILE_HISTORY_KEY, file_path)

    # ------------------------------------------------------------------
    # Async wrappers for pre-read checks
    #
    # Each wrapper offloads its sync counterpart to a worker thread so the
    # event loop is never blocked by Path resolution, stat(), or symlink-
    # following syscalls. The sync helpers stay independently testable.
    # ------------------------------------------------------------------

    async def _async_check_path_exists(self, file_path: Path) -> None:
        """Async wrapper around _check_path_exists."""
        await asyncio.to_thread(self._check_path_exists, file_path)

    async def _async_check_file_size(self, file_path: Path) -> None:
        """Async wrapper around _check_file_size."""
        await asyncio.to_thread(self._check_file_size, file_path)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _check_path_exists(self, file_path: Path) -> None:
        """Verify the resolved path exists and is a regular file (not a directory)."""
        if not file_path.exists():
            raise ValueError(f"path_not_found: '{file_path}' does not exist.")
        if file_path.is_dir():
            raise ValueError(f"is_a_directory: '{file_path}' is a directory, not a file.")

    def _check_file_size(self, file_path: Path) -> None:
        """Reject files larger than MAX_FILE_BYTES before they are read into memory."""
        try:
            size: int = file_path.stat().st_size
        except OSError as exc:
            raise ValueError(f"read_error: Could not stat '{file_path}': {exc}") from exc
        if size > MAX_FILE_BYTES:
            raise ValueError(
                f"file_too_large: '{file_path}' is {size} bytes; exceeds the {MAX_FILE_BYTES}-byte limit."
            )

    def _validate_line_range(self, args: dict[str, Any]) -> tuple[int, int | None]:
        """Return (start_line, end_line). end_line is None when not specified."""
        start: Any = args.get("start_line", 1)
        if not isinstance(start, int) or start < 1:
            raise ValueError(f"invalid_input: 'start_line' must be a positive integer, got {start!r}.")

        end: Any = args.get("end_line")
        if end is not None:
            if not isinstance(end, int) or end < 1:
                raise ValueError(f"invalid_input: 'end_line' must be a positive integer, got {end!r}.")
            if end < start:
                raise ValueError(f"invalid_input: 'end_line' ({end}) must be >= 'start_line' ({start}).")

        return start, end

    def _validate_max_content_chars(self, args: dict[str, Any]) -> int:
        """Return a validated max_content_chars value, raising invalid_input on bad input."""
        value: Any = args.get("max_content_chars", MAX_CHARS)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"invalid_input: 'max_content_chars' must be a positive integer, got {value!r}.")
        return value

    def _slice_text(
        self, raw_text: str, start_line: int, end_line: int | None, max_chars: int
    ) -> tuple[str, int, int, int]:
        """Slice raw_text to the requested line range and char cap.

        Returns (content, actual_start, actual_end, total_lines). When start_line is past
        EOF (or the file is empty), returns empty content with actual_start > actual_end so
        the reported range stays internally consistent. end_line=None reads to EOF.
        """
        lines: list[str] = raw_text.splitlines(keepends=True)
        total_lines: int = len(lines)
        if start_line > total_lines:
            # Requested range is past EOF — return empty content with consistent bounds.
            actual_start: int = total_lines + 1 if total_lines else 1
            actual_end: int = total_lines
        else:
            actual_start = max(1, start_line)
            actual_end = min(total_lines, end_line if end_line is not None else total_lines)
        content: str = "".join(lines[actual_start - 1 : actual_end])[:max_chars]
        return content, actual_start, actual_end, total_lines
