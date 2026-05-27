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
import shutil
from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Optional

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer


@dataclass
class ExportResult:
    """Outcome of exporting one network: where it landed, what it contains, what was missing."""

    network_name: str
    output_path: str
    dependencies: AgentNetworkDependencies = field(default_factory=AgentNetworkDependencies)
    warnings: List[str] = field(default_factory=list)


class AgentNetworkExporter:
    """Bundle an agent network from a project into a self-contained file.

    Source of truth is the user's project (`project_dir`) — same layout as `ns import`
    consumes: `registries/`, `coded_tools/`, `middleware/`. The dependency walker is
    pointed at the project's directories, so a network exported from a project
    references only files that exist in that project.

    Phase 4 handles the no-deps case (single `.hocon` output). Networks with deps
    raise `ValueError`; zip support comes in Phase 5.
    """

    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self.registries_dir = os.path.join(project_dir, "registries")
        self.coded_tools_dir = os.path.join(project_dir, "coded_tools")
        self.middleware_dir = os.path.join(project_dir, "middleware")

    def export(self, network: str, output_path: Optional[str] = None) -> ExportResult:
        """Export `network` (a name like 'music_nerd' or relative path 'basic/music_nerd[.hocon]')
        to `output_path`. If `output_path` is None, write `<cwd>/<basename>.hocon`."""
        rel_hocon = self._resolve_network(network)
        full_hocon = os.path.join(self.registries_dir, rel_hocon)

        analyzer = DependencyAnalyzer(self.registries_dir, self.coded_tools_dir, self.middleware_dir)
        deps = analyzer.get_transitive_dependencies(full_hocon)

        if self._has_dependencies(deps):
            raise ValueError(
                f"Network '{network}' has dependencies "
                f"(coded_tools={len(deps.coded_tools)}, middleware={len(deps.middleware)}, "
                f"sub_networks={len(deps.sub_networks)}); "
                f"export to a .zip instead (zip output lands in a later phase)."
            )

        target = self._resolve_output_path(rel_hocon, output_path, has_deps=False)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.copy2(full_hocon, target)

        return ExportResult(
            network_name=os.path.basename(rel_hocon).removesuffix(".hocon"),
            output_path=target,
            dependencies=deps,
        )

    def _resolve_network(self, network: str) -> str:
        """Map a user-supplied name to a registries-relative `.hocon` path; raise if missing."""
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
    def _has_dependencies(deps: AgentNetworkDependencies) -> bool:
        """True iff the network references any coded tool, middleware, or sub-network."""
        return bool(deps.coded_tools or deps.middleware or deps.sub_networks)

    @staticmethod
    def _resolve_output_path(rel_hocon: str, output_path: Optional[str], *, has_deps: bool) -> str:
        """Pick the output file path. Reject suffix mismatches against the deps shape."""
        basename = os.path.basename(rel_hocon).removesuffix(".hocon")

        if output_path is None:
            default_suffix = ".zip" if has_deps else ".hocon"
            return os.path.abspath(f"{basename}{default_suffix}")

        suffix = os.path.splitext(output_path)[1].lower()
        if has_deps and suffix == ".hocon":
            raise ValueError(
                "Network has dependencies; cannot export to '.hocon'. Use '.zip' or omit -o."
            )
        if not has_deps and suffix == ".zip":
            # A zip wrapping a single hocon is a valid choice — defer to Phase 5 once
            # zip writes are implemented; for now, steer the user toward the natural shape.
            raise ValueError("Network has no dependencies; export as '.hocon' rather than '.zip'.")
        if suffix not in (".hocon", ".zip"):
            raise ValueError(f"Unsupported output suffix: '{suffix or '(none)'}'. Use '.hocon' or '.zip'.")

        return os.path.abspath(output_path)
