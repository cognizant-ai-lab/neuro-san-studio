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

from pathlib import Path
from typing import Any

from neuro_san_studio.coded_tools.file_management.path_access import PathAccess


# pylint: disable=too-few-public-methods
class PathRules:
    """
    The operator's allow/block rules, validated and resolved once for reuse.

    PathAccess.validate_and_check_access re-validates the four rule lists and
    re-resolves every allow/block path entry (filesystem syscalls) on each call —
    fine for a tool checking one target, prohibitive for tools that filter every
    entry of a directory tree (list_directory, and later file_search/grep). This
    class does that work once up front, then answers per-path questions with pure
    lookups and no exceptions, so a large scan costs O(entries) instead of
    O(entries x rule entries).

    Parsing failures (malformed or unresolvable rule entries) raise invalid_input
    at construction time, so a bad operator config fails the call loudly before
    any enumeration starts — never midway through a scan.

    Rule semantics match PathAccess.check_path_allowed, with one extension for
    enumerated entries: extension rules are evaluated against every candidate
    suffix handed to deny_reason (the displayed entry name and the resolved
    target's name, which differ for symlinks). The allow-list must pass for ALL
    candidate suffixes and the block-list must pass for EACH (fail-closed), so a
    symlink cannot dodge a block rule under either of its names.
    """

    def __init__(self, args: dict[str, Any]):
        """Validate and pre-resolve the rule lists from the tool args.

        :param args: The tool argument dictionary carrying allowed_paths (required),
                allowed_file_extensions, blocked_paths, and blocked_file_extensions.
        :raises ValueError: invalid_input when a rule list is malformed, empty where
                required, contains blank entries, or contains an unresolvable path.
        """
        self._allowed_paths: list[Path] = self._resolve_entries(PathAccess.validate_allowed_paths(args))
        self._blocked_paths: list[Path] = self._resolve_entries(
            PathAccess.validate_path_list(args.get("blocked_paths"), "blocked_paths")
        )

        allowed_exts: list[str] | None = PathAccess.validate_extension_list(
            args.get("allowed_file_extensions"), "allowed_file_extensions"
        )
        blocked_exts: list[str] | None = PathAccess.validate_extension_list(
            args.get("blocked_file_extensions"), "blocked_file_extensions"
        )
        # None = omitted (no filtering); an empty allow-set denies all files.
        self._allowed_extensions: frozenset[str] | None = (
            None if allowed_exts is None else frozenset(PathAccess.normalize_extensions(allowed_exts))
        )
        self._blocked_extensions: frozenset[str] = frozenset(
            PathAccess.normalize_extensions(blocked_exts) if blocked_exts else []
        )

    def deny_reason(self, resolved: Path, display_name: str, is_directory: bool) -> str | None:
        """Return a short reason when the path fails the rules, or None when allowed.

        :param resolved: The fully resolved path of the entry (symlinks followed),
                so path rules confine symlink targets, not just link locations.
        :param display_name: The entry name as it would appear in output. Extension
                rules check this name AND the resolved name, so what the operator's
                rules match is never hidden behind a differently-named symlink.
        :param is_directory: True when the resolved target is a directory. Directories
                are exempt from the extension ALLOW-list (they have no meaningful
                extension for a file-oriented whitelist) but never from block rules.

        Evaluation order mirrors PathAccess.check_path_allowed. Returns a reason
        string rather than raising: enumeration callers treat any deny as "omit
        this entry", and building/catching exceptions per denied entry is pure
        overhead at directory scale.
        """
        if not any(resolved.is_relative_to(candidate) for candidate in self._allowed_paths):
            return "outside_allowed_paths"

        suffixes: set[str] = {PathAccess.effective_suffix(display_name), PathAccess.effective_suffix(resolved.name)}

        if not is_directory and self._allowed_extensions is not None:
            if not suffixes.issubset(self._allowed_extensions):
                return "extension_not_allowed"

        if any(resolved.is_relative_to(candidate) for candidate in self._blocked_paths):
            return "blocked_path"

        if suffixes & self._blocked_extensions:
            return "blocked_extension"

        return None

    @staticmethod
    def _resolve_entries(entries: list[str]) -> list[Path]:
        """Resolve rule-list entries once, failing closed on any unresolvable entry."""
        resolved: list[Path] = []
        for entry in entries:
            try:
                resolved.append(Path(entry).expanduser().resolve(strict=False))
            except (RuntimeError, ValueError, OSError) as exc:
                raise ValueError(f"invalid_input: Cannot resolve allow/block list entry {entry!r}: {exc}") from exc
        return resolved
