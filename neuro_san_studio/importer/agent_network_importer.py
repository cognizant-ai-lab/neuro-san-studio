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
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import List

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies


@dataclass
class ImportResult:
    """Outcome of importing one agent network into the target project."""

    network_name: str
    hocon_path: str
    copied_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class AgentNetworkImporter:
    """Copy agent networks (and their dependencies) from source_dir into target_dir."""

    def __init__(self, source_dir: str, target_dir: str):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.source_registries = os.path.join(source_dir, "registries")
        self.source_coded_tools = os.path.join(source_dir, "coded_tools")
        self.source_middleware = os.path.join(source_dir, "middleware")
        self.target_registries = os.path.join(target_dir, "registries")
        self.target_coded_tools = os.path.join(target_dir, "coded_tools")
        self.target_middleware = os.path.join(target_dir, "middleware")

    # Shared registry-level HOCONs that networks pull in via `include "registries/<name>"`.
    # These aren't agent networks themselves so the dependency walker doesn't see them, but
    # almost every network in the basic/industry/experimental groups includes one. Copy them
    # alongside any imported network. (llm_config is generated fresh by `ns init`, not copied.)
    SHARED_INCLUDES = ("aaosa.hocon", "aaosa_basic.hocon", "aaosa_basic_debug.hocon")

    def import_network(self, hocon_relative_path: str, dependencies: AgentNetworkDependencies) -> ImportResult:
        """Copy the network's HOCON, sub-networks, coded tools, and middleware into the target project."""
        result = ImportResult(network_name=Path(hocon_relative_path).stem, hocon_path=hocon_relative_path)

        self._copy_hocon(hocon_relative_path, result)
        for sub_ref in dependencies.sub_networks:
            sub_name = sub_ref.lstrip("/")
            if not sub_name.endswith(".hocon"):
                sub_name += ".hocon"
            self._copy_hocon(sub_name, result)
        for coded in dependencies.coded_tools:
            self._copy_under(coded, "coded_tools", self.source_coded_tools, self.target_coded_tools, result)
        for mw in dependencies.middleware:
            self._copy_under(mw, "middleware", self.source_middleware, self.target_middleware, result)
        for shared in self.SHARED_INCLUDES:
            self._copy_hocon(shared, result)

        return result

    def _copy_hocon(self, relative_path: str, result: ImportResult) -> None:
        source = os.path.join(self.source_registries, relative_path)
        target = os.path.join(self.target_registries, relative_path)
        if not os.path.exists(source):
            result.warnings.append(f"Source HOCON not found: {relative_path}")
            return
        self._copy_file_or_dir(source, target, relative_path, result)

    def _copy_under(
        self,
        dep_path: str,
        prefix: str,
        source_root: str,
        target_root: str,
        result: ImportResult,
    ) -> None:
        rel = dep_path[len(prefix) + 1 :] if dep_path.startswith(prefix + "/") else dep_path
        source = os.path.join(source_root, rel)
        target = os.path.join(target_root, rel)
        if not os.path.exists(source):
            result.warnings.append(f"Dependency not found: {dep_path}")
            return
        self._copy_file_or_dir(source, target, dep_path, result)
        if os.path.isfile(source):
            self._copy_parent_inits(os.path.dirname(source), source_root, target_root, result)

    @staticmethod
    def _copy_file_or_dir(source: str, target: str, display: str, result: ImportResult) -> None:
        if os.path.exists(target):
            result.skipped_files.append(display)
            return
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.isdir(source):
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
            result.copied_files.append(display)
        except OSError as exc:
            result.errors.append(f"Failed to copy {display}: {exc}")

    @staticmethod
    def _copy_parent_inits(current_dir: str, source_root: str, target_root: str, result: ImportResult) -> None:
        """Copy __init__.py up the parent chain so the package is importable in the target."""
        while current_dir.startswith(source_root) and current_dir != source_root:
            init_src = os.path.join(current_dir, "__init__.py")
            if os.path.exists(init_src):
                rel = os.path.relpath(init_src, source_root)
                init_dst = os.path.join(target_root, rel)
                if not os.path.exists(init_dst):
                    try:
                        os.makedirs(os.path.dirname(init_dst), exist_ok=True)
                        shutil.copy2(init_src, init_dst)
                        result.copied_files.append(os.path.join(os.path.basename(target_root), rel))
                    except OSError as exc:
                        result.errors.append(f"Failed to copy __init__.py: {exc}")
            current_dir = os.path.dirname(current_dir)

    def update_manifest(self, imported_networks: List[str]) -> None:
        """Merge new entries into target registries/manifest.hocon (always JSON-formatted)."""
        manifest_path = os.path.join(self.target_registries, "manifest.hocon")
        os.makedirs(self.target_registries, exist_ok=True)

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
