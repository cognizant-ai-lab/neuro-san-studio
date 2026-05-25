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

"""Registry for discovering agent networks from the installed package."""

import os
from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import List
from typing import Optional

from pyhocon import ConfigFactory


@dataclass
class AgentNetworkMetadata:
    """Metadata for an agent network."""

    name: str  # e.g., "music_nerd"
    group: str  # e.g., "basic"
    hocon_path: str  # e.g., "registries/basic/music_nerd.hocon"
    description: str = ""  # From metadata.description in HOCON
    tags: List[str] = field(default_factory=list)  # From metadata.tags in HOCON
    sample_queries: List[str] = field(default_factory=list)  # From metadata.sample_queries
    is_public: bool = True  # From manifest (true/false or public flag)


class AgentNetworkRegistry:
    """Discover and catalog agent networks from the installed package."""

    GROUPS = ["basic", "industry", "experimental", "tools", "root"]

    def __init__(self, source_dir: Optional[str] = None):
        """
        Initialize the registry.

        Args:
            source_dir: Path to neuro-san-studio installation.
                       If None, auto-discover from current directory or package location.
        """
        self.source_dir = source_dir or self._discover_source_dir()
        self.registries_dir = os.path.join(self.source_dir, "registries")

    def _discover_source_dir(self) -> str:
        """
        Auto-discover the source directory.

        Returns:
            Path to neuro-san-studio installation directory.

        Raises:
            FileNotFoundError: If registries directory cannot be found.
        """
        # Try current directory first (development mode)
        if os.path.exists("registries"):
            return os.getcwd()

        # Try to find registries via import (installed package mode)
        try:
            import registries

            if hasattr(registries, "__path__"):
                registries_path = registries.__path__[0]
                return os.path.dirname(registries_path)
        except ImportError:
            pass

        raise FileNotFoundError(
            "Cannot find registries directory. "
            "Make sure you're running from the neuro-san-studio directory "
            "or have neuro-san-studio installed."
        )

    def discover_networks(self) -> Dict[str, List[AgentNetworkMetadata]]:
        """
        Discover all agent networks organized by group.

        Returns:
            Dictionary mapping group names to lists of AgentNetworkMetadata.
            Example:
                {
                    "basic": [AgentNetworkMetadata(...), ...],
                    "industry": [...],
                    "experimental": [...],
                    "tools": [...]
                }
        """
        networks_by_group: Dict[str, List[AgentNetworkMetadata]] = {group: [] for group in self.GROUPS}

        for group in self.GROUPS:
            if group == "root":
                # Handle root-level networks (not in subdirectories)
                self._discover_root_networks(networks_by_group)
            else:
                # Handle group subdirectories
                group_dir = os.path.join(self.registries_dir, group)
                if not os.path.exists(group_dir):
                    continue

                # Read group manifest to get public/private status
                manifest_path = os.path.join(group_dir, "manifest.hocon")
                manifest = self._read_manifest(manifest_path) if os.path.exists(manifest_path) else {}

                # Scan for HOCON files
                for filename in os.listdir(group_dir):
                    if not filename.endswith(".hocon") or filename == "manifest.hocon":
                        continue

                    hocon_path = os.path.join(group, filename)
                    full_path = os.path.join(self.registries_dir, hocon_path)

                    # Check manifest for public/private status
                    manifest_key = f"{group}/{filename}"
                    is_public = self._is_public_from_manifest(manifest.get(manifest_key, True))

                    # Extract metadata
                    metadata = self.get_network_metadata(full_path, group, hocon_path, is_public)
                    networks_by_group[group].append(metadata)

        return networks_by_group

    def _discover_root_networks(self, networks_by_group: Dict[str, List[AgentNetworkMetadata]]) -> None:
        """
        Discover networks in the root registries/ directory.

        Args:
            networks_by_group: Dict to populate with root networks
        """
        # Only include certain root-level networks (not config files like aaosa.hocon)
        root_network_prefixes = ["agent_network_"]

        for filename in os.listdir(self.registries_dir):
            if not filename.endswith(".hocon"):
                continue

            # Skip manifest, config files, and subdirectories
            if filename in ["manifest.hocon", "llm_config.hocon"]:
                continue

            # Skip aaosa config files
            if filename.startswith("aaosa"):
                continue

            # Only include networks that match expected prefixes
            if not any(filename.startswith(prefix) for prefix in root_network_prefixes):
                continue

            full_path = os.path.join(self.registries_dir, filename)
            if not os.path.isfile(full_path):
                continue

            # Extract metadata
            metadata = self.get_network_metadata(full_path, "root", filename, is_public=True)
            networks_by_group["root"].append(metadata)

    def get_network_metadata(
        self, hocon_path: str, group: str, relative_path: str, is_public: bool = True
    ) -> AgentNetworkMetadata:
        """
        Parse HOCON file and extract metadata block.

        Args:
            hocon_path: Absolute path to HOCON file
            group: Group name (basic, industry, etc.)
            relative_path: Relative path from registries/ (e.g., "basic/music_nerd.hocon")
            is_public: Whether network is public (from manifest)

        Returns:
            AgentNetworkMetadata object
        """
        name = os.path.basename(hocon_path).replace(".hocon", "")

        # Default metadata
        metadata = AgentNetworkMetadata(
            name=name,
            group=group,
            hocon_path=relative_path,
            description="",
            tags=[],
            sample_queries=[],
            is_public=is_public,
        )

        # Parse HOCON to extract metadata block
        try:
            config = ConfigFactory.parse_file(hocon_path)

            # Extract metadata fields if present
            if "metadata" in config:
                meta_block = config["metadata"]
                metadata.description = meta_block.get("description", "")
                metadata.tags = meta_block.get("tags", [])
                metadata.sample_queries = meta_block.get("sample_queries", [])

        except Exception as e:
            # If parsing fails, return basic metadata
            print(f"Warning: Could not parse metadata from {hocon_path}: {e}")

        return metadata

    def _read_manifest(self, manifest_path: str) -> Dict:
        """
        Read and parse a manifest HOCON file.

        Args:
            manifest_path: Path to manifest.hocon file

        Returns:
            Parsed manifest dictionary
        """
        try:
            return ConfigFactory.parse_file(manifest_path)
        except Exception as e:
            print(f"Warning: Could not parse manifest {manifest_path}: {e}")
            return {}

    def _is_public_from_manifest(self, value) -> bool:
        """
        Determine if a network is public based on manifest value.

        Args:
            value: Manifest value (True, False, or dict with "public" key)

        Returns:
            True if public, False otherwise
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, dict):
            # Check for "public" key; default to True if not specified
            return value.get("public", True)
        return True
