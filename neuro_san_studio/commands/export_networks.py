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

"""Export an agent network from the current project into a self-contained file."""

import os
import sys
from typing import Dict
from typing import List
from typing import Optional

import questionary

from neuro_san_studio.discovery.agent_network_registry import AgentNetworkRegistry
from neuro_san_studio.exporter.agent_network_exporter import AgentNetworkExporter
from neuro_san_studio.utils.cli_prompt import CliPrompt
from neuro_san_studio.utils.cli_status import CliStatus


class ExportCommand:  # pylint: disable=too-few-public-methods
    """Run the `ns export` flow: resolve the network, walk deps, write the bundle."""

    def __init__(self, network: Optional[str] = None, output: Optional[str] = None):
        self.network = network
        self.output = output
        self.project_dir = os.getcwd()

    def run(self) -> None:
        """Resolve, walk, and write; print a small summary."""
        if not self._verify_project_initialized():
            print()
            CliStatus.err("Project not initialized. Run 'ns init' first.")
            print()
            sys.exit(1)

        if not self.network:
            picked = self._prompt_for_network()
            if not picked:
                print()
                CliStatus.info("No network selected. Exiting.")
                print()
                return
            self.network = picked

        exporter = AgentNetworkExporter(project_dir=self.project_dir)
        try:
            result = exporter.export(self.network, output_path=self.output)
        except FileNotFoundError as exc:
            print()
            CliStatus.err(str(exc))
            print()
            sys.exit(1)
        except ValueError as exc:
            print()
            CliStatus.err(str(exc))
            print()
            sys.exit(1)

        print()
        CliStatus.ok(f"Exported '{result.network_name}' -> {result.output_path}")
        self._print_dep_summary(result)
        if result.warnings:
            print()
            CliStatus.warn(f"Warnings ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"        - {w}")
        print()

    @staticmethod
    def _print_dep_summary(result) -> None:
        """List what's in the bundle so the user can verify nothing is missing."""
        deps = result.dependencies
        if not (
            deps.coded_tools
            or deps.middleware
            or deps.sub_networks
            or result.shared_includes
            or result.bundled_mcp_urls
        ):
            return
        print()
        CliStatus.info("Included dependencies:")
        if deps.sub_networks:
            print(f"        sub-networks ({len(deps.sub_networks)}):")
            for ref in deps.sub_networks:
                print(f"          - {ref}")
        if deps.coded_tools:
            print(f"        coded_tools ({len(deps.coded_tools)}):")
            for path in deps.coded_tools:
                print(f"          - {path}")
        if deps.middleware:
            print(f"        middleware ({len(deps.middleware)}):")
            for path in deps.middleware:
                print(f"          - {path}")
        if result.shared_includes:
            print(f"        shared includes ({len(result.shared_includes)}):")
            for inc in result.shared_includes:
                print(f"          - registries/{inc}")
        if result.bundled_mcp_urls:
            print(f"        mcp servers ({len(result.bundled_mcp_urls)}):")
            for url in result.bundled_mcp_urls:
                print(f"          - {url}")

    def _verify_project_initialized(self) -> bool:
        return os.path.exists(os.path.join(self.project_dir, "registries", "manifest.hocon"))

    def _prompt_for_network(self) -> Optional[str]:
        """Single-select picker over the project's manifest. Networks are grouped by
        directory prefix, separators delimit each group. Returns the chosen
        registries-relative path (e.g. ``basic/music_nerd.hocon``), or ``None`` if
        the user aborts (Ctrl-C / Esc) or the project has no networks."""
        try:
            registry = AgentNetworkRegistry(source_dir=self.project_dir)
            networks_by_group = registry.discover()
        except FileNotFoundError as exc:
            print()
            CliStatus.err(str(exc))
            print()
            return None

        if not networks_by_group:
            print()
            CliStatus.err("No networks declared in the project's manifest. Add some first or pass a name.")
            print()
            return None

        choices = self._build_picker_choices(networks_by_group)
        try:
            question = questionary.select(
                "Pick a network to export:",
                choices=choices,
            )
            answer = CliPrompt.bind_exit_on_esc(question).ask()
        except (KeyboardInterrupt, EOFError):
            return None
        if answer is None or answer == CliPrompt.EXIT:
            return None
        return answer

    @staticmethod
    def _build_picker_choices(networks_by_group: Dict[str, List[str]]) -> List:
        """Render group separators followed by each group's networks as Choice rows."""
        choices: List = []
        for group, paths in networks_by_group.items():
            choices.append(questionary.Separator(f"─── {group.upper()} ({len(paths)}) ───"))
            for path in sorted(paths):
                name = os.path.basename(path).removesuffix(".hocon")
                choices.append(questionary.Choice(title=name, value=path))
        return choices
