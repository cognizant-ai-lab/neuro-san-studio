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

"""Add agent networks to existing projects."""

import os
import sys
from typing import List
from typing import Optional

import questionary

from neuro_san_studio.discovery.agent_network_registry import AgentNetworkMetadata
from neuro_san_studio.discovery.agent_network_registry import AgentNetworkRegistry
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer
from neuro_san_studio.installer.agent_network_installer import AgentNetworkInstaller


class AddCommand:
    """Add agent networks to existing project."""

    def __init__(self, networks_arg: Optional[str] = None):
        """
        Initialize the add command.

        Args:
            networks_arg: Optional comma-separated networks to add (non-interactive mode)
        """
        self.networks_arg = networks_arg
        self.target_dir = os.getcwd()

    def run(self) -> None:
        """Execute the add command."""
        # Step 1: Verify project is initialized
        if not self._verify_project_initialized():
            print("\n❌ Error: Project not initialized.")
            print("Please run 'ns init' first to create a new project.\n")
            sys.exit(1)

        # Step 2: Discover available networks from neuro-san-studio installation
        print("🔍 Discovering available agent networks...\n")
        try:
            # Find neuro-san-studio installation (not the target project's registries)
            source_dir = self._find_neuro_san_studio_installation()
            registry = AgentNetworkRegistry(source_dir=source_dir)
            networks_by_group = registry.discover_networks()
        except FileNotFoundError as e:
            print(f"❌ Error: {e}\n")
            sys.exit(1)

        # Step 3: Get network selection (interactive or from args)
        if self.networks_arg:
            selected_paths = self._parse_networks_arg(self.networks_arg, networks_by_group)
        else:
            selected_paths = self._prompt_for_networks(networks_by_group)

        if not selected_paths:
            print("\n📭 No networks selected. Exiting.\n")
            return

        # Step 4: Install selected networks
        print(f"\n📦 Installing {len(selected_paths)} network(s)...\n")
        self._install_networks(selected_paths, registry)

        print("\n✅ Installation complete!")
        print("\n💡 Next steps:")
        print("   - Run 'ns run' to start the server")
        print("   - The manifest will auto-reload within 5 seconds\n")

    def _verify_project_initialized(self) -> bool:
        """
        Check if the current directory is an initialized ns project.

        Returns:
            True if initialized, False otherwise
        """
        manifest_path = os.path.join(self.target_dir, "registries", "manifest.hocon")
        return os.path.exists(manifest_path)

    def _find_neuro_san_studio_installation(self) -> str:
        """
        Find the neuro-san-studio installation directory.

        Returns:
            Path to neuro-san-studio installation

        Raises:
            FileNotFoundError: If installation cannot be found
        """
        # Try to find via import (installed package)
        try:
            import registries

            if hasattr(registries, "__path__"):
                registries_path = registries.__path__[0]
                return os.path.dirname(registries_path)
        except ImportError:
            pass

        # Try to find based on this module's location (development mode)
        # neuro_san_studio/commands/add.py -> neuro_san_studio/commands -> neuro_san_studio -> project_root
        this_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(this_file)))
        registries_dir = os.path.join(project_root, "registries")

        if os.path.exists(registries_dir):
            return project_root

        raise FileNotFoundError(
            "Cannot find neuro-san-studio installation. "
            "Make sure neuro-san-studio is installed via pip."
        )

    def _parse_networks_arg(
        self, networks_arg: str, networks_by_group: dict
    ) -> List[str]:
        """
        Parse --networks argument.

        Supports:
        - Group names: "basic", "industry"
        - Specific paths: "basic/music_nerd", "agent_network_designer"
        - Special: "all"

        Args:
            networks_arg: Comma-separated network specifiers
            networks_by_group: Dict of group -> list of AgentNetworkMetadata

        Returns:
            List of HOCON paths to install
        """
        selected_paths = []
        specifiers = [s.strip() for s in networks_arg.split(",")]

        for spec in specifiers:
            if spec == "all":
                # Add all networks from all groups
                for group_networks in networks_by_group.values():
                    selected_paths.extend([net.hocon_path for net in group_networks])

            elif spec in networks_by_group:
                # Add all networks from this group
                selected_paths.extend([net.hocon_path for net in networks_by_group[spec]])

            else:
                # Try as specific network path
                # Handle: "basic/music_nerd", "basic/music_nerd.hocon", "music_nerd", "agent_network_designer"
                spec_clean = spec.replace(".hocon", "")  # Remove .hocon if present

                # Check if it exists in any group
                found = False
                for group_networks in networks_by_group.values():
                    for net in group_networks:
                        # Match by:
                        # 1. Exact hocon_path match: "basic/music_nerd.hocon" or "basic/music_nerd"
                        # 2. Just network name: "music_nerd"
                        net_path_clean = net.hocon_path.replace(".hocon", "")
                        if net_path_clean == spec_clean or net.name == spec_clean:
                            selected_paths.append(net.hocon_path)
                            found = True
                            break
                    if found:
                        break

                if not found:
                    print(f"⚠️  Warning: Network '{spec}' not found, skipping.")

        return list(set(selected_paths))  # Deduplicate

    def _prompt_for_networks(self, networks_by_group: dict) -> List[str]:
        """
        Interactive prompt for network selection.

        Args:
            networks_by_group: Dict of group -> list of AgentNetworkMetadata

        Returns:
            List of HOCON paths to install
        """
        # Step 1: Prompt for group selection
        group_choices = []
        for group_name in ["basic", "industry", "experimental", "tools"]:
            if group_name in networks_by_group:
                count = len(networks_by_group[group_name])
                description = self._get_group_description(group_name)
                group_choices.append(
                    questionary.Choice(
                        title=f"{group_name.capitalize()} ({count} networks) - {description}",
                        value=group_name,
                        checked=(group_name == "basic"),  # Default to basic
                    )
                )

        group_choices.extend(
            [
                questionary.Separator(),
                questionary.Choice(title="Custom Selection - Choose specific networks", value="custom"),
                questionary.Choice(title="All - Install everything", value="all"),
            ]
        )

        selected_groups = questionary.checkbox(
            "Which agent network groups do you want to install?",
            choices=group_choices,
        ).ask()

        if selected_groups is None:  # User cancelled
            return []

        # Step 2: Handle selection
        if "all" in selected_groups:
            # Install all networks
            all_paths = []
            for group_networks in networks_by_group.values():
                all_paths.extend([net.hocon_path for net in group_networks])
            return all_paths

        if "custom" in selected_groups:
            # Show individual network selection
            return self._prompt_individual_networks(networks_by_group)

        # Install selected groups
        selected_paths = []
        for group_name in selected_groups:
            if group_name in networks_by_group:
                selected_paths.extend([net.hocon_path for net in networks_by_group[group_name]])

        return selected_paths

    def _prompt_individual_networks(self, networks_by_group: dict) -> List[str]:
        """
        Prompt for individual network selection.

        Args:
            networks_by_group: Dict of group -> list of AgentNetworkMetadata

        Returns:
            List of HOCON paths to install
        """
        # Build flat list of all networks with group labels
        choices = []
        for group_name in ["basic", "industry", "experimental", "tools"]:
            if group_name not in networks_by_group:
                continue

            choices.append(questionary.Separator(f"─── {group_name.upper()} ───"))
            for net in sorted(networks_by_group[group_name], key=lambda n: n.name):
                # Format: "network_name - description"
                title = net.name
                if net.description:
                    # Truncate long descriptions
                    desc = net.description[:80] + "..." if len(net.description) > 80 else net.description
                    title = f"{net.name} - {desc}"

                choices.append(questionary.Choice(title=title, value=net.hocon_path))

        selected_paths = questionary.checkbox(
            "Select agent networks to install:",
            choices=choices,
        ).ask()

        return selected_paths if selected_paths else []

    def _get_group_description(self, group_name: str) -> str:
        """Get description for a group."""
        descriptions = {
            "basic": "Simple examples and tutorials",
            "industry": "Domain-specific use cases",
            "experimental": "Research and advanced features",
            "tools": "Tool integrations and utilities",
        }
        return descriptions.get(group_name, "")

    def _install_networks(self, hocon_paths: List[str], registry: AgentNetworkRegistry) -> None:
        """
        Install selected networks with their dependencies.

        Args:
            hocon_paths: List of HOCON paths to install
            registry: AgentNetworkRegistry instance
        """
        # Initialize analyzer and installer
        analyzer = DependencyAnalyzer(registry.registries_dir, registry.source_dir + "/coded_tools", registry.source_dir + "/middleware")
        installer = AgentNetworkInstaller(registry.source_dir, self.target_dir)

        total_copied = 0
        total_skipped = 0
        all_errors = []
        all_warnings = []
        installed_paths = []

        for hocon_path in hocon_paths:
            # Get full path
            full_hocon_path = os.path.join(registry.registries_dir, hocon_path)

            # Analyze dependencies
            print(f"   Analyzing {hocon_path}...")
            try:
                deps = analyzer.get_transitive_dependencies(full_hocon_path)
            except Exception as e:
                all_errors.append(f"Failed to analyze {hocon_path}: {e}")
                continue

            # Install network
            print(f"   Installing {hocon_path}...")
            try:
                result = installer.install_network(hocon_path, deps)
                total_copied += len(result.copied_files)
                total_skipped += len(result.skipped_files)
                all_errors.extend(result.errors)
                all_warnings.extend(result.warnings)
                installed_paths.append(result.hocon_path)

            except Exception as e:
                all_errors.append(f"Failed to install {hocon_path}: {e}")
                continue

        # Update manifest
        if installed_paths:
            print("\n   Updating manifest...")
            installer.update_manifest(installed_paths)

        # Print summary
        print(f"\n📊 Summary:")
        print(f"   ✅ Copied: {total_copied} files")
        if total_skipped > 0:
            print(f"   ⏭️  Skipped: {total_skipped} files (already exist)")

        if all_warnings:
            print(f"\n⚠️  Warnings ({len(all_warnings)}):")
            for warning in all_warnings[:5]:
                print(f"   - {warning}")
            if len(all_warnings) > 5:
                print(f"   ... and {len(all_warnings) - 5} more")

        if all_errors:
            print(f"\n❌ Errors ({len(all_errors)}):")
            for error in all_errors[:5]:
                print(f"   - {error}")
            if len(all_errors) > 5:
                print(f"   ... and {len(all_errors) - 5} more")
