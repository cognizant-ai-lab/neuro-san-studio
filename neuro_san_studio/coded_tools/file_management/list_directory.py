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
import stat as stat_module
from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from pathlib import Path
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.file_management.path_access import PathAccess
from neuro_san_studio.coded_tools.file_management.path_rules import PathRules
from neuro_san_studio.coded_tools.file_management.sly_data_history import SlyDataHistory

DEFAULT_MAX_ENTRIES: int = 500
MAX_ENTRIES: int = 10_000  # hard cap on max_entries, mirroring the 10 MB caps of read_file/write_file
LIST_DIRECTORY_HISTORY_KEY: str = "list_directory_history"  # sly_data key for the list of listed directories

# _describe_entry status values
_STATUS_OK: str = "ok"
_STATUS_DENIED: str = "denied"  # entry fails the allow/block rules — omitted silently by design
_STATUS_ERROR: str = "error"  # entry metadata unreadable — omitted but counted, so listings self-report gaps
_STATUS_SPECIAL: str = "special"  # FIFO/socket/device — not representable by the file tools, omitted


class ListDirectory(CodedTool):
    """
    CodedTool implementation that lists the entries of a local directory.

    By default the tool cannot list any directory. Access must be explicitly
    granted via allow-lists in the tool arguments:
        - allowed_paths   : specific directories (or files) that may be accessed
        - allowed_file_extensions: file extensions the listing may include

    allowed_paths is required and must be non-empty. The directory target itself
    is exempt from the extension ALLOW-list (directories have no meaningful
    extension for a file-oriented whitelist); blocked_paths and
    blocked_file_extensions always apply, so a directory named 'prod.env' is
    still denied under blocked_file_extensions=[".env"]. Block-lists are
    evaluated after allow-lists; a match in a block-list always denies access.

    Entries that fail the allow/block rules are silently omitted from the
    listing rather than reported, so the listing never leaks the existence of
    files the operator has scoped out (e.g. a blocked_paths subtree). For
    symlinks, path rules are checked against the resolved target (so a link
    pointing outside the allowed roots is omitted) and extension rules are
    checked against BOTH the displayed name and the target's name, fail-closed.
    Symlinks resolving to directories are exempt from the extension allow-list
    like real directories. Special files (FIFOs, sockets, devices) are omitted:
    they are not representable by the file management tools, and advertising a
    FIFO as a readable file would hang a subsequent read_file call.

    Entries whose metadata cannot be read (or whose names are not UTF-8
    encodable) are omitted and counted in "unreadable_entries", so a listing
    with gaps never presents itself as complete; when NO entry can be returned
    and at least one was unreadable, the call fails with list_error instead of
    reporting an unsearchable directory as empty.

    Error types (raised as ValueError with the specified message prefix):
        invalid_input    – required parameter is missing, wrong type, or invalid value.
        path_not_allowed – the resolved directory is outside every allowed_paths
                           entry or matches a block rule; also raised (instead of
                           path_not_found / not_a_directory) when the target is
                           missing or is a non-directory that the extension rules
                           would hide, so error types never form an existence oracle.
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
                                         (including symlinks to directories) are not
                                         extension-filtered. When omitted, no extension
                                         filtering is applied. An empty list omits all
                                         file entries.
                    "blocked_paths"      (list[str], optional): File paths or directories that
                                         are always denied, even if listed in allowed_paths.
                    "blocked_file_extensions" (list[str], optional): File extensions whose
                                         entries are always omitted from the listing. Also
                                         applies to directory names and to symlinks'
                                         displayed names.
                    "include_hidden"     (bool, optional): When True, dotfiles and dot-
                                         directories are included. Defaults to False.
                    "max_entries"        (int, optional): Cap on the number of returned
                                         entries. Defaults to DEFAULT_MAX_ENTRIES (500);
                                         must be a positive integer no greater than
                                         MAX_ENTRIES (10000).

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
                "truncated"     (bool): True when the max_entries cap was reached with
                                directory entries still unexamined — the listing may
                                be incomplete.
                "unreadable_entries" (int): Number of entries omitted because their
                                metadata could not be read; 0 for a fully readable
                                directory.
                "listed_at"     (str): ISO-8601 UTC timestamp when the listing was taken.

        :raises ValueError: invalid_input, path_not_allowed, path_not_found,
                            not_a_directory, list_error.
        """
        directory, include_hidden, max_entries = await self._async_precheck(args)
        entries, truncated, unreadable = await self._async_list_entries(args, directory, include_hidden, max_entries)
        await self._async_cache_listing(sly_data, directory)

        return {
            "path": str(directory),
            "entries": entries,
            "total_entries": len(entries),
            "truncated": truncated,
            "unreadable_entries": unreadable,
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
        (which would leak filesystem layout). The extension allow-list is not
        applied to the directory target itself — only to the file entries inside
        it; block rules always apply.
        """
        directory: Path = await PathAccess.async_resolve_path(args, "directory_path")
        await PathAccess.async_validate_and_check_access(args, directory, enforce_allowed_extensions=False)
        include_hidden: bool = PathAccess.validate_bool(args, "include_hidden", False)
        max_entries: int = self._validate_max_entries(args)
        await self._async_check_directory_target(args, directory)
        return directory, include_hidden, max_entries

    async def _async_list_entries(
        self, args: dict[str, Any], directory: Path, include_hidden: bool, max_entries: int
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """Scan the directory in a worker thread and return (entries, truncated, unreadable)."""
        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("ListDirectory: listing %s", directory)
        entries, truncated, unreadable = await asyncio.to_thread(
            self._list_entries, args, directory, include_hidden, max_entries
        )
        logger.info(
            "ListDirectory: returned %d entries from %s (truncated=%s, unreadable=%d)",
            len(entries),
            directory,
            truncated,
            unreadable,
        )
        return entries, truncated, unreadable

    async def _async_cache_listing(self, sly_data: dict[str, Any] | None, directory: Path) -> None:
        """Append the resolved directory to the session-scoped listing history in sly_data."""
        await SlyDataHistory.async_record(
            sly_data, "list_directory_history_lock", LIST_DIRECTORY_HISTORY_KEY, directory
        )

    # ------------------------------------------------------------------
    # Async wrappers for pre-listing checks
    # ------------------------------------------------------------------

    async def _async_check_directory_target(self, args: dict[str, Any], directory: Path) -> None:
        """Async wrapper around _check_directory_target."""
        await asyncio.to_thread(self._check_directory_target, args, directory)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _check_directory_target(self, args: dict[str, Any], directory: Path) -> None:
        """Verify the resolved target exists and is a directory, without leaking existence.

        os.stat (not Path.exists) is used so a permission failure surfaces as
        list_error instead of being swallowed into a false "does not exist" —
        pathlib's exists() returns False on EACCES.

        Existence-oracle guard: the precheck exempts the target from the extension
        allow-list (directories have no meaningful extension), so a FILE path the
        extension rules would hide could otherwise be probed via the error type
        (not_a_directory = exists, path_not_found = doesn't). Whenever the target
        is missing or is not a directory, re-check it under the FULL file rules
        first and answer path_not_allowed uniformly when they deny it — the
        existence-revealing error types are only used for paths the agent could
        legitimately see as files anyway.
        """
        try:
            target_stat = directory.stat()
        except FileNotFoundError:
            self._raise_denied_or(args, directory, f"path_not_found: '{directory}' does not exist.")
            return
        except NotADirectoryError:
            # A path component is a regular file; the target cannot exist.
            self._raise_denied_or(args, directory, f"path_not_found: '{directory}' does not exist.")
            return
        except PermissionError as exc:
            raise ValueError(f"list_error: Permission denied accessing '{directory}'.") from exc
        except OSError as exc:
            raise ValueError(f"list_error: Could not access '{directory}': {exc}") from exc

        if not stat_module.S_ISDIR(target_stat.st_mode):
            self._raise_denied_or(args, directory, f"not_a_directory: '{directory}' is not a directory.")

    def _raise_denied_or(self, args: dict[str, Any], directory: Path, message: str) -> None:
        """Raise path_not_allowed when the full file rules deny the target, else the given error.

        Both the missing and the exists-but-not-a-directory cases funnel through
        here, so a path the extension rules hide gets the SAME path_not_allowed
        answer whether it exists or not.
        """
        if not PathAccess.is_path_allowed(args, directory, enforce_allowed_extensions=True):
            raise ValueError(f"path_not_allowed: '{directory}' is not allowed as a listing target.")
        raise ValueError(message)

    def _validate_max_entries(self, args: dict[str, Any]) -> int:
        """Return a validated max_entries value, raising invalid_input on bad input.

        MAX_ENTRIES is a hard, operator-independent ceiling: max_entries is
        LLM-settable, and without a cap a single call against a huge allowed
        directory could build an unbounded response (memory + token blowup).
        """
        value: int = PathAccess.validate_positive_int(args, "max_entries", DEFAULT_MAX_ENTRIES)
        if value > MAX_ENTRIES:
            raise ValueError(f"invalid_input: 'max_entries' must be at most {MAX_ENTRIES}, got {value}.")
        return value

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    def _list_entries(
        self, args: dict[str, Any], directory: Path, include_hidden: bool, max_entries: int
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """Enumerate, filter, and describe the directory's entries.

        The rules are parsed and resolved ONCE here (PathRules) so the per-entry
        check is pure lookups — no re-validation, no rule-path resolution, and no
        exception construction per denied entry. A malformed rule entry therefore
        fails the whole call up front instead of aborting midway through a scan.

        Names are sorted first so the output (and which entries fall past the
        max_entries cap) is deterministic. Entries the access rules exclude are
        omitted silently — surfacing them (even as an error) would leak the
        existence of paths the operator scoped out. Entries whose metadata cannot
        be read are omitted but counted, and if nothing could be returned while at
        least one entry was unreadable the call fails with list_error rather than
        presenting an unsearchable directory as empty.

        Returns (entries, truncated, unreadable_count). truncated=True means the
        cap was reached with names still unexamined (the tail is NOT scanned —
        deliberately, so a heavily filtered huge directory can't force a full
        walk); those unexamined names may or may not have qualified.

        Raises list_error on permission / I/O failures.
        """
        rules: PathRules = PathRules(args)

        try:
            # Hidden-name filtering happens before the sort: it needs no metadata,
            # so excluded dotfiles never cost sort comparisons or syscalls.
            visible: list[str] = sorted(
                entry.name for entry in directory.iterdir() if include_hidden or not entry.name.startswith(".")
            )
        except PermissionError as exc:
            raise ValueError(f"list_error: Permission denied listing '{directory}'.") from exc
        except OSError as exc:
            raise ValueError(f"list_error: Could not list '{directory}': {exc}") from exc

        entries: list[dict[str, Any]] = []
        truncated: bool = False
        unreadable: int = 0
        for index, name in enumerate(visible):
            described, status = self._describe_entry(rules, directory, name)
            if status == _STATUS_ERROR:
                unreadable += 1
                continue
            if described is None:
                continue
            entries.append(described)
            if len(entries) >= max_entries:
                truncated = index + 1 < len(visible)
                break

        if unreadable and not entries:
            raise ValueError(
                f"list_error: Could not read metadata for any entry in '{directory}' "
                f"({unreadable} unreadable) — permission denied?"
            )
        return entries, truncated, unreadable

    def _describe_entry(self, rules: PathRules, directory: Path, name: str) -> tuple[dict[str, Any] | None, str]:
        """Classify one entry and check it against the pre-parsed access rules.

        Returns (entry_dict, status): entry_dict is None unless status is "ok".
        Statuses: "denied" (fails the rules — omitted silently so scoped-out paths
        never leak), "special" (FIFO/socket/device — not representable by the file
        tools), "error" (metadata unreadable or name not UTF-8 encodable — counted
        by the caller so the listing reports its gaps).

        A single lstat supplies type and size: it never follows symlinks, so there
        is no window between a type check and a stat in which a swapped-in symlink
        could leak an out-of-scope target's metadata; only genuine symlinks are
        resolved (for target confinement), the parent directory itself having been
        resolved in the precheck.
        """
        entry_path: Path = directory / name
        try:
            # Names that cannot round-trip through UTF-8 (surrogateescape artifacts
            # from non-UTF-8 filesystems) would make the whole response fail at
            # transport serialization — count them as unreadable instead.
            name.encode("utf-8")
            entry_stat = entry_path.lstat()
        except (UnicodeEncodeError, OSError):
            return None, _STATUS_ERROR

        mode: int = entry_stat.st_mode
        size_bytes: int | None = None
        if stat_module.S_ISLNK(mode):
            entry_type: str = "symlink"
            try:
                resolved: Path = entry_path.resolve(strict=False)
                is_directory: bool = entry_path.is_dir()
            except (OSError, RuntimeError, ValueError):
                return None, _STATUS_ERROR
        elif stat_module.S_ISDIR(mode):
            entry_type = "directory"
            resolved = entry_path
            is_directory = True
        elif stat_module.S_ISREG(mode):
            entry_type = "file"
            size_bytes = entry_stat.st_size
            resolved = entry_path
            is_directory = False
        else:
            return None, _STATUS_SPECIAL

        if rules.deny_reason(resolved, name, is_directory) is not None:
            return None, _STATUS_DENIED

        return {"name": name, "type": entry_type, "size_bytes": size_bytes}, _STATUS_OK
