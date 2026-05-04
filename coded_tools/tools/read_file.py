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

from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from pathlib import Path
from typing import Any

import aiofiles
from neuro_san.interfaces.coded_tool import CodedTool

MAX_CHARS: int = 20_000


class ReadFile(CodedTool):
    """
    CodedTool implementation that reads a local file and returns its contents.

    By default the tool cannot read any file. Access must be explicitly granted
    via allow-lists in the tool arguments:
        - allowed_paths   : specific file paths or directories that may be read
        - allowed_extensions: file extensions (e.g. ".py", ".txt") that may be read

    Both allow-lists must permit the requested file for access to be granted; an empty
    list (or omitted allowed_paths) denies all access for that dimension.
    Block-lists are evaluated after allow-lists; a match in a block-list always denies access.

    Error types (raised as ValueError with the specified message prefix):
        invalid_input    – required parameter is missing, wrong type, or invalid value.
        path_not_allowed – the resolved path is outside every allowed_paths entry,
                           or its extension is not in allowed_extensions.
        path_not_found   – the file does not exist.
        is_a_directory   – the path points to a directory, not a file.
        read_error       – the file could not be read (permission error, I/O failure, etc.).
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "path"               (str, required): Absolute or relative path to the file.
                    "allowed_paths"      (list[str], required): One or more file paths or
                                         directory paths the tool is permitted to read from.
                                         A file is allowed when its resolved path equals or
                                         is a descendant of at least one entry. Must be
                                         non-empty; omitting it raises invalid_input.
                    "allowed_extensions" (list[str], optional): Whitelist of file extensions
                                         including the leading dot (e.g. [".py", ".txt"]).
                                         When omitted, no extension filtering is applied.
                                         An empty list denies all extensions.
                    "blocked_paths"      (list[str], optional): File paths or directories that
                                         are always denied, even if listed in allowed_paths.
                    "blocked_extensions" (list[str], optional): File extensions that are always
                                         denied, even if listed in allowed_extensions.
                    "start_line"         (int, optional): 1-based line number to start reading
                                         from. Defaults to 1.
                    "end_line"           (int, optional): 1-based line number to stop reading
                                         at (inclusive). Defaults to reading to end of file.
                    "max_content_chars"  (int, optional): Character cap on returned text.
                                         Defaults to MAX_CHARS. Must be a positive integer.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None

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
                            is_a_directory, read_error.
        """
        logger: Logger = getLogger(self.__class__.__name__)

        file_path: Path = self._validate_path(args)
        allowed_paths: list[str] = self._validate_allowed_paths(args)
        allowed_extensions: list[str] = self._validate_extension_list(args.get("allowed_extensions"), "allowed_extensions")
        blocked_paths: list[str] = self._validate_path_list(args.get("blocked_paths"), "blocked_paths")
        blocked_extensions: list[str] = self._validate_extension_list(args.get("blocked_extensions"), "blocked_extensions")
        start_line, end_line = self._validate_line_range(args)
        max_chars: int = self._validate_max_content_chars(args)

        self._check_path_allowed(file_path, allowed_paths, allowed_extensions, blocked_paths, blocked_extensions)

        logger.info("ReadFile: reading %s", file_path)

        try:
            async with aiofiles.open(file_path, encoding="utf-8", errors="replace") as f:
                raw_text: str = await f.read()
        except PermissionError as exc:
            raise ValueError(f"read_error: Permission denied reading '{file_path}'.") from exc
        except OSError as exc:
            raise ValueError(f"read_error: Could not read '{file_path}': {exc}") from exc

        lines: list[str] = raw_text.splitlines(keepends=True)
        total_lines: int = len(lines)

        actual_start: int = max(1, start_line)
        actual_end: int = min(total_lines, end_line if end_line is not None else total_lines)

        selected_lines: list[str] = lines[actual_start - 1 : actual_end]
        content: str = "".join(selected_lines)[:max_chars]

        read_at: str = datetime.now(timezone.utc).isoformat()

        logger.info(
            "ReadFile: returned %d characters from %s (lines %d-%d of %d)",
            len(content),
            file_path,
            actual_start,
            actual_end,
            total_lines,
        )

        return {
            "path": str(file_path),
            "content": content,
            "start_line": actual_start,
            "end_line": actual_end,
            "total_lines": total_lines,
            "read_at": read_at,
        }

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_path(self, args: dict[str, Any]) -> Path:
        """Resolve and validate the 'path' argument. Returns an absolute Path."""
        value: Any = args.get("path", "")
        if not isinstance(value, str):
            raise ValueError(f"invalid_input: 'path' must be a string, got {value!r}.")
        path_str: str = value.strip()
        if not path_str:
            raise ValueError("invalid_input: No 'path' provided.")

        try:
            resolved: Path = Path(path_str).resolve()
        except (ValueError, OSError) as exc:
            raise ValueError(f"invalid_input: Cannot resolve path '{path_str}': {exc}") from exc

        if not resolved.exists():
            raise ValueError(f"path_not_found: '{resolved}' does not exist.")
        if resolved.is_dir():
            raise ValueError(f"is_a_directory: '{resolved}' is a directory, not a file.")

        return resolved

    def _validate_allowed_paths(self, args: dict[str, Any]) -> list[str]:
        """Validate and return the 'allowed_paths' list. Returns empty list when missing (deny all)."""
        return self._validate_path_list(args.get("allowed_paths"), "allowed_paths")

    def _validate_path_list(self, value: Any, param_name: str) -> list[str]:
        """Coerce and validate a path list parameter. Accepts None, list[str], or a single str."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if not isinstance(value, list):
            raise ValueError(f"invalid_input: '{param_name}' must be a list of strings, got {value!r}.")
        for item in value:
            if not isinstance(item, str):
                raise ValueError(
                    f"invalid_input: '{param_name}' must be a list of strings, "
                    f"but contains non-string element {item!r}."
                )
        return value

    def _validate_extension_list(self, value: Any, param_name: str) -> list[str]:
        """Coerce and validate an extension list parameter. Accepts None, list[str], or a single str.

        None means the parameter was omitted (sentinel for "no filtering"); an empty list means deny all.
        """
        if value is None:
            return None  # type: ignore[return-value]  # None = omitted, distinct from []
        if isinstance(value, str):
            return [value]
        if not isinstance(value, list):
            raise ValueError(f"invalid_input: '{param_name}' must be a list of strings, got {value!r}.")
        for item in value:
            if not isinstance(item, str):
                raise ValueError(
                    f"invalid_input: '{param_name}' must be a list of strings, "
                    f"but contains non-string element {item!r}."
                )
        return value

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
                raise ValueError(
                    f"invalid_input: 'end_line' ({end}) must be >= 'start_line' ({start})."
                )

        return start, end

    def _validate_max_content_chars(self, args: dict[str, Any]) -> int:
        """Return a validated max_content_chars value, raising invalid_input on bad input."""
        value: Any = args.get("max_content_chars", MAX_CHARS)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"invalid_input: 'max_content_chars' must be a positive integer, got {value!r}.")
        return value

    # ------------------------------------------------------------------
    # Access-control helpers
    # ------------------------------------------------------------------

    def _check_path_allowed(
        self,
        file_path: Path,
        allowed_paths: list[str],
        allowed_extensions: list[str] | None,
        blocked_paths: list[str],
        blocked_extensions: list[str] | None,
    ) -> None:
        """Raise ValueError(path_not_allowed) when the file fails the allow/block rules.

        Evaluation order:
          1. allowed_extensions: None = omitted (skip check); [] = deny all; non-empty = whitelist.
          2. allowed_paths:      [] = deny all; non-empty = whitelist.
          3. blocked_extensions: None or [] = skip; non-empty = deny matching extensions.
          4. blocked_paths:      None or [] = skip; non-empty = deny matching paths/dirs.
        """
        # For dotfiles like ".env", pathlib returns suffix="" and stem=".env".
        # Use the full filename in that case so callers can match by e.g. ".env".
        suffix: str = file_path.suffix.lower() or file_path.name.lower()

        # 1. allowed_extensions
        if allowed_extensions is not None:
            if not allowed_extensions:
                raise ValueError(
                    f"path_not_allowed: Extension '{suffix}' is not allowed (allowed_extensions is empty)."
                )
            normalised_allowed_exts: list[str] = self._normalise_extensions(allowed_extensions)
            if suffix not in normalised_allowed_exts:
                raise ValueError(
                    f"path_not_allowed: Extension '{suffix}' is not in allowed_extensions {allowed_extensions}."
                )

        # 2. allowed_paths (empty list = deny all)
        if not allowed_paths:
            raise ValueError(
                f"path_not_allowed: '{file_path}' cannot be read (allowed_paths is empty)."
            )
        if not self._path_matches_any(file_path, allowed_paths):
            raise ValueError(
                f"path_not_allowed: '{file_path}' is not within any of the allowed_paths entries."
            )

        # 3. blocked_extensions
        if blocked_extensions:
            normalised_blocked_exts: list[str] = self._normalise_extensions(blocked_extensions)
            if suffix in normalised_blocked_exts:
                raise ValueError(
                    f"path_not_allowed: Extension '{suffix}' is in blocked_extensions {blocked_extensions}."
                )

        # 4. blocked_paths
        if blocked_paths and self._path_matches_any(file_path, blocked_paths):
            raise ValueError(
                f"path_not_allowed: '{file_path}' is blocked by blocked_paths."
            )

    def _normalise_extensions(self, extensions: list[str]) -> list[str]:
        """Return extensions normalised to lowercase with a leading dot."""
        return [e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions]

    def _path_matches_any(self, file_path: Path, path_list: list[str]) -> bool:
        """Return True if file_path equals or is a descendant of any entry in path_list."""
        for entry in path_list:
            try:
                candidate: Path = Path(entry).resolve()
            except (ValueError, OSError):
                continue
            if file_path == candidate:
                return True
            try:
                file_path.relative_to(candidate)
                return True
            except ValueError:
                pass
        return False
