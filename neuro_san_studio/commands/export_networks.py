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
from typing import Optional

from neuro_san_studio.exporter.agent_network_exporter import AgentNetworkExporter


class ExportCommand:  # pylint: disable=too-few-public-methods
    """Run the `ns export` flow: resolve the network, walk deps, write the bundle."""

    def __init__(self, network: Optional[str] = None, output: Optional[str] = None):
        self.network = network
        self.output = output
        self.project_dir = os.getcwd()

    def run(self) -> None:
        """Resolve, walk, and write; print a small summary."""
        if not self._verify_project_initialized():
            print("\n❌ Project not initialized. Run 'ns init' first.\n")
            sys.exit(1)

        if not self.network:
            # Phase 6 will add the interactive picker.
            print("\n❌ Interactive export is not implemented yet. Pass a network name explicitly.\n")
            sys.exit(2)

        exporter = AgentNetworkExporter(project_dir=self.project_dir)
        try:
            result = exporter.export(self.network, output_path=self.output)
        except FileNotFoundError as exc:
            print(f"\n❌ {exc}\n")
            sys.exit(1)
        except ValueError as exc:
            print(f"\n❌ {exc}\n")
            sys.exit(1)

        print(f"\n📦 Exported '{result.network_name}' → {result.output_path}")
        if result.warnings:
            print("\n⚠️  Warnings:")
            for w in result.warnings:
                print(f"   - {w}")
        print()

    def _verify_project_initialized(self) -> bool:
        return os.path.exists(os.path.join(self.project_dir, "registries", "manifest.hocon"))
