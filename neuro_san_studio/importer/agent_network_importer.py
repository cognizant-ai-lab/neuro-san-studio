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

import json
import os
import shutil
import stat
import zipfile
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import List
from typing import Tuple

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies

ALLOWED_TOP_LEVEL = ("registries/", "coded_tools/", "middleware/", "skills/")
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_ARCHIVE_ENTRIES = 100


@dataclass
class ImportResult:
    """Outcome of importing one agent network into the target project."""

    network_name: str
    hocon_path: str
    copied_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


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

    # Shared registry-level HOCONs that networks pull in via `include "registries/<name>"`.
    # These aren't agent networks themselves so the dependency walker doesn't see them, but
    # almost every network in the basic/industry/experimental groups includes one. Copy them
    # alongside any imported network. (llm_config is generated fresh by `ns init`, not copied.)
    SHARED_INCLUDES = ("aaosa.hocon", "aaosa_basic.hocon", "aaosa_basic_debug.hocon")

    def import_network(
        self,
        hocon_relative_path: str,
        dependencies: AgentNetworkDependencies,
        force: bool = False,
    ) -> ImportResult:
        """Copy the network's HOCON, sub-networks, coded tools, and middleware into the target project."""
        result = ImportResult(network_name=Path(hocon_relative_path).stem, hocon_path=hocon_relative_path)

        self._copy_hocon(hocon_relative_path, result, force=force)
        for sub_ref in dependencies.sub_networks:
            sub_name = sub_ref.lstrip("/")
            if not sub_name.endswith(".hocon"):
                sub_name += ".hocon"
            self._copy_hocon(sub_name, result, force=force)
        for coded in dependencies.coded_tools:
            self._copy_under(coded, "coded_tools", self.coded_tools, result, force=force)
        for mw in dependencies.middleware:
            self._copy_under(mw, "middleware", self.middleware, result, force=force)
        for shared in self.SHARED_INCLUDES:
            self._copy_hocon(shared, result, force=force)

        return result

    def _copy_hocon(self, relative_path: str, result: ImportResult, force: bool = False) -> None:
        source = os.path.join(self.registries.source, relative_path)
        target = os.path.join(self.registries.target, relative_path)
        if not os.path.exists(source):
            result.warnings.append(f"Source HOCON not found: {relative_path}")
            return
        self._copy_file_or_dir(source, target, relative_path, result, force=force)

    def _copy_under(
        self, dep_path: str, prefix: str, roots: "_Roots", result: ImportResult, force: bool = False
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
    def _copy_file_or_dir(
        source: str, target: str, display: str, result: ImportResult, force: bool = False
    ) -> None:
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
    def _copy_parent_inits(
        current_dir: str, roots: "_Roots", result: ImportResult, force: bool = False
    ) -> None:
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
            return result

        if suffix == ".zip":
            return self._import_from_zip(source_path, force=force)

        raise ValueError(f"Unsupported file type: {suffix or '(none)'}. Expected .hocon or .zip")

    def _import_from_zip(self, zip_path: str, force: bool = False) -> ImportResult:
        """Validate then extract a zip bundle into the target project.

        Validation runs over every entry up front; extraction only proceeds when all
        entries pass. This avoids leaving the project half-imported on rejection.
        """
        result = ImportResult(network_name=Path(zip_path).stem, hocon_path=os.path.basename(zip_path))
        with zipfile.ZipFile(zip_path) as zf:
            entries = [info for info in zf.infolist() if not info.is_dir()]
            self._validate_zip_entries(entries)
            for info in entries:
                rel = info.filename
                normalized, _ = self._normalize_zip_path(rel)
                if not normalized.startswith(ALLOWED_TOP_LEVEL) or self._is_skippable_metadata(normalized):
                    # Tolerated by validation (metadata, __pycache__) but not part of the bundle's
                    # real content — silently drop instead of polluting the receiver's tree.
                    continue
                target = os.path.join(self.target_dir, rel)
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
            raise ValueError(
                f"Archive has too many entries ({len(entries)} > {MAX_ARCHIVE_ENTRIES})."
            )
        total_size = 0
        for info in entries:
            total_size += info.file_size
            if total_size > MAX_ARCHIVE_BYTES:
                raise ValueError(
                    f"Archive exceeds size limit ({MAX_ARCHIVE_BYTES} bytes uncompressed)."
                )
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ValueError(f"Archive contains a symlink entry: {info.filename}")
            normalized, escapes = AgentNetworkImporter._normalize_zip_path(info.filename)
            if escapes:
                raise ValueError(f"Archive entry escapes target root (zip-slip): {info.filename}")
            if normalized.startswith(ALLOWED_TOP_LEVEL) or AgentNetworkImporter._is_skippable_metadata(normalized):
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

    @staticmethod
    def _is_skippable_metadata(normalized: str) -> bool:
        """Tolerate common archive noise so a real-world zip isn't rejected over a __MACOSX entry,
        and so receivers don't end up with stray .DS_Store / __pycache__ files in their tree."""
        return (
            normalized.startswith("__MACOSX/")
            or "/.DS_Store" in normalized
            or normalized.endswith(".DS_Store")
            or "/__pycache__/" in normalized
            or normalized.endswith(".pyc")
        )

    def update_manifest(self, imported_networks: List[str]) -> None:
        """Merge new entries into target registries/manifest.hocon (always JSON-formatted)."""
        manifest_path = os.path.join(self.registries.target, "manifest.hocon")
        os.makedirs(self.registries.target, exist_ok=True)

        existing: dict = {}
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as fh:
                content = fh.read().strip()
            if content:
                try:
                    existing = json.loads(content)
                except json.JSONDecodeError:
                    # Source was HOCON-style or malformed; start fresh rather than corrupt it
                    existing = {}

        for path in imported_networks:
            existing[path] = True

        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(dict(sorted(existing.items())), fh, indent=4)
            fh.write("\n")
