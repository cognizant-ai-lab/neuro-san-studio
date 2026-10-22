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
from pathlib import Path
from typing import Any


class PathAccess:
    """
    Shared path validation and access-control helpers for the file management tools.

    Every file management tool (read_file, write_file, ...) enforces the same
    operator-configured security model:
        - allowed_paths          : required, non-empty allow-list of files/directories.
        - allowed_file_extensions: optional allow-list of extensions. None (omitted)
                                   skips the check; an empty list denies all.
        - blocked_paths          : optional block-list of files/directories.
        - blocked_file_extensions: optional block-list of extensions.
    Block-lists are evaluated after allow-lists; a match in a block-list always
    denies access.

    All methods are static so tools can call them without holding shared state;
    each raises ValueError with a machine-readable prefix (invalid_input,
    path_not_allowed) consistent with the per-tool error taxonomies.

    IMPORTANT ordering contract for callers: run resolve_path() and
    validate_and_check_access() BEFORE any filesystem existence checks, so
    out-of-scope paths always surface path_not_allowed and never leak
    filesystem layout via a path_not_found / file_already_exists error type.
    """

    # ------------------------------------------------------------------
    # Async wrappers
    #
    # Each wrapper offloads its sync counterpart to a worker thread so the
    # event loop is never blocked by Path resolution or symlink-following
    # syscalls. The sync helpers stay independently testable.
    # ------------------------------------------------------------------

    @staticmethod
    async def async_resolve_path(args: dict[str, Any], param_name: str = "file_path") -> Path:
        """Async wrapper around resolve_path."""
        return await asyncio.to_thread(PathAccess.resolve_path, args, param_name)

    @staticmethod
    async def async_validate_and_check_access(args: dict[str, Any], file_path: Path) -> None:
        """Async wrapper around validate_and_check_access."""
        await asyncio.to_thread(PathAccess.validate_and_check_access, args, file_path)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_path(args: dict[str, Any], param_name: str = "file_path") -> Path:
        """Parse and resolve a path argument without touching the filesystem.

        :param args: The tool argument dictionary.
        :param param_name: Name of the args key holding the path (e.g. "file_path",
                "source_path"). Used in error messages so callers can tell which
                parameter failed.
        :return: The absolute, symlink-resolved Path. Only raises invalid_input —
                never path_not_found or is_a_directory, so callers can run access
                checks before existence checks and avoid leaking filesystem layout
                via error type.
        """
        value: Any = args.get(param_name, "")
        if not isinstance(value, str):
            raise ValueError(f"invalid_input: '{param_name}' must be a string, got {value!r}.")
        path_str: str = value.strip()
        if not path_str:
            raise ValueError(f"invalid_input: No '{param_name}' provided.")

        try:
            # expanduser() raises RuntimeError (not OSError) when the home directory
            # of a '~user' path cannot be determined, so it must be caught explicitly
            # to keep the invalid_input taxonomy instead of leaking a raw traceback.
            return Path(path_str).expanduser().resolve(strict=False)
        except (ValueError, OSError, RuntimeError) as exc:
            raise ValueError(f"invalid_input: Cannot resolve '{param_name}' '{path_str}': {exc}") from exc

    @staticmethod
    def validate_allowed_paths(args: dict[str, Any]) -> list[str]:
        """Validate and return the 'allowed_paths' list. Raises invalid_input when missing or empty."""
        paths: list[str] = PathAccess.validate_path_list(args.get("allowed_paths"), "allowed_paths")
        if not paths:
            raise ValueError("invalid_input: 'allowed_paths' is required and must be a non-empty list of paths.")
        return paths

    @staticmethod
    def validate_and_check_access(args: dict[str, Any], file_path: Path) -> None:
        """Validate the four allow/block rule lists from args and enforce them against file_path."""
        PathAccess.check_path_allowed(
            file_path,
            PathAccess.validate_allowed_paths(args),
            PathAccess.validate_extension_list(args.get("allowed_file_extensions"), "allowed_file_extensions"),
            PathAccess.validate_path_list(args.get("blocked_paths"), "blocked_paths"),
            PathAccess.validate_extension_list(args.get("blocked_file_extensions"), "blocked_file_extensions"),
        )

    @staticmethod
    def validate_path_list(value: Any, param_name: str) -> list[str]:
        """Coerce and validate a path list parameter. Accepts None, list[str], or a single str."""
        coerced: list[str] | None = PathAccess._coerce_str_list(value, param_name)
        return [] if coerced is None else coerced

    @staticmethod
    def validate_extension_list(value: Any, param_name: str) -> list[str] | None:
        """Coerce and validate an extension list parameter. Accepts None, list[str], or a single str.

        None means the parameter was omitted (sentinel for "no filtering"); an empty list means deny all.
        """
        return PathAccess._coerce_str_list(value, param_name)

    @staticmethod
    def _coerce_str_list(value: Any, param_name: str) -> list[str] | None:
        """Shared coercion core for the allow/block list parameters.

        Accepts None (returned as-is so callers can apply their own sentinel
        semantics), a single str (wrapped in a list), or list[str].

        Blank / whitespace-only entries are rejected as invalid_input: a blank
        path entry would resolve to the process working directory in
        path_matches_any (Path('').resolve() is the CWD), silently turning a
        misconfigured allow-list entry (e.g. an unset templating variable) into
        access to the entire working-directory tree. Failing closed here keeps
        that misconfiguration loud.
        """
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise ValueError(f"invalid_input: '{param_name}' must be a list of strings, got {value!r}.")
        for item in value:
            if not isinstance(item, str):
                raise ValueError(
                    f"invalid_input: '{param_name}' must be a list of strings, "
                    f"but contains non-string element {item!r}."
                )
            if not item.strip():
                raise ValueError(f"invalid_input: '{param_name}' contains a blank entry, which is not allowed.")
        return value

    @staticmethod
    def validate_bool(args: dict[str, Any], param_name: str, default: bool) -> bool:
        """Return a validated boolean parameter, raising invalid_input on non-bool input."""
        value: Any = args.get(param_name, default)
        if not isinstance(value, bool):
            raise ValueError(f"invalid_input: '{param_name}' must be a boolean, got {value!r}.")
        return value

    # ------------------------------------------------------------------
    # Access-control helpers
    # ------------------------------------------------------------------

    @staticmethod
    def check_path_allowed(
        file_path: Path,
        allowed_paths: list[str],
        allowed_file_extensions: list[str] | None,
        blocked_paths: list[str],
        blocked_file_extensions: list[str] | None,
    ) -> None:
        """Raise ValueError(path_not_allowed) when the file fails the allow/block rules.

        Evaluation order:
          1. allowed_paths:      non-empty whitelist (caller guarantees this via validation).
          2. allowed_file_extensions: None = omitted (skip check); [] = deny all; non-empty = whitelist.
          3. blocked_paths:      [] or omitted = skip; non-empty = deny matching paths/dirs.
          4. blocked_file_extensions: [] or omitted = skip; non-empty = deny matching extensions.
        """
        # pathlib returns suffix="" for dotfiles (".gitignore") and extensionless files ("Dockerfile").
        # Fall back to the filename, ensuring a leading dot so it normalizes to the same shape
        # as a real extension and can be matched against allow/block lists.
        suffix: str = file_path.suffix.lower()
        if not suffix:
            name: str = file_path.name.lower()
            suffix = name if name.startswith(".") else f".{name}"

        # 1. allowed_paths
        if not PathAccess.path_matches_any(file_path, allowed_paths):
            raise ValueError(f"path_not_allowed: '{file_path}' is not within any of the allowed_paths entries.")

        # 2. allowed_file_extensions
        if allowed_file_extensions is not None:
            if not allowed_file_extensions:
                raise ValueError(
                    f"path_not_allowed: Extension '{suffix}' is not allowed (allowed_file_extensions is empty)."
                )
            normalized_allowed_exts: list[str] = PathAccess.normalize_extensions(allowed_file_extensions)
            if suffix not in normalized_allowed_exts:
                raise ValueError(
                    f"path_not_allowed: Extension '{suffix}' is not in "
                    f"allowed_file_extensions {allowed_file_extensions}."
                )

        # 3. blocked_paths
        if blocked_paths and PathAccess.path_matches_any(file_path, blocked_paths):
            raise ValueError(f"path_not_allowed: '{file_path}' is blocked by blocked_paths.")

        # 4. blocked_file_extensions
        if blocked_file_extensions:
            normalized_blocked_exts: list[str] = PathAccess.normalize_extensions(blocked_file_extensions)
            if suffix in normalized_blocked_exts:
                raise ValueError(
                    f"path_not_allowed: Extension '{suffix}' is in blocked_file_extensions {blocked_file_extensions}."
                )

    @staticmethod
    def normalize_extensions(extensions: list[str]) -> list[str]:
        """Return extensions normalized to lowercase with a leading dot."""
        return [e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions]

    @staticmethod
    def path_matches_any(file_path: Path, path_list: list[str]) -> bool:
        """Return True if file_path equals or is a descendant of any entry in path_list.

        Each entry is run through expanduser() and resolve(strict=False) for symmetry
        with resolve_path, so allow/block entries like '~/project' work as expected.

        An entry that cannot be resolved fails closed with invalid_input rather than
        being skipped: these lists are operator-controlled security config, and
        silently ignoring a mis-typed blocked_paths entry would fail open (a path the
        operator intended to block would be allowed).
        """
        for entry in path_list:
            try:
                candidate: Path = Path(entry).expanduser().resolve(strict=False)
            except (RuntimeError, ValueError, OSError) as exc:
                raise ValueError(f"invalid_input: Cannot resolve allow/block list entry {entry!r}: {exc}") from exc
            if file_path == candidate:
                return True
            try:
                file_path.relative_to(candidate)
                return True
            except ValueError:
                pass
        return False
