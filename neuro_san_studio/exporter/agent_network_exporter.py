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

"""Bundle an agent network from a project directory into the shape `ns import -f` consumes."""

import os
import re
import zipfile
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from pathlib import PurePosixPath
from typing import List
from typing import Optional
from typing import Set

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer
from neuro_san_studio.exporter.export_metadata import ExportMetadataStamper
from neuro_san_studio.mcp.mcp_info_merger import McpInfoMerger

# `include "registries/<name>"` and `include classpath("registries/<name>")` both surface
# shared HOCON files (e.g. aaosa.hocon). The DependencyAnalyzer reads the `tools` array
# but doesn't parse include directives — this regex bridges the gap.
_INCLUDE_RE = re.compile(r'include\s+(?:classpath\()?"registries/([^"]+)"\)?')

# `ns init` scaffolds <project>/mcp/mcp_info.hocon. We export from the project's copy when
# present, falling back to the studio package's bundled mcp_info.hocon — same precedence
# as the runtime resolver in NeuroSanRunner.
_PROJECT_MCP_INFO_RELPATH = os.path.join("mcp", "mcp_info.hocon")


@dataclass
class ExportResult:
    """Outcome of exporting one network: where it landed, what it contains, what was missing."""

    network_name: str
    output_path: str
    dependencies: AgentNetworkDependencies = field(default_factory=AgentNetworkDependencies)
    shared_includes: List[str] = field(default_factory=list)
    bundled_files: List[str] = field(default_factory=list)
    bundled_mcp_urls: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class AgentNetworkExporter:  # pylint: disable=too-few-public-methods
    """Bundle an agent network from a project into a self-contained file.

    Source of truth is the user's project (`project_dir`) — same layout as `ns import`
    consumes: `registries/`, `coded_tools/`, `middleware/`. The dependency walker is
    pointed at the project's directories, so a network exported from a project
    references only files that exist in that project.

    Auto-detection on output shape: no deps → single `.hocon`; any deps → `.zip` carrying
    the network plus its dependencies. Users can override via `-o` but a mismatch between
    the suffix and the deps shape is rejected up front.
    """

    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self.registries_dir = os.path.join(project_dir, "registries")
        self.coded_tools_dir = os.path.join(project_dir, "coded_tools")
        self.middleware_dir = os.path.join(project_dir, "middleware")
        self.mcp_info_path = os.path.join(project_dir, _PROJECT_MCP_INFO_RELPATH)

    def export(self, network: str, output_path: Optional[str] = None) -> ExportResult:
        """Export `network` (a name like 'music_nerd' or relative path 'basic/music_nerd[.hocon]')
        to `output_path`. If `output_path` is None, write `<cwd>/<basename>.{hocon,zip}` based
        on whether the network has dependencies."""
        rel_hocon = self._resolve_network(network)
        full_hocon = os.path.join(self.registries_dir, rel_hocon)

        # pyhocon resolves `include "registries/..."` directives relative to CWD; chdir to
        # the project root while the analyzer parses, mirroring AgentNetworkRegistry.
        analyzer = DependencyAnalyzer(self.registries_dir, self.coded_tools_dir, self.middleware_dir)
        prev_cwd = os.getcwd()
        try:
            os.chdir(self.project_dir)
            deps = analyzer.get_transitive_dependencies(full_hocon)
        finally:
            os.chdir(prev_cwd)
        # Shared HOCON `include` directives don't surface through the structured walker —
        # do a textual scan over the network's own file so includes count toward "has_deps".
        own_includes = self._collect_shared_includes([full_hocon])
        # MCP refs are URL strings in the `tools` array; deps.mcp_tools already collects them
        # (including transitively through sub-networks). Even an MCP-only network must export
        # as a zip so we can ship the filtered mcp_info.hocon alongside the network.
        has_deps = self._has_dependencies(deps) or bool(own_includes) or bool(deps.mcp_tools)
        target = self._resolve_output_path(rel_hocon, output_path, has_deps=has_deps)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)

        result = ExportResult(
            network_name=os.path.basename(rel_hocon).removesuffix(".hocon"),
            output_path=target,
            dependencies=deps,
        )

        if not has_deps:
            Path(target).write_text(self._stamped_network_hocon(full_hocon), encoding="utf-8")
            result.bundled_files.append(f"registries/{rel_hocon}")
            return result

        self._write_zip(target, rel_hocon, deps, result)
        return result

    @staticmethod
    def _stamped_network_hocon(full_hocon: str) -> str:
        """Read the network HOCON and return its text with export-provenance metadata stamped in."""
        text = Path(full_hocon).read_text(encoding="utf-8")
        return ExportMetadataStamper().stamp(text)

    def _write_zip(
        self,
        target: str,
        rel_hocon: str,
        deps: AgentNetworkDependencies,
        result: ExportResult,
    ) -> None:
        """Bundle the network HOCON, sub-networks, coded tools, middleware, and shared includes."""
        full_hocon = os.path.join(self.registries_dir, rel_hocon)
        # Use deduplicating set to avoid double-adding when sub-networks share files.
        added: Set[str] = set()

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            # The primary network file is the one that carries the export-provenance metadata;
            # write its stamped text rather than the verbatim file.
            arcname = f"registries/{rel_hocon}"
            zf.writestr(arcname, self._stamped_network_hocon(full_hocon))
            added.add(arcname)
            result.bundled_files.append(arcname)
            self._add_sub_networks(zf, deps.sub_networks, added, result)
            for ct in deps.coded_tools:
                self._add_dep(zf, ct, added, result)
            for mw in deps.middleware:
                self._add_dep(zf, mw, added, result)
            self._add_shared_includes(zf, full_hocon, deps.sub_networks, added, result)
            self._add_filtered_mcp_info(zf, deps.mcp_tools, added, result)

    def _add_sub_networks(
        self, zf: zipfile.ZipFile, sub_refs: List[str], added: Set[str], result: ExportResult
    ) -> None:
        for sub_ref in sub_refs:
            sub_rel = sub_ref.lstrip("/")
            if not sub_rel.endswith(".hocon"):
                sub_rel += ".hocon"
            sub_full = os.path.join(self.registries_dir, sub_rel)
            if not os.path.isfile(sub_full):
                result.warnings.append(f"Sub-network not found: {sub_ref}")
                continue
            self._add_file(zf, sub_full, f"registries/{sub_rel}", added, result)

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def _add_shared_includes(
        self,
        zf: zipfile.ZipFile,
        full_hocon: str,
        sub_refs: List[str],
        added: Set[str],
        result: ExportResult,
    ) -> None:
        sub_paths = [
            os.path.join(self.registries_dir, s.lstrip("/") + ("" if s.endswith(".hocon") else ".hocon"))
            for s in sub_refs
        ]
        shared = self._collect_shared_includes([full_hocon] + sub_paths)
        for inc_rel in sorted(shared):
            inc_full = os.path.join(self.registries_dir, inc_rel)
            if not os.path.isfile(inc_full):
                result.warnings.append(f"Shared include not found: registries/{inc_rel}")
                continue
            self._add_file(zf, inc_full, f"registries/{inc_rel}", added, result)
            result.shared_includes.append(inc_rel)

    # pylint: disable-next=too-many-arguments,too-many-positional-arguments
    def _add_file(self, zf: zipfile.ZipFile, source: str, arcname: str, added: Set[str], result: ExportResult) -> None:
        """Write one file under arcname, skipping duplicates and recording the addition."""
        if arcname in added:
            return
        zf.write(source, arcname=arcname)
        added.add(arcname)
        result.bundled_files.append(arcname)

    def _add_dep(self, zf: zipfile.ZipFile, dep_path: str, added: Set[str], result: ExportResult) -> None:
        """Resolve a coded_tools/ or middleware/ relative path and bundle the file or directory."""
        full = os.path.join(self.project_dir, dep_path)
        if os.path.isfile(full):
            self._add_file(zf, full, dep_path, added, result)
            self._add_parent_inits(zf, full, added, result)
            return
        if os.path.isdir(full):
            for root, _dirs, files in os.walk(full):
                for name in files:
                    if name.endswith(".pyc") or name == ".DS_Store":
                        continue
                    src = os.path.join(root, name)
                    arc = os.path.relpath(src, self.project_dir)
                    self._add_file(zf, src, arc, added, result)
            return
        result.warnings.append(f"Dependency not found: {dep_path}")

    def _add_parent_inits(self, zf: zipfile.ZipFile, file_path: str, added: Set[str], result: ExportResult) -> None:
        """Walk parent dirs up to the project root and bundle any __init__.py we encounter,
        so the receiver's package tree imports cleanly."""
        current = os.path.dirname(file_path)
        # Stop at the project root, never above.
        while current.startswith(self.project_dir) and current != self.project_dir:
            init_path = os.path.join(current, "__init__.py")
            if os.path.isfile(init_path):
                arc = os.path.relpath(init_path, self.project_dir)
                self._add_file(zf, init_path, arc, added, result)
            current = os.path.dirname(current)

    def _add_filtered_mcp_info(
        self,
        zf: zipfile.ZipFile,
        mcp_urls: List[str],
        added: Set[str],
        result: ExportResult,
    ) -> None:
        """Filter the project's mcp_info.hocon to the URLs the network references and bundle it.

        Falls back to the bundled studio mcp_info.hocon if the project hasn't scaffolded one
        yet (matches NeuroSanRunner._resolve_mcp_info_file precedence). If no source file is
        found, or the URLs aren't present in any source, we surface a warning rather than
        silently shipping an empty file — receivers need every URL configured.
        """
        if not mcp_urls:
            return
        source_path = self._resolve_mcp_info_source()
        if not source_path:
            result.warnings.append(f"MCP refs found ({', '.join(mcp_urls)}) but no mcp_info.hocon located.")
            return
        with open(source_path, encoding="utf-8") as fh:
            source_text = fh.read()
        merger = McpInfoMerger()
        blocks = merger.filter_blocks(source_text, mcp_urls)
        missing = [url for url in mcp_urls if url not in blocks]
        if missing:
            result.warnings.append(f"MCP server(s) not found in {source_path}: {', '.join(missing)}")
        if not blocks:
            return
        rendered = merger.render_file(blocks)
        arcname = "mcp/mcp_info.hocon"
        if arcname in added:
            return
        zf.writestr(arcname, rendered)
        added.add(arcname)
        result.bundled_files.append(arcname)
        result.bundled_mcp_urls.extend(blocks.keys())

    def _resolve_mcp_info_source(self) -> str:
        """Project's <project>/mcp/mcp_info.hocon if it exists, otherwise the studio fallback."""
        if os.path.isfile(self.mcp_info_path):
            return self.mcp_info_path
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio import mcp as _mcp_pkg

        bundled = os.path.join(os.path.dirname(_mcp_pkg.__file__), "mcp_info.hocon")
        return bundled if os.path.isfile(bundled) else ""

    @staticmethod
    def _collect_shared_includes(hocon_paths: List[str]) -> Set[str]:
        """Scan each hocon for `include "registries/<name>"` and return the unique <name>s."""
        seen: Set[str] = set()
        for path in hocon_paths:
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            for match in _INCLUDE_RE.findall(text):
                name = match if match.endswith(".hocon") else f"{match}.hocon"
                seen.add(name)
        return seen

    def _resolve_network(self, network: str) -> str:
        """Map a user-supplied name to a registries-relative `.hocon` path; raise if missing."""
        # Tolerate a repo-root-style `registries/...` prefix: `ns export
        # registries/basic/hello_world.hocon` should behave like `basic/hello_world.hocon`.
        network = self._strip_registries_prefix(network)
        candidate = network if network.endswith(".hocon") else f"{network}.hocon"

        # Direct relative path under registries/ (e.g., 'basic/music_nerd.hocon').
        direct = os.path.join(self.registries_dir, candidate)
        if os.path.isfile(direct):
            return candidate

        # Bare name — search every group dir for a matching .hocon.
        if "/" not in candidate:
            for root, _dirs, files in os.walk(self.registries_dir):
                if candidate in files:
                    return os.path.relpath(os.path.join(root, candidate), self.registries_dir)

        raise FileNotFoundError(
            f"Network '{network}' not found under {self.registries_dir}. "
            f"Pass a name like 'music_nerd' or a relative path like 'basic/music_nerd'."
        )

    @staticmethod
    def _strip_registries_prefix(network: str) -> str:
        """Drop a leading `registries/` segment so a repo-root-style path resolves like
        the registries-relative form. `PurePosixPath.parts` collapses `./` and interior
        `.` so equivalent spellings are handled by one rule, and keeps the result `/`-
        separated (it feeds zip arcnames, which must stay POSIX on every OS)."""
        parts = PurePosixPath(network).parts
        if parts and parts[0] == "registries":
            return str(PurePosixPath(*parts[1:])) if len(parts) > 1 else ""
        return network

    @staticmethod
    def _has_dependencies(deps: AgentNetworkDependencies) -> bool:
        """True iff the network references any coded tool, middleware, sub-network, or MCP server."""
        return bool(deps.coded_tools or deps.middleware or deps.sub_networks or deps.mcp_tools)

    @staticmethod
    def _resolve_output_path(rel_hocon: str, output_path: Optional[str], *, has_deps: bool) -> str:
        """Pick the output file path. Reject suffix mismatches against the deps shape."""
        basename = os.path.basename(rel_hocon).removesuffix(".hocon")

        if output_path is None:
            default_suffix = ".zip" if has_deps else ".hocon"
            return os.path.abspath(f"{basename}{default_suffix}")

        suffix = os.path.splitext(output_path)[1].lower()
        if has_deps and suffix == ".hocon":
            raise ValueError("Network has dependencies; cannot export to '.hocon'. Use '.zip' or omit -o.")
        if not has_deps and suffix == ".zip":
            # A zip wrapping a single hocon adds nothing — keep the natural shape.
            raise ValueError("Network has no dependencies; export as '.hocon' rather than '.zip'.")
        if suffix not in (".hocon", ".zip"):
            raise ValueError(f"Unsupported output suffix: '{suffix or '(none)'}'. Use '.hocon' or '.zip'.")

        return os.path.abspath(output_path)
