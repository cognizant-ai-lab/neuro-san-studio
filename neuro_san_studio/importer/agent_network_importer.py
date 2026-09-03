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
from functools import cached_property
from pathlib import Path
from typing import Callable
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer
from neuro_san_studio.importer.bulk_import_result import BulkImportResult
from neuro_san_studio.importer.import_result import ImportResult
from neuro_san_studio.importer.import_roots import ImportRoots
from neuro_san_studio.mcp.mcp_info_merger import McpInfoMerger
from neuro_san_studio.utils.shared_registries import SHARED_REGISTRY_INCLUDES


class AgentNetworkImporter:
    """Copy agent networks (and their dependencies) from source_dir into target_dir."""

    # `mcp/` is whitelisted so an export-side bundle can carry the filtered mcp_info.hocon. The
    # importer extracts it into memory and merges into the receiver's file additively rather than
    # dropping it on disk verbatim — receivers may have already-configured URLs we must not
    # overwrite (e.g. with their own `${ENV}` headers).
    ALLOWED_TOP_LEVEL = ("registries/", "coded_tools/", "middleware/", "skills/", "mcp/")
    MAX_ARCHIVE_BYTES = 100 * 1024 * 1024  # 100 MB
    MAX_ARCHIVE_ENTRIES = 100

    @staticmethod
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

    def __init__(self, source_dir: str, target_dir: str):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.registries = ImportRoots(os.path.join(source_dir, "registries"), os.path.join(target_dir, "registries"))
        self.coded_tools = ImportRoots(
            os.path.join(source_dir, "coded_tools"), os.path.join(target_dir, "coded_tools")
        )
        self.middleware = ImportRoots(os.path.join(source_dir, "middleware"), os.path.join(target_dir, "middleware"))
        # mcp_info.hocon lives under <project>/mcp/. Discovery imports read the source's copy
        # (or the studio fallback) and extract only the URLs the imported network references.
        # File-mode imports get a pre-filtered mcp_info.hocon already inside the zip.
        self.mcp_source = os.path.join(source_dir, "mcp", "mcp_info.hocon")
        self.mcp_target = os.path.join(target_dir, "mcp", "mcp_info.hocon")

    @cached_property
    def analyzer(self) -> DependencyAnalyzer:
        """Dependency walker over the source tree.

        Its three roots are exactly the source roots computed in `__init__`, so the importer
        owns it rather than making every caller rebuild the same object. Built on first use:
        a file-mode import (`import_from_path`) is self-contained and never walks
        dependencies, and there `source_dir` is the target project, where an analyzer would
        mean nothing.
        """
        return DependencyAnalyzer(self.registries.source, self.coded_tools.source, self.middleware.source)

    # Shared registry-level HOCONs that networks pull in via `include "registries/<name>"`.
    # These aren't agent networks themselves so the dependency walker doesn't see them, but
    # almost every network in the basic/industry/experimental groups includes one. Copy them
    # alongside any imported network. (llm_config is generated fresh by `ns init`, not copied.)
    # Defined in neuro_san_studio.utils.shared_registries so `ns init` scaffolds exactly the
    # same set — the two lists used to be maintained separately and drifted.
    SHARED_INCLUDES = SHARED_REGISTRY_INCLUDES

    def _register_manifest_entry(self, result: ImportResult, registries_relative: str) -> None:
        """Append ``registries_relative`` to ``result.manifest_entries`` unless it's a shared
        include (substitution fragment, not a network). Registering one as a network would
        crash neuro-san at startup — its validator iterates the file expecting agent specs
        and a string value (e.g. ``aaosa_instructions = "..."``) blows up ``agent.get(...)``.
        """
        if os.path.basename(registries_relative) in self.SHARED_INCLUDES:
            return
        result.manifest_entries.append(registries_relative)

    def import_networks(
        self,
        hocon_paths: List[str],
        *,
        force: bool = False,
        on_network: Optional[Callable[[str], None]] = None,
    ) -> BulkImportResult:
        """Analyze and import each of `hocon_paths` (registry-relative) from the source tree.

        A network that fails to analyze or import is recorded and skipped rather than raised:
        a batch missing one network is still useful, while a half-written project is not.
        `on_network` is invoked with each path before its work starts, so a CLI can report
        progress without this method knowing anything about how progress is displayed.

        Deliberately does NOT touch the manifest. `ns import` registers `manifest_entries`
        afterwards; `ns init` must not, because it scaffolds its manifest from a template
        that declares support networks as `{"serve": true, "public": false}` and
        `update_manifest` would flatten those to a bare `true`.
        """
        bulk = BulkImportResult()
        for hocon_path in hocon_paths:
            if on_network is not None:
                on_network(hocon_path)
            full_path = os.path.join(self.registries.source, hocon_path)
            try:
                dependencies = self.analyzer.get_transitive_dependencies(full_path)
            except (OSError, ValueError) as exc:
                bulk.errors.append(f"Failed to analyze {hocon_path}: {exc}")
                continue
            try:
                bulk.results.append(self.import_network(hocon_path, dependencies, force=force))
            except (OSError, ValueError) as exc:
                bulk.errors.append(f"Failed to import {hocon_path}: {exc}")
        return bulk

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
        self._ensure_package_roots(result)

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
        self, dep_path: str, prefix: str, roots: ImportRoots, result: ImportResult, *, force: bool = False
    ) -> None:
        rel = dep_path[len(prefix) + 1 :] if dep_path.startswith(prefix + "/") else dep_path
        source = os.path.join(roots.source, rel)
        target = os.path.join(roots.target, rel)
        if not os.path.exists(source):
            result.warnings.append(f"Dependency not found: {dep_path}")
            return
        self._copy_file_or_dir(source, target, dep_path, result, force=force)
        # A directory dependency is its own starting point; a file's package chain starts at
        # the directory holding it.
        self._copy_parent_inits(
            source if os.path.isdir(source) else os.path.dirname(source), roots, result, force=force
        )

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
    def _copy_parent_inits(current_dir: str, roots: ImportRoots, result: ImportResult, force: bool = False) -> None:
        """Copy __init__.py up the parent chain so the package is importable in the target.

        The chain includes the root itself (``coded_tools/__init__.py``,
        ``middleware/__init__.py``). Without it the target's directory is only a namespace
        *portion*, and Python's finder skips namespace portions in favor of any regular package
        of the same name further along sys.path — which for a pip-installed project is
        neuro-san-studio's own bundled copy. The project's coded tools would then be silently
        shadowed by the installed ones, no matter that the project root comes first on the path.
        """
        while current_dir.startswith(roots.source):
            init_src = os.path.join(current_dir, "__init__.py")
            if os.path.exists(init_src):
                rel = os.path.relpath(init_src, roots.source)
                init_dst = os.path.join(roots.target, rel)
                if force or not os.path.exists(init_dst):
                    try:
                        os.makedirs(os.path.dirname(init_dst), exist_ok=True)
                        shutil.copy2(init_src, init_dst)
                        # Record with forward slashes regardless of platform: every other
                        # display uses "/", and downstream bookkeeping (`_touched_under`)
                        # compares displays as "/"-separated strings.
                        display = os.path.join(os.path.basename(roots.target), rel).replace(os.sep, "/")
                        result.copied_files.append(display)
                    except OSError as exc:
                        result.errors.append(f"Failed to copy __init__.py: {exc}")
            if current_dir == roots.source:
                break
            current_dir = os.path.dirname(current_dir)

    def _ensure_package_roots(self, result: ImportResult) -> None:
        """Guarantee coded_tools/ and middleware/ are regular packages in the target.

        `_copy_parent_inits` covers this whenever the source has an ``__init__.py`` to copy and
        a dependency lands under that root. This is the fallback for when neither holds: a zip
        bundle that omitted the root file (the zip path extracts verbatim and never walks the
        parent chain), or a source tree whose own root is a namespace package. See
        `_copy_parent_inits` for why a namespace *portion* here silently shadows the project.

        Only ever creates an empty file, never copies: if the source had one to give,
        `_copy_parent_inits` already delivered it. Deliberately does not create the directory
        -- the contract is "if we put files there, make it importable", not "every project
        gets a coded_tools/". The same contract is why a root this import never touched is
        left alone: a self-contained .hocon import must not convert a target's intentional
        namespace-package coded_tools/ into a regular package as a side effect.
        """
        for roots in (self.coded_tools, self.middleware):
            # Skipped files count as "touched" too: on a re-run of the same import, the files
            # are already in place and a missing root __init__.py should still be healed.
            if not self._touched_under(result, os.path.basename(roots.target) + "/"):
                continue
            target = os.path.join(roots.target, "__init__.py")
            if os.path.exists(target) or not os.path.isdir(roots.target):
                continue
            try:
                with open(target, "w", encoding="utf-8"):
                    pass
            except OSError as exc:
                result.errors.append(f"Failed to create {target}: {exc}")
                continue
            result.copied_files.append(f"{os.path.basename(roots.target)}/__init__.py")

    @staticmethod
    def _touched_under(result: ImportResult, prefix: str) -> bool:
        """
        Whether this import copied or skipped anything under the given root prefix.

        Skips count: a skipped file proves the import *wanted* to place content there, so the
        root is part of this import's footprint even when every file already existed.

        :param result: The in-progress import outcome to inspect.
        :param prefix: Root-relative display prefix, e.g. ``"coded_tools/"``.
        :return: True when any copied or skipped display path starts with ``prefix``.
        """
        for copied_file in result.copied_files:
            if copied_file.startswith(prefix):
                return True
        for skipped_file in result.skipped_files:
            if skipped_file.startswith(prefix):
                return True
        return False

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
            self._ensure_package_roots(result)
            return result

        if suffix == ".zip":
            result = self._import_from_zip(source_path, force=force)
            self._ensure_package_roots(result)
            return result

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
                if not normalized.startswith(
                    AgentNetworkImporter.ALLOWED_TOP_LEVEL
                ) or AgentNetworkImporter.is_skippable_metadata(normalized):
                    # Tolerated by validation (metadata, __pycache__) but not part of the bundle's
                    # real content — silently drop instead of polluting the receiver's tree.
                    continue
                if normalized == "mcp/mcp_info.hocon":
                    # Always merge — never overwrite the receiver's mcp_info, even with --force.
                    # The receiver's configured `${ENV}` references must not be clobbered.
                    payload = zf.read(info).decode("utf-8")
                    self._merge_mcp_text(payload, result)
                    continue
                # Extract to — and record — the normalized path, not the raw entry name.
                # A zip may spell entries "./coded_tools/tool.py" or (from a Windows builder)
                # "coded_tools\\tool.py"; validation normalizes only its whitelist check, so
                # raw names would land odd paths on disk and leave displays that downstream
                # bookkeeping (`_touched_under`) cannot match against.
                target = os.path.join(self.target_dir, normalized)
                # Track every bundled registry HOCON for manifest registration — including
                # skipped (already-present) ones, so re-running with the same bundle still
                # ensures the entry exists in the receiver's manifest.
                if normalized.startswith("registries/") and normalized.endswith(".hocon"):
                    self._register_manifest_entry(result, normalized[len("registries/") :])
                if os.path.exists(target) and not force:
                    result.skipped_files.append(normalized)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                result.copied_files.append(normalized)
        return result

    @staticmethod
    def _validate_zip_entries(entries: List[zipfile.ZipInfo]) -> None:
        """Run the four safety checks; raise ValueError on the first failure."""
        if len(entries) > AgentNetworkImporter.MAX_ARCHIVE_ENTRIES:
            raise ValueError(
                f"Archive has too many entries ({len(entries)} > {AgentNetworkImporter.MAX_ARCHIVE_ENTRIES})."
            )
        total_size = 0
        for info in entries:
            total_size += info.file_size
            if total_size > AgentNetworkImporter.MAX_ARCHIVE_BYTES:
                raise ValueError(
                    f"Archive exceeds size limit ({AgentNetworkImporter.MAX_ARCHIVE_BYTES} bytes uncompressed)."
                )
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ValueError(f"Archive contains a symlink entry: {info.filename}")
            normalized, escapes = AgentNetworkImporter._normalize_zip_path(info.filename)
            if escapes:
                raise ValueError(f"Archive entry escapes target root (zip-slip): {info.filename}")
            if normalized.startswith(
                AgentNetworkImporter.ALLOWED_TOP_LEVEL
            ) or AgentNetworkImporter.is_skippable_metadata(normalized):
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
