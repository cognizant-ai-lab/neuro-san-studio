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

"""Install agent networks with all dependencies to target projects."""

import os
import shutil
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import List
from typing import Set

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies


@dataclass
class InstallResult:
    """Result of installing an agent network."""

    network_name: str
    hocon_path: str
    copied_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class AgentNetworkInstaller:
    """Install agent networks with all dependencies."""

    def __init__(self, source_dir: str, target_dir: str):
        """
        Initialize the installer.

        Args:
            source_dir: Root of neuro-san-studio installation
            target_dir: User's project directory (cwd)
        """
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.source_registries = os.path.join(source_dir, "registries")
        self.source_coded_tools = os.path.join(source_dir, "coded_tools")
        self.source_middleware = os.path.join(source_dir, "middleware")
        self.target_registries = os.path.join(target_dir, "registries")
        self.target_coded_tools = os.path.join(target_dir, "coded_tools")
        self.target_middleware = os.path.join(target_dir, "middleware")

    def install_network(self, hocon_relative_path: str, dependencies: AgentNetworkDependencies) -> InstallResult:
        """
        Copy agent network and all dependencies to target directory.

        Args:
            hocon_relative_path: Path relative to registries/ (e.g., "basic/music_nerd.hocon")
            dependencies: Dependencies extracted by DependencyAnalyzer

        Returns:
            InstallResult with copied files, errors, warnings

        Steps:
            1. Copy HOCON file to registries/
            2. Copy all included HOCON files
            3. Copy all coded tool Python files
            4. Copy all middleware Python files
            5. Update manifest.hocon
        """
        # Extract network name from path
        network_name = Path(hocon_relative_path).stem  # Remove .hocon extension

        result = InstallResult(network_name=network_name, hocon_path=hocon_relative_path)

        # 1. Copy main HOCON file
        self._copy_hocon(hocon_relative_path, result)

        # 2. Copy sub-network HOCON files
        # Note: includes are auto-resolved by AbstractAsyncConfigRestorer, no need to copy separately
        for sub_network_ref in dependencies.sub_networks:
            # Convert "/agent_network_editor" to "agent_network_editor.hocon"
            sub_network_name = sub_network_ref.lstrip("/")
            if not sub_network_name.endswith(".hocon"):
                sub_network_name = sub_network_name + ".hocon"
            self._copy_hocon(sub_network_name, result)

        # 4. Copy coded tools
        for coded_tool_path in dependencies.coded_tools:
            self._copy_coded_tool(coded_tool_path, result)

        # 5. Copy middleware
        for middleware_path in dependencies.middleware:
            self._copy_middleware(middleware_path, result)

        return result

    def _copy_hocon(self, relative_path: str, result: InstallResult) -> None:
        """
        Copy a HOCON file from source to target.

        Args:
            relative_path: Path relative to registries/ or config/
            result: InstallResult to update
        """
        # Determine source base directory (registries/ or config/ or root)
        if relative_path.startswith("registries/"):
            source_file = os.path.join(self.source_dir, relative_path)
            target_file = os.path.join(self.target_dir, relative_path)
        elif relative_path.startswith("config/"):
            source_file = os.path.join(self.source_dir, relative_path)
            target_file = os.path.join(self.target_dir, relative_path)
        else:
            # Assume it's in registries/
            source_file = os.path.join(self.source_registries, relative_path)
            target_file = os.path.join(self.target_registries, relative_path)

        # Check if source exists
        if not os.path.exists(source_file):
            result.warnings.append(f"Source HOCON not found: {relative_path}")
            return

        # Skip if target exists (idempotent)
        if os.path.exists(target_file):
            result.skipped_files.append(relative_path)
            return

        try:
            # Create parent directories
            os.makedirs(os.path.dirname(target_file), exist_ok=True)

            # Copy file
            shutil.copy2(source_file, target_file)
            result.copied_files.append(relative_path)

        except Exception as e:
            result.errors.append(f"Failed to copy {relative_path}: {e}")

    def _copy_coded_tool(self, coded_tool_path: str, result: InstallResult) -> None:
        """
        Copy a coded tool Python file or package.

        Handles both:
        - Single file: coded_tools/basic/coffee_finder/order_api.py
        - Package directory: coded_tools/experimental/kwik_agents/

        Args:
            coded_tool_path: Path relative to project root
            result: InstallResult to update
        """
        # Remove "coded_tools/" prefix if present
        if coded_tool_path.startswith("coded_tools/"):
            relative_path = coded_tool_path[len("coded_tools/") :]
        else:
            relative_path = coded_tool_path

        source_path = os.path.join(self.source_coded_tools, relative_path)
        target_path = os.path.join(self.target_coded_tools, relative_path)

        # Check if it's a directory (package) or file
        if os.path.isdir(source_path):
            self._copy_package(source_path, target_path, coded_tool_path, result)
        elif os.path.isfile(source_path):
            self._copy_single_file(source_path, target_path, coded_tool_path, result)
        else:
            result.warnings.append(f"Coded tool not found: {coded_tool_path}")

    def _copy_middleware(self, middleware_path: str, result: InstallResult) -> None:
        """
        Copy middleware Python files.

        Middleware is usually a package with multiple files.

        Args:
            middleware_path: Path relative to project root
            result: InstallResult to update
        """
        # Remove "middleware/" prefix if present
        if middleware_path.startswith("middleware/"):
            relative_path = middleware_path[len("middleware/") :]
        else:
            relative_path = middleware_path

        source_path = os.path.join(self.source_middleware, relative_path)
        target_path = os.path.join(self.target_middleware, relative_path)

        # Check if it's a directory (package) or file
        if os.path.isfile(source_path):
            self._copy_single_file(source_path, target_path, middleware_path, result)

            # Also copy the parent package if it has __init__.py
            parent_dir = os.path.dirname(source_path)
            self._copy_parent_packages(parent_dir, self.source_middleware, self.target_middleware, result)

        elif os.path.isdir(source_path):
            self._copy_package(source_path, target_path, middleware_path, result)
        else:
            result.warnings.append(f"Middleware not found: {middleware_path}")

    def _copy_single_file(self, source_file: str, target_file: str, display_path: str, result: InstallResult) -> None:
        """
        Copy a single file.

        Args:
            source_file: Absolute source path
            target_file: Absolute target path
            display_path: Path for display in results
            result: InstallResult to update
        """
        # Skip if target exists
        if os.path.exists(target_file):
            result.skipped_files.append(display_path)
            return

        try:
            # Create parent directories
            os.makedirs(os.path.dirname(target_file), exist_ok=True)

            # Copy file
            shutil.copy2(source_file, target_file)
            result.copied_files.append(display_path)

        except Exception as e:
            result.errors.append(f"Failed to copy {display_path}: {e}")

    def _copy_package(self, source_dir: str, target_dir: str, display_path: str, result: InstallResult) -> None:
        """
        Copy a Python package directory.

        Args:
            source_dir: Absolute source directory path
            target_dir: Absolute target directory path
            display_path: Path for display in results
            result: InstallResult to update
        """
        # Skip if target exists
        if os.path.exists(target_dir):
            result.skipped_files.append(display_path)
            return

        try:
            # Copy entire directory tree
            shutil.copytree(source_dir, target_dir)
            result.copied_files.append(display_path)

        except Exception as e:
            result.errors.append(f"Failed to copy package {display_path}: {e}")

    def _copy_parent_packages(
        self, current_dir: str, source_root: str, target_root: str, result: InstallResult
    ) -> None:
        """
        Copy __init__.py files from parent packages.

        This ensures that all parent packages exist and are valid Python packages.

        Args:
            current_dir: Current directory to check
            source_root: Root directory (e.g., source_middleware)
            target_root: Target root directory (e.g., target_middleware)
            result: InstallResult to update
        """
        # Stop if we've reached the root
        if current_dir == source_root or not current_dir.startswith(source_root):
            return

        # Check for __init__.py
        init_file = os.path.join(current_dir, "__init__.py")
        if os.path.exists(init_file):
            # Calculate relative path
            relative_path = os.path.relpath(init_file, source_root)
            target_file = os.path.join(target_root, relative_path)

            # Copy if not exists
            if not os.path.exists(target_file):
                try:
                    os.makedirs(os.path.dirname(target_file), exist_ok=True)
                    shutil.copy2(init_file, target_file)
                    result.copied_files.append(os.path.join(os.path.basename(target_root), relative_path))
                except Exception as e:
                    result.errors.append(f"Failed to copy __init__.py: {e}")

        # Recurse to parent
        parent_dir = os.path.dirname(current_dir)
        if parent_dir != current_dir:  # Avoid infinite loop
            self._copy_parent_packages(parent_dir, source_root, target_root, result)

    def update_manifest(self, installed_networks: List[str]) -> None:
        """
        Update or create registries/manifest.hocon to include all installed networks.

        Args:
            installed_networks: List of network paths to add (e.g., ["basic/music_nerd.hocon"])

        Structure:
            {
                "basic/music_nerd.hocon": true,
                "basic/coffee_finder.hocon": true,
                "agent_network_designer.hocon": true
            }
        """
        manifest_path = os.path.join(self.target_registries, "manifest.hocon")

        # Ensure registries directory exists
        os.makedirs(self.target_registries, exist_ok=True)

        # Read existing manifest or create new one
        existing_entries: Set[str] = set()
        manifest_format = "json"  # Default to JSON format

        if os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as f:
                content = f.read()

            # Detect format
            manifest_format = "json" if "{" in content and "}" in content else "hocon"

            # Extract existing entries
            import re

            # Match: "path/to/file.hocon": true OR "path/to/file.hocon" = true
            pattern = r'["\']([^"\']+\.hocon)["\']'
            for match in re.finditer(pattern, content):
                existing_entries.add(match.group(1))

        # Add new entries
        for network_path in installed_networks:
            if network_path not in existing_entries:
                existing_entries.add(network_path)

        # Write updated manifest
        with open(manifest_path, "w", encoding="utf-8") as f:
            if manifest_format == "json":
                f.write("{\n")
                sorted_entries = sorted(existing_entries)
                for i, entry in enumerate(sorted_entries):
                    comma = "," if i < len(sorted_entries) - 1 else ""
                    f.write(f'    "{entry}": true{comma}\n')
                f.write("}\n")
            else:
                # HOCON format
                for entry in sorted(existing_entries):
                    f.write(f'"{entry}" = true\n')
