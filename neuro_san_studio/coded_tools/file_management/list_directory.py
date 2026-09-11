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
from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from pathlib import Path
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.file_management.directory_handle import DirectoryHandle
from neuro_san_studio.coded_tools.file_management.path_access import PathAccess
from neuro_san_studio.coded_tools.file_management.path_not_allowed_error import PathNotAllowedError
from neuro_san_studio.coded_tools.file_management.path_rules import PathRules
from neuro_san_studio.coded_tools.file_management.sly_data_history import SlyDataHistory

DEFAULT_MAX_ENTRIES: int = 500
MAX_ENTRIES: int = 10_000  # ceiling on the LLM-settable max_entries, mirroring the 10 MB caps of read_file/write_file
MAX_SCAN_ENTRIES: int = 100_000  # scan budget: in-scope names kept from one directory before the call fails
LIST_DIRECTORY_HISTORY_KEY: str = "list_directory_history"  # sly_data key for the list of listed directories


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
    still denied under blocked_file_extensions=[".env"]. The target is judged
    under both the name the caller supplied and its resolved name, so reaching
    that directory through a symlink called 'prod.env' is denied as well.
    Block-lists are evaluated after allow-lists; a match in a block-list always
    denies access.

    Entries that fail the allow/block rules are silently omitted from the
    listing rather than reported, so the listing never leaks the existence of
    files the operator has scoped out (e.g. a blocked_paths subtree) — not
    through an error, not through the truncated flag, and not through the
    unreadable_entries count. For symlinks, the link is followed by the kernel
    relative to the listed directory's handle and its target must be a regular
    file or a directory; path rules are checked against the resolved target (so
    a link pointing outside the allowed roots is omitted) and extension rules
    are checked against BOTH the displayed name and the target's name,
    fail-closed. Symlinks resolving to directories are exempt from the
    extension allow-list like real directories. Special files (FIFOs, sockets,
    devices), symlinks to them, dangling symlinks, and symlink loops are
    omitted: they are not representable by the file management tools, and
    advertising a FIFO — or a link to one — as readable would hang a subsequent
    read_file call.

    The scan runs through a DirectoryHandle: on POSIX the access-checked path is
    opened one component at a time without following symlinks and every read is
    made relative to that descriptor; on platforms without descriptor-relative
    calls the path is strictly re-verified at open time instead and reads go
    through the path (a narrower guarantee, documented on DirectoryHandle).
    Either way a component swapped for a symlink after the check fails closed
    (list_error). Names the rules exclude are dropped as they are read, and at
    most MAX_SCAN_ENTRIES in-scope names are kept (list_error beyond that), so a
    huge allowed directory cannot drive an unbounded response.

    An unsearchable directory (names readable, metadata not) is detected up
    front and fails with list_error rather than presenting as empty. Otherwise
    entries whose metadata cannot be read (or whose names are not UTF-8
    encodable) are omitted and counted in "unreadable_entries" — but only when
    the entry would have qualified as a plain file under the rules, so the count
    can never reveal an entry the extension allow-list hides. The count covers
    the entries inspected before the max_entries cap was filled; the tail is
    never inspected beyond deciding "truncated".

    Error types (raised as ValueError with the specified message prefix):
        invalid_input    – required parameter is missing, wrong type, or invalid value.
        path_not_allowed – the resolved directory is outside every allowed_paths
                           entry or matches a block rule; also raised (instead of
                           path_not_found / not_a_directory) when the target is
                           missing or is a non-directory that the extension rules
                           would hide, so error types never form an existence oracle.
        path_not_found   – the directory does not exist.
        not_a_directory  – the path points to a file, not a directory.
        list_error       – the directory could not be opened or read (permission
                           error, not searchable, I/O failure, a path component
                           swapped for a symlink after the access check, or more
                           than MAX_SCAN_ENTRIES in-scope entries).
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
                "truncated"     (bool): True when at least one more entry that would
                                have qualified exists beyond the max_entries cap —
                                the listing is incomplete. Entries the rules exclude
                                never affect this flag.
                "unreadable_entries" (int): Number of entries inspected before the
                                cap was filled that were omitted because their
                                metadata could not be read; 0 for a fully readable
                                directory.
                "listed_at"     (str): ISO-8601 UTC timestamp when the listing was taken.

        :raises ValueError: invalid_input, path_not_allowed, path_not_found,
                            not_a_directory, list_error.
        """
        directory, rules, include_hidden, max_entries = await self._async_precheck(args)
        entries, truncated, unreadable = await self._async_list_entries(rules, directory, include_hidden, max_entries)
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

    async def _async_precheck(self, args: dict[str, Any]) -> tuple[Path, PathRules, bool, int]:
        """
        Run all pre-listing validation and access checks.

        Order matters: rules → resolve → access → existence. The operator's four
        rule lists are parsed and resolved into a PathRules FIRST, so a malformed
        entry anywhere in them fails with invalid_input before anything else is
        attempted — even resolving the target, which can fail on its own — and
        the same parsed rules then serve the target check and the whole scan.
        Access checks run before the filesystem is touched so out-of-scope paths
        never surface path_not_found (which would leak filesystem layout). The
        target is judged as a directory (exempt from the extension allow-list,
        never from block rules) under both the supplied and the resolved name.

        :param args: The tool argument dictionary.
        :return: A tuple of (directory, rules, include_hidden, max_entries).
        :raises ValueError: invalid_input, path_not_allowed, path_not_found,
                not_a_directory, list_error.
        """
        rules: PathRules = await asyncio.to_thread(PathRules, args)
        directory: Path = await PathAccess.async_resolve_path(args, "directory_path")
        display_name: str = PathAccess.supplied_name(args, "directory_path")
        self._check_target_access(rules, directory, display_name)
        include_hidden: bool = PathAccess.validate_bool(args, "include_hidden", False)
        max_entries: int = self._validate_max_entries(args)
        await self._async_check_directory_target(rules, directory, display_name)
        return directory, rules, include_hidden, max_entries

    async def _async_list_entries(
        self, rules: PathRules, directory: Path, include_hidden: bool, max_entries: int
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """
        Scan the directory in a worker thread.

        :param rules: The pre-parsed operator rules.
        :param directory: The resolved, access-checked directory to list.
        :param include_hidden: Whether dot-prefixed names are included.
        :param max_entries: Maximum number of entries to return.
        :return: A tuple of (entries, truncated, unreadable_count).
        """
        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("ListDirectory: listing %s", directory)
        entries, truncated, unreadable = await asyncio.to_thread(
            self._list_entries, rules, directory, include_hidden, max_entries
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
        """
        Append the resolved directory to the session-scoped listing history in sly_data.

        :param sly_data: The sly_data dictionary, or None when there is none.
        :param directory: The resolved directory that was listed.
        """
        await SlyDataHistory.async_record(
            sly_data, "list_directory_history_lock", LIST_DIRECTORY_HISTORY_KEY, directory
        )

    # ------------------------------------------------------------------
    # Async wrappers for pre-listing checks
    # ------------------------------------------------------------------

    async def _async_check_directory_target(self, rules: PathRules, directory: Path, display_name: str) -> None:
        """
        Async wrapper around _check_directory_target.

        :param rules: The pre-parsed operator rules.
        :param directory: The resolved directory target.
        :param display_name: The target's final path component as the caller supplied it.
        """
        await asyncio.to_thread(self._check_directory_target, rules, directory, display_name)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _check_target_access(self, rules: PathRules, directory: Path, display_name: str) -> None:
        """
        Enforce the operator's rules against the directory target, judged as a directory.

        Directories are exempt from the extension allow-list (a directory named
        'data' is not "extension .data") but never from block rules, and both the
        supplied name and the resolved name are checked, so a symlink 'prod.env'
        pointing at 'data' is denied under blocked_file_extensions=[".env"] exactly
        like a real directory named 'prod.env'.

        :param rules: The pre-parsed operator rules.
        :param directory: The resolved directory target.
        :param display_name: The target's final path component as the caller supplied it.
        :raises PathNotAllowedError: path_not_allowed when the rules deny the target.
        """
        reason: str | None = rules.deny_reason(directory, display_name, True)
        if reason is not None:
            raise PathNotAllowedError(self._denial_message(reason, directory, display_name))

    @staticmethod
    def _denial_message(reason: str, directory: Path, display_name: str) -> str:
        """
        Turn a PathRules deny reason into the path_not_allowed message the tool family uses.

        :param reason: The reason code returned by PathRules.deny_reason.
        :param directory: The resolved directory target.
        :param display_name: The target's final path component as the caller supplied it.
        :return: A message starting with the path_not_allowed prefix.
        """
        if reason == "outside_allowed_paths":
            return f"path_not_allowed: '{directory}' is not within any of the allowed_paths entries."
        if reason == "blocked_path":
            return f"path_not_allowed: '{directory}' is blocked by blocked_paths."
        if reason == "blocked_extension":
            return f"path_not_allowed: The extension of '{display_name}' is in blocked_file_extensions."
        return f"path_not_allowed: The extension of '{display_name}' is not in allowed_file_extensions."

    def _check_directory_target(self, rules: PathRules, directory: Path, display_name: str) -> None:
        """
        Verify the resolved target exists and is a directory, without leaking existence.

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

        :param rules: The pre-parsed operator rules.
        :param directory: The resolved directory target.
        :param display_name: The target's final path component as the caller supplied it.
        :raises ValueError: path_not_allowed, path_not_found, not_a_directory, list_error.
        """
        try:
            target_stat: os.stat_result = directory.stat()
        except FileNotFoundError:
            self._raise_denied_or(rules, directory, display_name, f"path_not_found: '{directory}' does not exist.")
            return
        except NotADirectoryError:
            # A path component is a regular file; the target cannot exist.
            self._raise_denied_or(rules, directory, display_name, f"path_not_found: '{directory}' does not exist.")
            return
        except PermissionError as exc:
            raise ValueError(f"list_error: Permission denied accessing '{directory}'.") from exc
        except OSError as exc:
            raise ValueError(f"list_error: Could not access '{directory}': {exc}") from exc

        if not stat_module.S_ISDIR(target_stat.st_mode):
            self._raise_denied_or(
                rules, directory, display_name, f"not_a_directory: '{directory}' is not a directory."
            )

    def _raise_denied_or(self, rules: PathRules, directory: Path, display_name: str, message: str) -> None:
        """
        Raise path_not_allowed when the full file rules deny the target, else the given error.

        Both the missing and the exists-but-not-a-directory cases funnel through
        here, so a path the extension rules hide gets the SAME path_not_allowed
        answer whether it exists or not. The target is judged as a plain FILE
        (is_directory=False): that applies the extension allow-list, which is
        exactly the rule set that would hide a file of that name from a listing.

        :param rules: The pre-parsed operator rules.
        :param directory: The resolved directory target.
        :param display_name: The target's final path component as the caller supplied it.
        :param message: The existence-revealing error to raise when the rules allow the path.
        :raises ValueError: Always — path_not_allowed or the given message.
        """
        if rules.deny_reason(directory, display_name, False) is not None:
            raise PathNotAllowedError(f"path_not_allowed: '{directory}' is not allowed as a listing target.")
        raise ValueError(message)

    def _validate_max_entries(self, args: dict[str, Any]) -> int:
        """
        Return a validated max_entries value.

        MAX_ENTRIES is a hard, operator-independent ceiling: max_entries is
        LLM-settable, and without a cap a single call against a huge allowed
        directory could build an unbounded response (memory + token blowup).

        :param args: The tool argument dictionary.
        :return: The validated max_entries value, or DEFAULT_MAX_ENTRIES when omitted.
        :raises ValueError: invalid_input when the value is not a positive integer
                no greater than MAX_ENTRIES.
        """
        value: int = PathAccess.validate_positive_int(args, "max_entries", DEFAULT_MAX_ENTRIES)
        if value > MAX_ENTRIES:
            raise ValueError(f"invalid_input: 'max_entries' must be at most {MAX_ENTRIES}, got {value}.")
        return value

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    def _list_entries(
        self, rules: PathRules, directory: Path, include_hidden: bool, max_entries: int
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """
        Enumerate, filter, and describe the directory's entries.

        The rules arrive pre-parsed (PathRules, built once in the precheck) so the
        per-entry check is pure lookups — no re-validation, no rule-path resolution,
        and no exception construction per denied entry.

        All filesystem reads go through a DirectoryHandle so the scan is bound to
        the directory the access check authorized (see that class for the
        descriptor-mode guarantee and the path-mode fallback). Searchability is
        probed once before enumeration: a directory whose names enumerate but whose
        metadata is unreadable fails loudly here rather than being inferred from
        per-entry failures, which would depend on which entries exist.

        :param rules: The pre-parsed operator rules.
        :param directory: The resolved, access-checked directory to list.
        :param include_hidden: Whether dot-prefixed names are included.
        :param max_entries: Maximum number of entries to return.
        :return: A tuple of (entries, truncated, unreadable_count).
        :raises ValueError: list_error when the directory cannot be opened, is not
                searchable, cannot be read, has a symlink path component, or
                exceeds the scan budget.
        """
        handle: DirectoryHandle = DirectoryHandle(directory)
        try:
            handle.open()
        except PermissionError as exc:
            raise ValueError(f"list_error: Permission denied listing '{directory}'.") from exc
        except OSError as exc:
            raise ValueError(f"list_error: Could not open '{directory}' for listing: {exc}") from exc

        try:
            if not handle.is_searchable():
                raise ValueError(
                    f"list_error: Permission denied listing '{directory}': the directory is not searchable."
                )
            names: list[str] = self._read_names(handle, rules, include_hidden)
            return self._collect_entries(handle, rules, names, max_entries)
        finally:
            handle.close()

    def _read_names(self, handle: DirectoryHandle, rules: PathRules, include_hidden: bool) -> list[str]:
        """
        Read the in-scope entry names through the handle, sorted, within the scan budget.

        Only names are kept — no Path objects and no metadata — so the fixed cost
        of a heavily filtered directory is one readdir plus a sort, and metadata is
        read later for at most the entries that can be returned. Hidden-name
        filtering and a rule prefilter happen here. The readdir d_type carried by
        each os.DirEntry says whether the entry is a plain file, a real directory,
        or a symlink without a metadata read: files are judged under the full rules
        (extension allow-list included), directories get the allow-list exemption,
        and symlinks (and Windows junctions) — whose verdict depends on their
        target — are classified fully right away (one stat per link). Anything
        denied here is dropped before it can count toward the scan budget or
        influence any result field, so scoped-out entries of every kind stay
        invisible everywhere, including in the budget error. When the type cannot
        be determined the entry is judged as a plain file — the strictest reading,
        so an unknown entry can never widen the budget — and the later metadata
        read decides.

        :param handle: The open handle on the listed directory.
        :param rules: The pre-parsed operator rules.
        :param include_hidden: Whether dot-prefixed names are kept.
        :return: The in-scope entry names, sorted.
        :raises ValueError: list_error when the read fails or more than
                MAX_SCAN_ENTRIES in-scope names are encountered.
        """
        directory: Path = handle.directory
        names: list[str] = []
        try:
            for entry in handle.scan_entries():
                name: str = entry.name
                if not include_hidden and name.startswith("."):
                    continue
                try:
                    is_symlink: bool = entry.is_symlink() or entry.is_junction()
                    is_directory: bool = entry.is_dir(follow_symlinks=False)
                except OSError:
                    is_symlink = False
                    is_directory = False
                if is_symlink:
                    # A link the rules would omit (out-of-scope or special target,
                    # dangling, loop) must not count toward the budget either.
                    if self._describe_symlink(handle, rules, name)[0] is None:
                        continue
                elif rules.deny_reason(directory / name, name, is_directory) is not None:
                    continue
                names.append(name)
                if len(names) > MAX_SCAN_ENTRIES:
                    raise ValueError(
                        f"list_error: '{directory}' has more than {MAX_SCAN_ENTRIES} entries in scope; "
                        "listing is not supported for directories this large."
                    )
        except PermissionError as exc:
            raise ValueError(f"list_error: Permission denied listing '{directory}'.") from exc
        except OSError as exc:
            raise ValueError(f"list_error: Could not list '{directory}': {exc}") from exc
        names.sort()
        return names

    def _collect_entries(
        self, handle: DirectoryHandle, rules: PathRules, names: list[str], max_entries: int
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """
        Describe the sorted names in order until the cap is filled, then look one qualifying entry ahead.

        Once the cap is filled, the tail is examined only until the next entry that
        would have qualified (or could have, had its metadata been readable), which
        sets truncated; nothing past the cap is returned and nothing past it is
        counted — unreadable_entries covers the inspected window only. Because
        denied names never reach this method, neither truncated nor the unreadable
        count can reveal an entry the operator scoped out.

        :param handle: The open handle on the listed directory.
        :param rules: The pre-parsed operator rules.
        :param names: The in-scope entry names, sorted.
        :param max_entries: Maximum number of entries to return.
        :return: A tuple of (entries, truncated, unreadable_count).
        """
        entries: list[dict[str, Any]] = []
        truncated: bool = False
        unreadable: int = 0
        for name in names:
            described, failure = self._describe_entry(handle, rules, name)
            if failure is not None:
                if len(entries) >= max_entries:
                    # Past the cap, an unreadable entry may well have qualified:
                    # the listing is incomplete either way. Not counted — the tail
                    # is not inspected beyond this decision.
                    truncated = True
                    break
                unreadable += 1
                continue
            if described is None:
                continue
            if len(entries) >= max_entries:
                # One more qualifying entry exists beyond the cap: flag it, never return it.
                truncated = True
                break
            entries.append(described)
        return entries, truncated, unreadable

    def _describe_entry(
        self, handle: DirectoryHandle, rules: PathRules, name: str
    ) -> tuple[dict[str, Any] | None, Exception | None]:
        """
        Classify one in-scope entry through the handle and check it against the pre-parsed rules.

        Metadata comes from a single lstat relative to the handle: it never follows
        symlinks, so a swapped-in link cannot leak an out-of-scope target's size;
        real symlinks are handed to _describe_symlink. The caller has already
        dropped names the rules deny under the permissive (directory) assumption;
        the type-aware check happens here once the type is known.

        :param handle: The open handle on the listed directory.
        :param rules: The pre-parsed operator rules.
        :param name: The entry name.
        :return: A tuple of (entry_dict, failure). entry_dict is None when the entry
                is omitted; failure is the exception when the entry's metadata could
                not be read (the caller counts it) and None otherwise.
        """
        entry_path: Path = handle.directory / name
        try:
            # Names that cannot round-trip through UTF-8 (surrogateescape artifacts
            # from non-UTF-8 filesystems) would make the whole response fail at
            # transport serialization — treat them as unreadable instead.
            name.encode("utf-8")
            entry_stat: os.stat_result = handle.lstat(name)
        except FileNotFoundError:
            # Removed between readdir and stat: nothing to report, nothing unreadable.
            return None, None
        except (UnicodeEncodeError, OSError) as exc:
            # Only an entry that would qualify even as a plain file may surface as
            # unreadable: an entry the extension allow-list would hide must stay
            # invisible in the count too, and without metadata "plain file" is the
            # assumption that can never widen what the rules would show.
            if rules.deny_reason(entry_path, name, False) is not None:
                return None, None
            return None, exc

        if stat_module.S_ISLNK(entry_stat.st_mode) or self._is_junction(entry_stat):
            return self._describe_symlink(handle, rules, name)
        entry_type, size_bytes, is_directory = self._classify_entry(entry_stat)
        if entry_type is None or rules.deny_reason(entry_path, name, is_directory) is not None:
            # Special file (FIFO/socket/device) or excluded by the rules: omitted silently.
            return None, None
        return {"name": name, "type": entry_type, "size_bytes": size_bytes}, None

    @staticmethod
    def _is_junction(entry_stat: os.stat_result) -> bool:
        """
        Report whether an lstat result describes a Windows directory junction.

        Junctions are reparse points that lstat reports as directories rather than
        symlinks, yet they redirect like a link, so they must go through the same
        target-resolution checks. Always False where the stat result carries no
        reparse tag (POSIX).

        :param entry_stat: The entry's lstat result.
        :return: True for a mount-point reparse tag.
        """
        tag: int = getattr(entry_stat, "st_reparse_tag", 0)
        return tag != 0 and tag == getattr(stat_module, "IO_REPARSE_TAG_MOUNT_POINT", None)

    @staticmethod
    def _classify_entry(entry_stat: os.stat_result) -> tuple[str | None, int | None, bool]:
        """
        Classify a non-symlink entry from its lstat result.

        :param entry_stat: The entry's lstat result.
        :return: A tuple of (entry_type, size_bytes, is_directory). entry_type is
                None for FIFOs, sockets, and devices, which the file tools cannot
                represent and the listing omits.
        """
        mode: int = entry_stat.st_mode
        if stat_module.S_ISDIR(mode):
            return "directory", None, True
        if stat_module.S_ISREG(mode):
            return "file", entry_stat.st_size, False
        return None, None, False

    def _describe_symlink(
        self, handle: DirectoryHandle, rules: PathRules, name: str
    ) -> tuple[dict[str, Any] | None, Exception | None]:
        """
        Describe a symlink entry, admitting it only when its target is a regular file or a directory.

        The link is followed relative to the directory handle, so what it points at
        is decided against the directory the access check authorized rather than
        by re-walking the path text. The target's type gates the entry: FIFOs,
        sockets, devices, dangling links, and loops are omitted exactly like their
        direct counterparts — a link to a FIFO advertised as a symlink would pass
        read_file's prechecks and hang its open(). The textual resolution used for
        the rule check is then verified to land on that same inode, so a link
        retargeted between the two traversals is dropped rather than trusted.

        :param handle: The open handle on the listed directory.
        :param rules: The pre-parsed operator rules.
        :param name: The symlink's name.
        :return: A tuple of (entry_dict or None, None). A symlink never counts as
                unreadable: the entry itself was read, and counting an unusable
                target would reveal that a link to something exists.
        """
        try:
            target_stat: os.stat_result = handle.stat(name)
        except OSError:
            return None, None
        target_mode: int = target_stat.st_mode
        if stat_module.S_ISDIR(target_mode):
            is_directory: bool = True
        elif stat_module.S_ISREG(target_mode):
            is_directory = False
        else:
            return None, None

        try:
            resolved: Path = (handle.directory / name).resolve(strict=True)
            resolved_stat: os.stat_result = os.stat(resolved)
        except (OSError, RuntimeError, ValueError):
            return None, None
        if not os.path.samestat(target_stat, resolved_stat):
            return None, None

        if rules.deny_reason(resolved, name, is_directory) is not None:
            return None, None
        return {"name": name, "type": "symlink", "size_bytes": None}, None
