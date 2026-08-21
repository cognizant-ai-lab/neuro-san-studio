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

from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.file_management.path_access import PathAccess
from neuro_san_studio.coded_tools.file_management.sly_data_history import SlyDataHistory

DEFAULT_MAX_ENTRIES: int = 500
LIST_DIRECTORY_HISTORY_KEY: str = "list_directory_history"  # sly_data key for the list of listed directories


class ListDirectory(CodedTool):
    """
    CodedTool implementation that lists the entries of a local directory.

    By default the tool cannot list any directory. Access must be explicitly
    granted via allow-lists in the tool arguments:
        - allowed_paths   : specific directories (or files) that may be accessed
        - allowed_file_extensions: file extensions the listing may include

    allowed_paths is required and must be non-empty. The directory target itself
    is checked against the path rules only (directories have no meaningful
    extension); the extension allow/block rules are applied when filtering the
    file entries inside it. Block-lists are evaluated after allow-lists; a match
    in a block-list always denies access.

    Entries that fail the allow/block rules are silently omitted from the
    listing rather than reported, so the listing never leaks the existence of
    files the operator has scoped out (e.g. a blocked_paths subtree). Symlinks
    are never followed for metadata and are filtered on their resolved target,
    so a link pointing outside the allowed roots is omitted as well.

    Error types (raised as ValueError with the specified message prefix):
        invalid_input    – required parameter is missing, wrong type, or invalid value.
        path_not_allowed – the resolved directory is outside every allowed_paths
                           entry or matches blocked_paths.
        path_not_found   – the directory does not exist.
        not_a_directory  – the path points to a file, not a directory.
        list_error       – the directory could not be read (permission error, I/O failure, etc.).
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any] | None) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "directory_path"     (str, required): Absolute or relative path to the
                                         directory to list.
                    "allowed_paths"      (list[str], required): One or more file paths or
                                         directory paths the tool is permitted to access.
                                         A path is allowed when its resolved form equals or
                                         is a descendant of at least one entry. Must be
                                         non-empty; omitting it raises invalid_input.
                    "allowed_file_extensions" (list[str], optional): Whitelist of file extensions
                                         including the leading dot (e.g. [".py", ".txt"]).
                                         Applied to file entries in the listing; directories
                                         are not extension-filtered. When omitted, no
                                         extension filtering is applied. An empty list
                                         omits all file entries.
                    "blocked_paths"      (list[str], optional): File paths or directories that
                                         are always denied, even if listed in allowed_paths.
                    "blocked_file_extensions" (list[str], optional): File extensions whose
                                         entries are always omitted from the listing.
                    "include_hidden"     (bool, optional): When True, dotfiles and dot-
                                         directories are included. Defaults to False.
                    "max_entries"        (int, optional): Cap on the number of returned
                                         entries. Defaults to DEFAULT_MAX_ENTRIES (500).
                                         Must be a positive integer.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None. May be None.

                Side effect: on success, the resolved directory path is appended to
                the "list_directory_history" list in sly_data (deduped,
                insertion-ordered), guarded by a "list_directory_history_lock"
                entry. Best-effort bookkeeping — skipped when sly_data is None.

        :return:
            A dictionary with the following keys:
                "path"          (str): The resolved absolute directory that was listed.
                "entries"       (list[dict]): One dict per entry, sorted by name:
                                "name" (str), "type" ("file" | "directory" | "symlink"),
                                "size_bytes" (int for files, None otherwise).
                "total_entries" (int): Number of entries returned.
                "truncated"     (bool): True when more qualifying entries existed than
                                max_entries.
                "listed_at"     (str): ISO-8601 UTC timestamp when the listing was taken.

        :raises ValueError: invalid_input, path_not_allowed, path_not_found,
                            not_a_directory, list_error.
        """
        directory, include_hidden, max_entries = await self._async_precheck(args)
        entries, truncated = await self._async_list_entries(args, directory, include_hidden, max_entries)
        await self._async_cache_listing(sly_data, directory)

        return {
            "path": str(directory),
            "entries": entries,
            "total_entries": len(entries),
            "truncated": truncated,
            "listed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Async phases — async_invoke is just orchestration over these three.
    # ------------------------------------------------------------------

    async def _async_precheck(self, args: dict[str, Any]) -> tuple[Path, bool, int]:
        """Run all pre-listing validation and access checks.

        Returns (directory, include_hidden, max_entries).

        Order matters: resolve → access → existence. Access checks run before the
        filesystem is touched so out-of-scope paths never surface path_not_found
        (which would leak filesystem layout). Extension rules are not applied to
        the directory target itself — only to the file entries inside it.
        """
        directory: Path = await PathAccess.async_resolve_path(args, "directory_path")
        await PathAccess.async_validate_and_check_access(args, directory, apply_extension_rules=False)
        include_hidden: bool = PathAccess.validate_bool(args, "include_hidden", False)
        max_entries: int = self._validate_max_entries(args)
        await self._async_check_directory_exists(directory)
        return directory, include_hidden, max_entries

    async def _async_list_entries(
        self, args: dict[str, Any], directory: Path, include_hidden: bool, max_entries: int
    ) -> tuple[list[dict[str, Any]], bool]:
        """Scan the directory in a worker thread and return (entries, truncated)."""
        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("ListDirectory: listing %s", directory)
        entries, truncated = await asyncio.to_thread(self._list_entries, args, directory, include_hidden, max_entries)
        logger.info("ListDirectory: returned %d entries from %s (truncated=%s)", len(entries), directory, truncated)
        return entries, truncated

    async def _async_cache_listing(self, sly_data: dict[str, Any] | None, directory: Path) -> None:
        """Append the resolved directory to the session-scoped listing history in sly_data."""
        await SlyDataHistory.async_record(
            sly_data, "list_directory_history_lock", LIST_DIRECTORY_HISTORY_KEY, directory
        )

    # ------------------------------------------------------------------
    # Async wrappers for pre-listing checks
    # ------------------------------------------------------------------

    async def _async_check_directory_exists(self, directory: Path) -> None:
        """Async wrapper around _check_directory_exists."""
        await asyncio.to_thread(self._check_directory_exists, directory)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _check_directory_exists(self, directory: Path) -> None:
        """Verify the resolved path exists and is a directory."""
        if not directory.exists():
            raise ValueError(f"path_not_found: '{directory}' does not exist.")
        if not directory.is_dir():
            raise ValueError(f"not_a_directory: '{directory}' is not a directory.")

    def _validate_max_entries(self, args: dict[str, Any]) -> int:
        """Return a validated max_entries value, raising invalid_input on bad input."""
        value: Any = args.get("max_entries", DEFAULT_MAX_ENTRIES)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"invalid_input: 'max_entries' must be a positive integer, got {value!r}.")
        return value

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    def _list_entries(
        self, args: dict[str, Any], directory: Path, include_hidden: bool, max_entries: int
    ) -> tuple[list[dict[str, Any]], bool]:
        """Enumerate, filter, and describe the directory's entries.

        Names are sorted first so the output (and which entries fall past the
        max_entries cap) is deterministic. Entries the access rules exclude are
        omitted silently — surfacing them (even as an error) would leak the
        existence of paths the operator scoped out.

        Returns (entries, truncated). Raises list_error on permission / I/O failures.
        """
        try:
            names: list[str] = sorted(entry.name for entry in directory.iterdir())
        except PermissionError as exc:
            raise ValueError(f"list_error: Permission denied listing '{directory}'.") from exc
        except OSError as exc:
            raise ValueError(f"list_error: Could not list '{directory}': {exc}") from exc

        entries: list[dict[str, Any]] = []
        truncated: bool = False
        for name in names:
            if not include_hidden and name.startswith("."):
                continue
            described: dict[str, Any] | None = self._describe_entry(args, directory / name)
            if described is None:
                continue
            if len(entries) >= max_entries:
                # A qualifying entry exists past the cap — report the truncation
                # instead of silently presenting the listing as complete.
                truncated = True
                break
            entries.append(described)
        return entries, truncated

    def _describe_entry(self, args: dict[str, Any], entry_path: Path) -> dict[str, Any] | None:
        """Classify one entry and check it against the access rules.

        Returns the entry dict, or None when the entry must be omitted:
          - its resolved path (symlinks followed) fails the path rules, so a link
            pointing outside the allowed roots is hidden rather than advertised;
          - it is a file whose extension fails the extension rules;
          - its metadata cannot be read (treated as out of scope, not an error).
        """
        try:
            is_symlink: bool = entry_path.is_symlink()
            resolved: Path = entry_path.resolve(strict=False)
            is_dir: bool = entry_path.is_dir()
        except (OSError, RuntimeError, ValueError):
            return None

        # Directories are exempt from extension rules; files and symlinks are not.
        apply_extension_rules: bool = not is_dir or is_symlink
        if not PathAccess.is_path_allowed(args, resolved, apply_extension_rules=apply_extension_rules):
            return None

        if is_symlink:
            entry_type: str = "symlink"
            size_bytes: int | None = None
        elif is_dir:
            entry_type = "directory"
            size_bytes = None
        else:
            entry_type = "file"
            try:
                size_bytes = entry_path.stat().st_size
            except OSError:
                return None

        return {"name": entry_path.name, "type": entry_type, "size_bytes": size_bytes}
