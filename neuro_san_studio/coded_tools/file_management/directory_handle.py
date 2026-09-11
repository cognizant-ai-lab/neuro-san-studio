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

import errno
import os
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType
from typing import Self

# Descriptor-relative filesystem calls (openat/fstatat/faccessat/fdopendir) are a
# POSIX facility. Where any of them is missing (Windows), the handle falls back to
# path mode; see the class docstring for what that mode can and cannot guarantee.
_HAS_DESCRIPTOR_CALLS: bool = (
    os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.access in os.supports_dir_fd
    and os.scandir in os.supports_fd
)

# Flags for opening each path component: read-only, must be a directory, never
# follow a symlink, and keep the descriptor out of any child process. Flags a
# platform lacks are replaced by 0, a no-op.
_OPEN_DIRECTORY_FLAGS: int = (
    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
)


class DirectoryHandle:
    """
    An opened directory that answers name and metadata queries relative to itself.

    Why this exists: an access check authorizes a resolved path TEXT, but a later
    scan that re-walks that text can be redirected — rename the checked directory
    away, drop a symlink in its place, and a path-based scan lists whatever the
    link points at, with every entry judged as if it lived under the authorized
    root. Binding the scan to the directory itself closes that window.

    Descriptor mode (POSIX): open() walks the path one component at a time, each
    opened with O_NOFOLLOW relative to the previous component's descriptor. The
    path was fully resolved before the access check, so a legitimate target has
    no symlink anywhere in it; meeting one means a component was swapped after
    the check, and the open fails closed. Every later query (names, lstat, stat,
    searchability) is made relative to the descriptor, so a rename of the path
    text after open() cannot redirect them.

    Path mode (platforms without descriptor-relative calls, e.g. Windows): open()
    strictly re-resolves the path and refuses to proceed unless it still resolves
    to itself (present, no symlink component); queries then go through the path.
    That narrows the check-to-use window to the gap between the verification and
    each query rather than closing it — the strongest guarantee the platform's
    standard library offers.

    Instances are single-use context managers. Queries raise OSError exactly like
    the standard-library calls they wrap; callers map those to their own error
    taxonomy.
    """

    def __init__(self, directory: Path) -> None:
        """
        Prepare a handle for the given directory; nothing is opened until open().

        :param directory: The resolved, access-checked directory.
        """
        self._directory: Path = directory
        self._fd: int | None = None
        self._is_open: bool = False

    @property
    def directory(self) -> Path:
        """
        :return: The directory this handle was created for.
        """
        return self._directory

    @property
    def is_open(self) -> bool:
        """
        :return: True between a successful open() and close().
        """
        return self._is_open

    @property
    def uses_descriptor(self) -> bool:
        """
        :return: True when queries are descriptor-relative (POSIX), False in path mode.
        """
        return self._fd is not None

    def __enter__(self) -> Self:
        """
        Open the directory on entry.

        :return: This handle.
        :raises OSError: See open().
        """
        self.open()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """
        Close the directory on exit.

        :param exc_type: The exception type propagating out of the block, if any.
        :param exc: The exception instance, if any.
        :param traceback: Its traceback, if any.
        """
        self.close()

    def open(self) -> None:
        """
        Open the directory in descriptor mode when the platform allows it, else verify it in path mode.

        :raises OSError: when a component cannot be opened, a component is a symlink
                (ELOOP), or the path no longer resolves to itself.
        """
        if _HAS_DESCRIPTOR_CALLS:
            self._fd = self._open_descriptor(self._directory)
        else:
            self._verify_path()
        self._is_open = True

    def close(self) -> None:
        """
        Release the descriptor, if any. Safe to call more than once.
        """
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._is_open = False

    def is_searchable(self) -> bool:
        """
        Report whether entry metadata can be read through this directory (the POSIX search bit).

        A directory can be readable (its names enumerate) yet not searchable (every
        stat of an entry fails with EACCES). Probing that once up front lets a
        caller fail loudly instead of returning an empty listing, without inferring
        it from per-entry failures — an inference that would itself depend on which
        entries exist.

        :return: True when the directory grants search (execute) permission.
        """
        if self._fd is not None:
            return os.access(".", os.X_OK, dir_fd=self._fd)
        return os.access(self._directory, os.X_OK)

    def scan_names(self) -> Iterator[str]:
        """
        Yield the directory's entry names (never '.' or '..'), in filesystem order.

        :return: An iterator over entry names; the handle must stay open while it is consumed.
        :raises OSError: when the directory cannot be read.
        """
        target: int | Path = self._fd if self._fd is not None else self._directory
        with os.scandir(target) as scanner:
            for entry in scanner:
                yield entry.name

    def lstat(self, name: str) -> os.stat_result:
        """
        Stat an entry without following a symlink.

        :param name: The entry name.
        :return: The entry's own stat result.
        :raises OSError: when the entry cannot be stat'ed.
        """
        if self._fd is not None:
            return os.stat(name, dir_fd=self._fd, follow_symlinks=False)
        return os.lstat(self._directory / name)

    def stat(self, name: str) -> os.stat_result:
        """
        Stat an entry, following a symlink to its final target.

        :param name: The entry name.
        :return: The stat result of the entry or, for a symlink, of its target.
        :raises OSError: for a dangling link (ENOENT), a loop (ELOOP), or an unreadable target.
        """
        if self._fd is not None:
            return os.stat(name, dir_fd=self._fd)
        return os.stat(self._directory / name)

    @staticmethod
    def _open_descriptor(directory: Path) -> int:
        """
        Walk the path component by component with O_NOFOLLOW and return the final descriptor.

        :param directory: The resolved directory to open.
        :return: An open read-only directory descriptor; the caller closes it.
        :raises OSError: when any component cannot be opened or is a symlink.
        """
        fd: int = os.open(directory.anchor, _OPEN_DIRECTORY_FLAGS)
        try:
            for part in directory.parts[1:]:
                next_fd: int = os.open(part, _OPEN_DIRECTORY_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = next_fd
        except OSError:
            os.close(fd)
            raise
        return fd

    def _verify_path(self) -> None:
        """
        Path mode: require the directory to still resolve strictly to itself.

        :raises OSError: FileNotFoundError when it vanished; ELOOP when a component
                is now a symlink (the strict resolution lands elsewhere).
        """
        if self._directory.resolve(strict=True) != self._directory:
            raise OSError(
                getattr(errno, "ELOOP", errno.EINVAL),
                "path no longer resolves to the checked directory",
                str(self._directory),
            )
