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

"""Copy agent networks plus their dependencies into a target project."""

import logging
import os
import re
import shutil
import stat
import zipfile
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import List
from typing import Set
from typing import Tuple

from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.mcp.mcp_info_merger import McpInfoMerger

# `mcp/` is whitelisted so an export-side bundle can carry the filtered mcp_info.hocon. The
# importer extracts it into memory and merges into the receiver's file additively rather than
# dropping it on disk verbatim — receivers may have already-configured URLs we must not
# overwrite (e.g. with their own `${ENV}` headers).
ALLOWED_TOP_LEVEL = ("registries/", "coded_tools/", "middleware/", "skills/", "mcp/")
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_ARCHIVE_ENTRIES = 100


def is_skippable_metadata(normalized: str) -> bool:
    """Tolerate common archive noise so a real-world zip isn't rejected over a __MACOSX entry,
    and so receivers don't end up with stray .DS_Store / __pycache__ files in their tree."""
    return (
        normalized.startswith("__MACOSX/")
        or "/.DS_Store" in normalized
        or normalized.endswith(".DS_Store")
        or "/__pycache__/" in normalized
        or normalized.endswith(".pyc")
    )


@dataclass
class ImportResult:  # pylint: disable=too-many-instance-attributes
    """Outcome of importing one agent network into the target project.

    A value object accumulating every interesting datum from one import; the breadth
    of fields reflects the breadth of an import (files copied/skipped, manifest entries,
    MCP merge deltas, warnings, errors), not a missing abstraction.
    """

    network_name: str
    hocon_path: str
    copied_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    mcp_added: List[str] = field(default_factory=list)
    mcp_skipped: List[str] = field(default_factory=list)
    # Manifest-relative HOCONs that should be registered for serving. Includes the top-level
    # network plus every transitively-imported sub-network. Distinct from copied_files because
    # copied_files also contains coded_tools/middleware/__init__.py paths that don't belong
    # in the manifest, and because skipped (already-present) HOCONs still need their key
    # ensured in the manifest if the import had to register a new entry for it.
    manifest_entries: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Roots:
    """Source/target root directories for one dependency category (registries, coded_tools, middleware)."""

    source: str
    target: str


class AgentNetworkImporter:
    """Copy agent networks (and their dependencies) from source_dir into target_dir."""

    def __init__(self, source_dir: str, target_dir: str):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.registries = _Roots(os.path.join(source_dir, "registries"), os.path.join(target_dir, "registries"))
        self.coded_tools = _Roots(os.path.join(source_dir, "coded_tools"), os.path.join(target_dir, "coded_tools"))
        self.middleware = _Roots(os.path.join(source_dir, "middleware"), os.path.join(target_dir, "middleware"))
        # mcp_info.hocon lives under <project>/mcp/. Discovery imports read the source's copy
        # (or the studio fallback) and extract only the URLs the imported network references.
        # File-mode imports get a pre-filtered mcp_info.hocon already inside the zip.
        self.mcp_source = os.path.join(source_dir, "mcp", "mcp_info.hocon")
        self.mcp_target = os.path.join(target_dir, "mcp", "mcp_info.hocon")

    # Shared registry-level HOCONs that networks pull in via `include "registries/<name>"`.
    # These aren't agent networks themselves so the dependency walker doesn't see them, but
    # almost every network in the basic/industry/experimental groups includes one. Copy them
    # alongside any imported network. (llm_config is generated fresh by `ns init`, not copied.)
    SHARED_INCLUDES = ("aaosa.hocon", "aaosa_basic.hocon", "aaosa_basic_debug.hocon")

    def _register_manifest_entry(self, result: ImportResult, registries_relative: str) -> None:
        """Append ``registries_relative`` to ``result.manifest_entries`` unless it's a shared
        include (substitution fragment, not a network). Registering one as a network would
        crash neuro-san at startup — its validator iterates the file expecting agent specs
        and a string value (e.g. ``aaosa_instructions = "..."``) blows up ``agent.get(...)``.
        """
        if os.path.basename(registries_relative) in self.SHARED_INCLUDES:
            return
        result.manifest_entries.append(registries_relative)

    def import_network(
        self,
        hocon_relative_path: str,
        dependencies: AgentNetworkDependencies,
        force: bool = False,
    ) -> ImportResult:
        """Copy the network's HOCON, sub-networks, coded tools, and middleware into the target project."""
        result = ImportResult(network_name=Path(hocon_relative_path).stem, hocon_path=hocon_relative_path)

        self._copy_hocon(hocon_relative_path, result, force=force)
        # Sub-networks are first-class agent networks — the receiver's manifest must declare
        # them so they're served. Track them alongside the top-level network so the command
        # layer can register every imported HOCON, not just the entrypoint.
        self._register_manifest_entry(result, hocon_relative_path)
        for sub_ref in dependencies.sub_networks:
            sub_name = sub_ref.lstrip("/")
            if not sub_name.endswith(".hocon"):
                sub_name += ".hocon"
            self._copy_hocon(sub_name, result, force=force)
            self._register_manifest_entry(result, sub_name)
        for coded in dependencies.coded_tools:
            self._copy_under(coded, "coded_tools", self.coded_tools, result, force=force)
        for mw in dependencies.middleware:
            self._copy_under(mw, "middleware", self.middleware, result, force=force)
        for shared in self.SHARED_INCLUDES:
            self._copy_hocon(shared, result, force=force)
        if dependencies.mcp_tools:
            self._merge_mcp_from_source(dependencies.mcp_tools, result)

        return result

    def _copy_hocon(self, relative_path: str, result: ImportResult, force: bool = False) -> None:
        source = os.path.join(self.registries.source, relative_path)
        target = os.path.join(self.registries.target, relative_path)
        if not os.path.exists(source):
            result.warnings.append(f"Source HOCON not found: {relative_path}")
            return
        self._copy_file_or_dir(source, target, relative_path, result, force=force)

    # pylint: disable-next=too-many-arguments
    def _copy_under(
        self, dep_path: str, prefix: str, roots: "_Roots", result: ImportResult, *, force: bool = False
    ) -> None:
        rel = dep_path[len(prefix) + 1 :] if dep_path.startswith(prefix + "/") else dep_path
        source = os.path.join(roots.source, rel)
        target = os.path.join(roots.target, rel)
        if not os.path.exists(source):
            result.warnings.append(f"Dependency not found: {dep_path}")
            return
        self._copy_file_or_dir(source, target, dep_path, result, force=force)
        if os.path.isfile(source):
            self._copy_parent_inits(os.path.dirname(source), roots, result, force=force)

    @staticmethod
    def _copy_file_or_dir(source: str, target: str, display: str, result: ImportResult, force: bool = False) -> None:
        if os.path.exists(target) and not force:
            result.skipped_files.append(display)
            return
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.isdir(source):
                # dirs_exist_ok lets force overwrite existing trees file-by-file.
                shutil.copytree(source, target, dirs_exist_ok=force)
            else:
                shutil.copy2(source, target)
            result.copied_files.append(display)
        except OSError as exc:
            result.errors.append(f"Failed to copy {display}: {exc}")

    @staticmethod
    def _copy_parent_inits(current_dir: str, roots: "_Roots", result: ImportResult, force: bool = False) -> None:
        """Copy __init__.py up the parent chain so the package is importable in the target."""
        while current_dir.startswith(roots.source) and current_dir != roots.source:
            init_src = os.path.join(current_dir, "__init__.py")
            if os.path.exists(init_src):
                rel = os.path.relpath(init_src, roots.source)
                init_dst = os.path.join(roots.target, rel)
                if force or not os.path.exists(init_dst):
                    try:
                        os.makedirs(os.path.dirname(init_dst), exist_ok=True)
                        shutil.copy2(init_src, init_dst)
                        result.copied_files.append(os.path.join(os.path.basename(roots.target), rel))
                    except OSError as exc:
                        result.errors.append(f"Failed to copy __init__.py: {exc}")
            current_dir = os.path.dirname(current_dir)

    def import_from_path(self, source_path: str, force: bool = False) -> ImportResult:
        """Import a single network from a local file path.

        A `.hocon` is treated as self-contained and lands at `<target>/registries/<basename>`.
        A `.zip` is treated as a closed bundle whose layout is preserved verbatim under the
        top-level whitelist (`registries/`, `coded_tools/`, `middleware/`, `skills/`).
        """
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"File not found: {source_path}")
        suffix = os.path.splitext(source_path)[1].lower()

        if suffix == ".hocon":
            basename = os.path.basename(source_path)
            result = ImportResult(network_name=Path(basename).stem, hocon_path=basename)
            target = os.path.join(self.registries.target, basename)
            self._copy_file_or_dir(source_path, target, basename, result, force=force)
            # The file lands at registries/<basename> and should be registered, even when
            # the target already exists (skip path) — re-running an import shouldn't drop
            # an entry that earlier failed to make it into the manifest.
            self._register_manifest_entry(result, basename)
            return result

        if suffix == ".zip":
            return self._import_from_zip(source_path, force=force)

        raise ValueError(f"Unsupported file type: {suffix or '(none)'}. Expected .hocon or .zip")

    def _import_from_zip(self, zip_path: str, force: bool = False) -> ImportResult:
        """Validate then extract a zip bundle into the target project.

        Validation runs over every entry up front; extraction only proceeds when all
        entries pass. This avoids leaving the project half-imported on rejection.
        ``mcp/mcp_info.hocon`` is special-cased: instead of dropping the file verbatim
        we additively merge its URL blocks into the receiver's mcp_info, so the receiver's
        already-configured servers are never silently overwritten regardless of ``force``.
        """
        result = ImportResult(network_name=Path(zip_path).stem, hocon_path=os.path.basename(zip_path))
        with zipfile.ZipFile(zip_path) as zf:
            entries = [info for info in zf.infolist() if not info.is_dir()]
            self._validate_zip_entries(entries)
            for info in entries:
                rel = info.filename
                normalized, _ = self._normalize_zip_path(rel)
                if not normalized.startswith(ALLOWED_TOP_LEVEL) or is_skippable_metadata(normalized):
                    # Tolerated by validation (metadata, __pycache__) but not part of the bundle's
                    # real content — silently drop instead of polluting the receiver's tree.
                    continue
                if normalized == "mcp/mcp_info.hocon":
                    # Always merge — never overwrite the receiver's mcp_info, even with --force.
                    # The receiver's configured `${ENV}` references must not be clobbered.
                    payload = zf.read(info).decode("utf-8")
                    self._merge_mcp_text(payload, result)
                    continue
                target = os.path.join(self.target_dir, rel)
                # Track every bundled registry HOCON for manifest registration — including
                # skipped (already-present) ones, so re-running with the same bundle still
                # ensures the entry exists in the receiver's manifest.
                if normalized.startswith("registries/") and normalized.endswith(".hocon"):
                    self._register_manifest_entry(result, normalized[len("registries/") :])
                if os.path.exists(target) and not force:
                    result.skipped_files.append(rel)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                result.copied_files.append(rel)
        return result

    @staticmethod
    def _validate_zip_entries(entries: List[zipfile.ZipInfo]) -> None:
        """Run the four safety checks; raise ValueError on the first failure."""
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise ValueError(f"Archive has too many entries ({len(entries)} > {MAX_ARCHIVE_ENTRIES}).")
        total_size = 0
        for info in entries:
            total_size += info.file_size
            if total_size > MAX_ARCHIVE_BYTES:
                raise ValueError(f"Archive exceeds size limit ({MAX_ARCHIVE_BYTES} bytes uncompressed).")
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ValueError(f"Archive contains a symlink entry: {info.filename}")
            normalized, escapes = AgentNetworkImporter._normalize_zip_path(info.filename)
            if escapes:
                raise ValueError(f"Archive entry escapes target root (zip-slip): {info.filename}")
            if normalized.startswith(ALLOWED_TOP_LEVEL) or is_skippable_metadata(normalized):
                continue
            raise ValueError(
                f"Archive entry not in whitelist (registries/, coded_tools/, middleware/, skills/): {info.filename}"
            )

    @staticmethod
    def _normalize_zip_path(name: str) -> Tuple[str, bool]:
        """Return (normalized-relative-path, escapes_root). escapes_root is True for any absolute,
        traversal, or backslash-encoded path that resolves outside the target root."""
        if name.startswith(("/", "\\")) or ":" in name.split("/", 1)[0]:
            return name, True
        normalized = os.path.normpath(name).replace("\\", "/")
        if normalized.startswith("../") or normalized == ".." or "/../" in normalized:
            return normalized, True
        return normalized, False

    def _merge_mcp_from_source(self, mcp_urls: List[str], result: ImportResult) -> None:
        """Discovery-mode merge: pull entries for ``mcp_urls`` from the source's mcp_info.hocon
        and additively merge them into the target's mcp_info.hocon.

        Falls back to the studio package's bundled mcp_info if the source project hasn't
        scaffolded one — same precedence as ``ns run`` uses to find the active config.
        """
        source_path = self._resolve_mcp_source_path()
        if not source_path:
            result.warnings.append(f"MCP refs found ({', '.join(mcp_urls)}) but no source mcp_info.hocon located.")
            return
        with open(source_path, encoding="utf-8") as fh:
            source_text = fh.read()
        blocks = McpInfoMerger().filter_blocks(source_text, mcp_urls)
        missing = [url for url in mcp_urls if url not in blocks]
        if missing:
            result.warnings.append(f"MCP server(s) not found in {source_path}: {', '.join(missing)}")
        if not blocks:
            return
        self._splice_mcp_blocks(blocks, result)

    def _merge_mcp_text(self, payload: str, result: ImportResult) -> None:
        """File-mode merge: parse blocks out of the bundled mcp_info text and splice them in."""
        blocks = McpInfoMerger().extract_blocks(payload)
        if not blocks:
            return
        self._splice_mcp_blocks(blocks, result)

    def _splice_mcp_blocks(self, blocks: dict, result: ImportResult) -> None:
        """Read the receiver's mcp_info, additively merge ``blocks``, and write the result.

        If the receiver has no mcp_info.hocon yet, we render a fresh file containing only
        the new blocks. Existing URLs are never overwritten — that's the additive contract.
        """
        os.makedirs(os.path.dirname(self.mcp_target), exist_ok=True)
        merger = McpInfoMerger()
        if os.path.isfile(self.mcp_target):
            with open(self.mcp_target, encoding="utf-8") as fh:
                receiver_text = fh.read()
            new_text, added, skipped = merger.merge(receiver_text, blocks)
        else:
            new_text = merger.render_file(blocks)
            added, skipped = list(blocks.keys()), []
        with open(self.mcp_target, "w", encoding="utf-8") as fh:
            fh.write(new_text)
        result.mcp_added.extend(added)
        result.mcp_skipped.extend(skipped)

    def _resolve_mcp_source_path(self) -> str:
        """Source project's mcp_info.hocon if present, otherwise the bundled studio fallback."""
        if os.path.isfile(self.mcp_source):
            return self.mcp_source
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio import mcp as _mcp_pkg

        bundled = os.path.join(os.path.dirname(_mcp_pkg.__file__), "mcp_info.hocon")
        return bundled if os.path.isfile(bundled) else ""

    def update_manifest(self, imported_networks: List[str]) -> None:
        """Additively register ``imported_networks`` in ``registries/manifest.hocon``.

        The manifest is HOCON, not JSON: it can contain comments and ``include "..."``
        directives (notably ``include "registries/generated/manifest.hocon"`` from the
        scaffold) plus any user edits. We preserve all of that by splicing new
        ``"<path>": true`` lines before the closing ``}`` rather than re-emitting parsed
        structure. Existing keys are never rewritten — even with ``--force`` — so a
        previously-declared network's truthy value is left alone.
        """
        manifest_path = os.path.join(self.registries.target, "manifest.hocon")
        os.makedirs(self.registries.target, exist_ok=True)

        new_entries = list(dict.fromkeys(imported_networks))  # de-dupe, keep order
        if not new_entries:
            return

        if not os.path.isfile(manifest_path):
            with open(manifest_path, "w", encoding="utf-8") as fh:
                fh.write(self._render_fresh_manifest(new_entries))
            return

        with open(manifest_path, encoding="utf-8") as fh:
            existing_text = fh.read()

        existing_keys = self._read_existing_keys(manifest_path)
        to_add = [name for name in new_entries if name not in existing_keys]
        if not to_add:
            return

        new_text = self._splice_manifest_entries(existing_text, to_add)
        with open(manifest_path, "w", encoding="utf-8") as fh:
            fh.write(new_text)

    @staticmethod
    def _render_fresh_manifest(entries: List[str]) -> str:
        """Render a brand-new manifest.hocon containing exactly ``entries`` (sorted, JSON-shaped)."""
        body_lines = [f'    "{name}": true' for name in sorted(set(entries))]
        return "{\n" + ",\n".join(body_lines) + "\n}\n"

    @staticmethod
    def _read_existing_keys(manifest_path: str) -> Set[str]:
        """Return the set of HOCON keys already declared by the manifest (resolves ``include``s).

        Uses ``RawManifestRestorer`` so includes are followed; falls back to a regex scan if
        pyhocon can't parse the file (e.g. a hand-edited manifest with malformed syntax).
        """
        # pyhocon resolves include directives relative to CWD, so chdir into the target's
        # registries dir while reading. Demote pyhocon's chatty error logging during the read
        # so a parse failure here doesn't pollute the import output.
        registries_dir = os.path.dirname(manifest_path)
        prev_cwd = os.getcwd()
        prev_level = logging.getLogger("pyhocon.config_parser").level
        try:
            os.chdir(os.path.dirname(registries_dir) or ".")
            logging.getLogger("pyhocon.config_parser").setLevel(logging.CRITICAL)
            raw = RawManifestRestorer().restore(file_reference=manifest_path)
        except Exception:  # pylint: disable=broad-except
            return AgentNetworkImporter._regex_scan_keys(manifest_path)
        finally:
            logging.getLogger("pyhocon.config_parser").setLevel(prev_level)
            os.chdir(prev_cwd)
        return {key.strip('"') for key in raw if isinstance(key, str)}

    @staticmethod
    def _regex_scan_keys(manifest_path: str) -> Set[str]:
        """Best-effort fallback: scrape ``"key": true|false`` lines without invoking pyhocon."""
        try:
            with open(manifest_path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return set()
        return set(re.findall(r'"([^"\n]+\.hocon)"\s*[:=]', text))

    @staticmethod
    def _splice_manifest_entries(existing_text: str, new_entries: List[str]) -> str:
        """Insert ``"name": true`` lines before the manifest's closing ``}``.

        Preserves every byte of the existing text that isn't whitespace/comma adjustment around
        the closing brace, so includes, comments, and pre-existing entries (with whatever
        truthy value they had — ``true``, ``"on"``, etc.) survive verbatim. A leading comma
        is added when the previous content needs one to keep the dict well-formed.
        """
        last_brace = existing_text.rfind("}")
        if last_brace == -1:
            # No outer dict at all — wrap fresh, but keep the original text as a leading comment
            # so the user can recover anything we might be misreading.
            return AgentNetworkImporter._render_fresh_manifest(new_entries)

        head = existing_text[:last_brace].rstrip()
        tail = existing_text[last_brace:]
        last_meaningful = head.rstrip().rstrip("\n").rstrip()[-1:] if head.strip() else ""
        needs_comma = last_meaningful not in ("", ",", "{")
        sep = ",\n" if needs_comma else "\n"
        added_lines = ",\n".join(f'    "{name}": true' for name in new_entries)
        return head + sep + added_lines + "\n" + tail
