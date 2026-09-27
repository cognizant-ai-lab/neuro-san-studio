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
from uuid import uuid4

from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.file_management.path_access import PathAccess
from neuro_san_studio.coded_tools.file_management.sly_data_history import SlyDataHistory

MAX_WRITE_BYTES: int = 10 * 1024 * 1024  # 10 MB hard cap on content written to disk
WRITE_FILE_HISTORY_KEY: str = "write_file_history"  # sly_data key for the list of written file paths


class WriteFile(CodedTool):
    """
    CodedTool implementation that writes text content to a local file.

    By default the tool cannot write to any path. Access must be explicitly granted
    via allow-lists in the tool arguments:
        - allowed_paths   : specific file paths or directories that may be written
        - allowed_file_extensions: file extensions (e.g. ".py", ".txt") that may be written

    allowed_paths is required and must be non-empty; allowed_file_extensions is
    optional (an empty list denies all extensions, omitting it skips extension filtering).
    Block-lists are evaluated after allow-lists; a match in a block-list always denies access.

    Overwriting an existing file and creating missing parent directories are both
    opt-in (overwrite / create_parents default to False), so the least-destructive
    behavior is the default and the calling agent must state destructive intent
    explicitly.

    Error types (raised as ValueError with the specified message prefix):
        invalid_input        – required parameter is missing, wrong type, or invalid value.
        path_not_allowed     – the resolved path is outside every allowed_paths entry,
                               its extension is not in allowed_file_extensions, or the
                               path stopped resolving to the authorized location
                               between the access check and the write.
        is_a_directory       – the path points to an existing directory, not a file.
        file_already_exists  – the file exists and overwrite is False. Enforced both
                               up front and atomically at write time, so a file that
                               appears concurrently is never clobbered.
        parent_not_found     – the parent directory does not exist and
                               create_parents is False.
        parent_not_a_directory – the parent path exists but is not a directory
                               (raised regardless of create_parents, since the
                               parent could never be created there).
        content_too_large    – the content exceeds MAX_WRITE_BYTES (10 MB) when UTF-8 encoded.
        write_error          – the file could not be written (permission error, I/O failure, etc.).

    Permissions: a newly created file gets the umask-derived default mode (as a
    plain open() would); overwriting an existing file preserves that file's mode.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any] | None) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "file_path"          (str, required): Absolute or relative path to the file.
                    "content"            (str, required): Text content to write. UTF-8 encoded
                                         when written to disk and when measured against
                                         MAX_WRITE_BYTES. May be empty.
                    "allowed_paths"      (list[str], required): One or more file paths or
                                         directory paths the tool is permitted to write to.
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
                    "overwrite"          (bool, optional): When True, an existing file at
                                         file_path is replaced. When False (the default),
                                         an existing file raises file_already_exists.
                    "create_parents"     (bool, optional): When True, missing parent directories
                                         are created (mkdir -p semantics). When False (the
                                         default), a missing parent raises parent_not_found.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None. May be None.

                Side effect: on success, the resolved path is appended to the
                "write_file_history" list in sly_data (deduped, insertion-ordered),
                guarded by a "write_file_history_lock" entry. Best-effort
                bookkeeping — skipped when sly_data is None.

        :return:
            A dictionary with the following keys:
                "path"          (str): The resolved absolute path that was written.
                "bytes_written" (int): Number of bytes written (UTF-8 encoded).
                "created"       (bool): True when the file did not previously exist;
                                False when an existing file was overwritten.
                "written_at"    (str): ISO-8601 UTC timestamp when the file was written.

        :raises ValueError: invalid_input, path_not_allowed, is_a_directory,
                            file_already_exists, parent_not_found,
                            parent_not_a_directory, content_too_large, write_error.
        """
        file_path, content, overwrite, create_parents = await self._async_precheck(args)
        created: bool = await self._async_write_file(file_path, content, overwrite, create_parents)
        await self._async_cache_write(sly_data, file_path)

        return {
            "path": str(file_path),
            "bytes_written": len(content),
            "created": created,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Async phases — async_invoke is just orchestration over these three.
    # ------------------------------------------------------------------

    async def _async_precheck(self, args: dict[str, Any]) -> tuple[Path, bytes, bool, bool]:
        """Run all pre-write validation and access checks.

        Returns (file_path, content, overwrite, create_parents).

        Order matters: resolve → access → argument validation → target/parent state.
        Access checks run before the filesystem is touched so out-of-scope paths never
        surface file_already_exists / parent_not_found (which would leak filesystem layout).
        """
        file_path: Path = await PathAccess.async_resolve_path(args)
        await PathAccess.async_validate_and_check_access(args, file_path)
        content: bytes = self._validate_content(args)
        overwrite: bool = PathAccess.validate_bool(args, "overwrite", False)
        create_parents: bool = PathAccess.validate_bool(args, "create_parents", False)
        await self._async_check_writable_target(file_path, overwrite)
        await self._async_check_parent(file_path, create_parents)
        return file_path, content, overwrite, create_parents

    async def _async_write_file(self, file_path: Path, content: bytes, overwrite: bool, create_parents: bool) -> bool:
        """Write content to file_path atomically. Returns True when the file was newly created.

        Raises write_error on permission / I/O failures.
        """
        logger: Logger = getLogger(self.__class__.__name__)
        logger.info("WriteFile: writing %d bytes to %s", len(content), file_path)
        created: bool = await asyncio.to_thread(self._write_atomically, file_path, content, overwrite, create_parents)
        logger.info("WriteFile: wrote %d bytes to %s (created=%s)", len(content), file_path, created)
        return created

    async def _async_cache_write(self, sly_data: dict[str, Any] | None, file_path: Path) -> None:
        """Append the resolved file path to the session-scoped write history in sly_data.

        Mirrors read_file's read_file_history: only the resolved path is recorded
        (deduped, insertion-ordered) so companion tools and operators can audit which
        files a conversation has modified.
        """
        await SlyDataHistory.async_record(sly_data, "write_file_history_lock", WRITE_FILE_HISTORY_KEY, file_path)

    # ------------------------------------------------------------------
    # Async wrappers for pre-write checks
    #
    # Each wrapper offloads its sync counterpart to a worker thread so the
    # event loop is never blocked by stat() or symlink-following syscalls.
    # The sync helpers stay independently testable.
    # ------------------------------------------------------------------

    async def _async_check_writable_target(self, file_path: Path, overwrite: bool) -> None:
        """Async wrapper around _check_writable_target."""
        await asyncio.to_thread(self._check_writable_target, file_path, overwrite)

    async def _async_check_parent(self, file_path: Path, create_parents: bool) -> None:
        """Async wrapper around _check_parent."""
        await asyncio.to_thread(self._check_parent, file_path, create_parents)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_content(self, args: dict[str, Any]) -> bytes:
        """Validate the 'content' argument and return it UTF-8 encoded.

        The byte-size cap is enforced on the encoded form (what actually lands on
        disk), so multi-byte characters can't sneak past a character-count check.
        """
        value: Any = args.get("content")
        if not isinstance(value, str):
            raise ValueError(f"invalid_input: 'content' must be a string, got {value!r}.")
        try:
            encoded: bytes = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            # A str can hold unpaired surrogates (e.g. from mis-decoded JSON) that
            # are not encodable as UTF-8; keep the documented error taxonomy.
            raise ValueError(f"invalid_input: 'content' is not encodable as UTF-8: {exc}") from exc
        if len(encoded) > MAX_WRITE_BYTES:
            raise ValueError(
                f"content_too_large: content is {len(encoded)} bytes; exceeds the {MAX_WRITE_BYTES}-byte limit."
            )
        return encoded

    def _check_writable_target(self, file_path: Path, overwrite: bool) -> None:
        """Verify the target is writable under the requested overwrite policy.

        Directories are never writable targets; existing files require overwrite=True.
        """
        if file_path.is_dir():
            raise ValueError(f"is_a_directory: '{file_path}' is a directory, not a file.")
        if file_path.exists() and not overwrite:
            raise ValueError(f"file_already_exists: '{file_path}' already exists and 'overwrite' is False.")

    def _check_parent(self, file_path: Path, create_parents: bool) -> None:
        """Verify the parent directory exists (or may be created) before writing.

        With create_parents=True missing parents are allowed — they are created
        inside _write_atomically. A parent path that exists but is not a directory
        is always parent_not_a_directory, regardless of create_parents, since
        mkdir could never succeed there.
        """
        parent: Path = file_path.parent
        if parent.is_dir():
            return
        if parent.exists():
            raise ValueError(f"parent_not_a_directory: parent of '{file_path}' exists but is not a directory.")
        if not create_parents:
            raise ValueError(
                f"parent_not_found: parent directory of '{file_path}' does not exist and 'create_parents' is False."
            )

    # ------------------------------------------------------------------
    # Write helper
    # ------------------------------------------------------------------

    def _write_atomically(self, file_path: Path, content: bytes, overwrite: bool, create_parents: bool) -> bool:
        """Write content to file_path via a same-directory temp file + atomic install.

        Atomicity matters here: a direct open()/write() that fails midway (disk full,
        process kill) would leave a truncated file behind, and a concurrent reader
        could observe a half-written file. The temp file lives in the target's own
        directory so the final install never crosses a filesystem boundary.

        The install step enforces the overwrite policy atomically, not just in the
        earlier precheck: with overwrite=False the temp file is installed via
        os.link(), which fails with FileExistsError if the target appeared since the
        precheck — a concurrent write is surfaced as file_already_exists instead of
        being silently clobbered. With overwrite=True, os.replace() is used.

        Permissions: the temp file is created with mode 0o666 filtered by the
        process umask (matching a plain open()), so new files get the conventional
        default instead of mkstemp's private 0o600. When overwriting, the target's
        existing mode is copied onto the temp file first, so os.replace() does not
        silently downgrade permissions other consumers rely on.

        Returns True when the target did not previously exist (file was created).
        Raises write_error on permission / I/O failures.
        """
        parent: Path = file_path.parent
        if create_parents:
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ValueError(f"write_error: Could not create parent directories for '{file_path}': {exc}") from exc

        # The access check in the precheck ran against a fully resolved path, but the
        # syscalls below re-traverse the path string. Re-resolve here, in the same
        # thread hop as the write, and refuse if a directory component was swapped
        # (e.g. for a symlink pointing outside the allowed roots) since the check.
        # This shrinks the check-to-use window from the whole precheck-to-write span
        # to microseconds; fully closing it needs openat2(RESOLVE_BENEATH), which is
        # not portably available.
        try:
            actual_parent: Path = parent.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"write_error: Could not resolve parent of '{file_path}': {exc}") from exc
        if actual_parent != parent:
            raise ValueError(
                f"path_not_allowed: parent of '{file_path}' no longer resolves to the authorized "
                f"directory (now '{actual_parent}'); refusing to write."
            )

        # Single stat for both the 'created' flag and the mode to preserve on
        # overwrite. Best-effort under concurrency; the install step below is what
        # actually guarantees the no-clobber policy.
        existing_mode: int | None = None
        try:
            existing_mode = stat_module.S_IMODE(file_path.stat().st_mode)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise ValueError(f"write_error: Could not stat '{file_path}': {exc}") from exc

        tmp_path: Path | None = None
        try:
            # O_EXCL guards against temp-name collisions; mode 0o666 is filtered by
            # the process umask at creation, unlike tempfile.mkstemp's fixed 0o600.
            tmp_path = parent / f".{file_path.name}.{uuid4().hex}.tmp"
            fd: int = os.open(tmp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
            if existing_mode is not None:
                os.chmod(tmp_path, existing_mode)
            self._install_temp_file(tmp_path, file_path, overwrite)
            tmp_path = None  # ownership transferred to the target path
        except PermissionError as exc:
            raise ValueError(f"write_error: Permission denied writing '{file_path}'.") from exc
        except OSError as exc:
            raise ValueError(f"write_error: Could not write '{file_path}': {exc}") from exc
        finally:
            # A failed write must not leave the temp file behind.
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        return existing_mode is None

    def _install_temp_file(self, tmp_path: Path, file_path: Path, overwrite: bool) -> None:
        """Atomically install the written temp file at the target path.

        overwrite=True uses os.replace(), which clobbers by design. overwrite=False
        uses os.link(), the atomic create-if-absent primitive: if the target came
        into existence after the precheck, the link fails with FileExistsError and
        the caller's file never overwrites it. On filesystems without hard-link
        support the link raises a different OSError; that fails closed as
        write_error rather than falling back to a non-atomic existence check +
        os.replace, which would silently reintroduce the clobber race the flag
        exists to prevent.
        """
        if overwrite:
            os.replace(tmp_path, file_path)
            return
        try:
            os.link(tmp_path, file_path)
        except FileExistsError as exc:
            raise ValueError(f"file_already_exists: '{file_path}' already exists and 'overwrite' is False.") from exc
        except PermissionError:
            # Not a hard-link-support problem; let the caller map it to its own
            # permission-denied write_error message.
            raise
        except OSError as exc:
            raise ValueError(
                f"write_error: Cannot guarantee no-clobber creation of '{file_path}' on this filesystem "
                f"(hard links unavailable: {exc}). Retry with 'overwrite' set to True if replacing is acceptable."
            ) from exc
        # The target is installed; a failure to remove the now-redundant temp link
        # must not be reported as a failed write.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
