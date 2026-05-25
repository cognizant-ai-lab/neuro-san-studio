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

"""Analyze agent network HOCON files to extract all dependencies."""

import os
import re
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from pyhocon import ConfigFactory


@dataclass
class AgentNetworkDependencies:
    """Complete dependency graph for an agent network."""

    hocon_includes: List[str] = field(default_factory=list)  # Include directives
    coded_tools: List[str] = field(default_factory=list)  # class field paths
    middleware: List[str] = field(default_factory=list)  # middleware class paths
    sub_networks: List[str] = field(default_factory=list)  # /agent_name references
    toolbox_tools: List[str] = field(default_factory=list)  # toolbox field values
    mcp_tools: List[str] = field(default_factory=list)  # https:// MCP URLs


class DependencyAnalyzer:
    """Analyze HOCON files to extract dependencies."""

    def __init__(self, registries_dir: str, coded_tools_dir: str, middleware_dir: str):
        """
        Initialize the dependency analyzer.

        Args:
            registries_dir: Path to registries/ directory
            coded_tools_dir: Path to coded_tools/ directory
            middleware_dir: Path to middleware/ directory
        """
        self.registries_dir = registries_dir
        self.coded_tools_dir = coded_tools_dir
        self.middleware_dir = middleware_dir

    def analyze_network(self, hocon_path: str) -> AgentNetworkDependencies:
        """
        Parse HOCON file and extract all dependency references.

        Uses ConfigFactory for structured parsing with fallback to partial parsing
        when variable substitution fails.

        Args:
            hocon_path: Absolute path to HOCON file

        Returns:
            Dependency object with all referenced files/tools
        """
        dependencies = AgentNetworkDependencies()

        # Extract includes from raw file content (ConfigFactory resolves them)
        dependencies.hocon_includes = self._extract_includes(hocon_path)

        # Try structured parsing with ConfigFactory first
        try:
            config = ConfigFactory.parse_file(hocon_path)
            self._extract_from_config(config, dependencies)

        except Exception as parse_error:
            # ConfigFactory failed (likely due to variable substitution)
            # Fall back to partial parsing from raw config tree
            try:
                # Parse without substitution resolution
                from pyhocon import ConfigFactory as CF, ConfigTree

                with open(hocon_path, encoding="utf-8") as f:
                    config_tree = CF.parse_string(f.read(), resolve=False)

                if isinstance(config_tree, ConfigTree):
                    self._extract_from_config_tree(config_tree, dependencies)

            except Exception as fallback_error:
                print(f"Warning: Could not parse {hocon_path}: {parse_error}")

        # Deduplicate lists
        dependencies.hocon_includes = list(dict.fromkeys(dependencies.hocon_includes))
        dependencies.coded_tools = list(dict.fromkeys(dependencies.coded_tools))
        dependencies.middleware = list(dict.fromkeys(dependencies.middleware))
        dependencies.sub_networks = list(dict.fromkeys(dependencies.sub_networks))
        dependencies.toolbox_tools = list(dict.fromkeys(dependencies.toolbox_tools))
        dependencies.mcp_tools = list(dict.fromkeys(dependencies.mcp_tools))

        return dependencies

    def _extract_from_config(self, config: Dict[str, Any], dependencies: AgentNetworkDependencies) -> None:
        """
        Extract dependencies from fully resolved config.

        Args:
            config: Parsed HOCON config dictionary
            dependencies: AgentNetworkDependencies to populate
        """
        llm_classes = {"openai", "anthropic", "google", "bedrock", "azure"}
        middleware_class_paths = set()

        # Extract from tools array
        for tool_spec in config.get("tools", []):
            if not isinstance(tool_spec, dict):
                continue

            # Extract middleware first
            if "middleware" in tool_spec:
                for mw_spec in tool_spec.get("middleware", []):
                    if isinstance(mw_spec, dict) and "class" in mw_spec:
                        class_path = mw_spec["class"]
                        middleware_class_paths.add(class_path)
                        dependencies.middleware.append(class_path)

            # Extract coded tools (class field)
            if "class" in tool_spec:
                class_path = tool_spec["class"]
                if class_path.lower() not in llm_classes and class_path not in middleware_class_paths:
                    dependencies.coded_tools.append(class_path)

            # Extract toolbox
            if "toolbox" in tool_spec:
                dependencies.toolbox_tools.append(tool_spec["toolbox"])

            # Extract sub-networks and MCP from tools list
            for tool_name in tool_spec.get("tools", []):
                if isinstance(tool_name, str):
                    if tool_name.startswith("/"):
                        dependencies.sub_networks.append(tool_name)
                    elif tool_name.startswith("https://"):
                        dependencies.mcp_tools.append(tool_name)

    def _extract_from_config_tree(self, config_tree: Any, dependencies: AgentNetworkDependencies) -> None:
        """
        Extract dependencies from unresolved config tree.

        This is used as fallback when variable substitution fails.

        Args:
            config_tree: Unresolved HOCON ConfigTree
            dependencies: AgentNetworkDependencies to populate
        """
        llm_classes = {"openai", "anthropic", "google", "bedrock", "azure"}
        middleware_class_paths = set()

        # Try to extract tools array
        try:
            tools = config_tree.get("tools", [])
            if not isinstance(tools, list):
                return

            for tool_spec in tools:
                if not isinstance(tool_spec, dict):
                    continue

                # Extract middleware first
                if "middleware" in tool_spec:
                    middleware_list = tool_spec.get("middleware", [])
                    if isinstance(middleware_list, list):
                        for mw_spec in middleware_list:
                            if isinstance(mw_spec, dict) and "class" in mw_spec:
                                class_path = str(mw_spec["class"])
                                middleware_class_paths.add(class_path)
                                dependencies.middleware.append(class_path)

                # Extract coded tools
                if "class" in tool_spec:
                    class_path = str(tool_spec["class"])
                    if class_path.lower() not in llm_classes and class_path not in middleware_class_paths:
                        dependencies.coded_tools.append(class_path)

                # Extract toolbox
                if "toolbox" in tool_spec:
                    dependencies.toolbox_tools.append(str(tool_spec["toolbox"]))

                # Extract sub-networks and MCP from tools list
                if "tools" in tool_spec:
                    tools_list = tool_spec.get("tools", [])
                    if isinstance(tools_list, list):
                        for tool_name in tools_list:
                            if isinstance(tool_name, str):
                                if tool_name.startswith("/"):
                                    dependencies.sub_networks.append(tool_name)
                                elif tool_name.startswith("https://"):
                                    dependencies.mcp_tools.append(tool_name)

        except Exception as e:
            print(f"Warning: Partial extraction failed: {e}")

    def _extract_includes(self, hocon_path: str) -> List[str]:
        """
        Extract include directives from HOCON file.

        Uses line-by-line parsing to find include statements, avoiding regex.

        Args:
            hocon_path: Path to HOCON file

        Returns:
            List of include paths (e.g., ["registries/aaosa_basic.hocon"])
        """
        includes = []
        try:
            with open(hocon_path, encoding="utf-8") as f:
                for line in f:
                    # Strip comments
                    line = line.split('#')[0].split('//')[0].strip()

                    # Check if line starts with 'include'
                    if line.startswith('include '):
                        # Extract the quoted path
                        include_part = line[8:].strip()  # Skip 'include '

                        # Find the quoted string
                        for quote_char in ['"', "'"]:
                            if quote_char in include_part:
                                start = include_part.index(quote_char) + 1
                                end = include_part.index(quote_char, start)
                                include_path = include_part[start:end]
                                includes.append(include_path)
                                break

        except Exception as e:
            print(f"Warning: Could not extract includes from {hocon_path}: {e}")

        return includes

    def resolve_coded_tool_path(self, class_path: str, context_dir: Optional[str] = None) -> Optional[str]:
        """
        Convert class path to file path.

        Args:
            class_path: Class path like "order_api.OrderAPI" or "experimental.kwik_agents.list_topics.ListTopics"
            context_dir: Optional context directory (e.g., "basic/coffee_finder_advanced")

        Returns:
            File path relative to project root, or None if not resolvable

        Examples:
            "order_api.OrderAPI" + "basic/coffee_finder_advanced"
                → "coded_tools/basic/coffee_finder_advanced/order_api.py"
            "experimental.kwik_agents.list_topics.ListTopics"
                → "coded_tools/experimental/kwik_agents/list_topics.py"
            "middleware.agent_network_designer.agent_network_definition_middleware.AgentNetworkDefinitionMiddleware"
                → "middleware/agent_network_designer/agent_network_definition_middleware.py"
        """
        parts = class_path.split(".")

        # Middleware check
        if parts[0] == "middleware":
            # middleware.path.to.module.Class → middleware/path/to/module.py
            module_path = "/".join(parts[:-1]) + ".py"
            full_path = os.path.join(self.middleware_dir, *parts[1:-1]) + ".py"
            if os.path.exists(full_path):
                return module_path
            return None

        # CodedTools check - explicit namespace
        if parts[0] == "coded_tools":
            # coded_tools.path.to.module.Class → coded_tools/path/to/module.py
            module_path = "/".join(parts[:-1]) + ".py"
            full_path = os.path.join(self.coded_tools_dir, *parts[1:-1]) + ".py"
            if os.path.exists(full_path):
                return module_path
            return None

        # Short path - infer from context
        if len(parts) == 2 and context_dir:  # e.g., "order_api.OrderAPI"
            # Try context directory first
            candidate = os.path.join(self.coded_tools_dir, context_dir, parts[0] + ".py")
            if os.path.exists(candidate):
                return f"coded_tools/{context_dir}/{parts[0]}.py"

        # Long path - explicit namespace (e.g., "experimental.kwik_agents.list_topics.ListTopics")
        module_path = os.path.join(self.coded_tools_dir, *parts[:-1]) + ".py"
        if os.path.exists(module_path):
            return "coded_tools/" + "/".join(parts[:-1]) + ".py"

        # Try as package directory (e.g., experimental/kwik_agents/__init__.py)
        package_path = os.path.join(self.coded_tools_dir, *parts[:-1])
        if os.path.isdir(package_path):
            return f"coded_tools/{'/'.join(parts[:-1])}"

        return None

    def resolve_sub_network(self, network_ref: str) -> Optional[str]:
        """
        Convert sub-network reference to HOCON file path.

        Args:
            network_ref: Sub-network reference like "/agent_network_editor" or "/industry/macys"

        Returns:
            File path relative to registries directory, or None if not found

        Examples:
            "/agent_network_editor" → "registries/agent_network_editor.hocon"
            "/industry/macys" → "registries/industry/macys.hocon"
        """
        # Remove leading slash
        network_name = network_ref.lstrip("/")

        # Try direct path
        hocon_path = os.path.join(self.registries_dir, network_name + ".hocon")
        if os.path.exists(hocon_path):
            return network_name + ".hocon"

        # Try with .hocon if already included
        hocon_path = os.path.join(self.registries_dir, network_name)
        if os.path.exists(hocon_path):
            return network_name

        return None

    def get_transitive_dependencies(
        self, hocon_path: str, visited: Optional[Set[str]] = None, context_group: Optional[str] = None
    ) -> AgentNetworkDependencies:
        """
        Recursively resolve ALL dependencies (including sub-networks' dependencies).

        Args:
            hocon_path: Path to HOCON file
            visited: Set of already-visited paths (for cycle detection)
            context_group: Group name (e.g., "basic") for resolving short coded tool paths

        Returns:
            Merged dependency set with all transitive dependencies
        """
        if visited is None:
            visited = set()

        # Normalize path
        abs_path = os.path.abspath(hocon_path)

        # Cycle detection
        if abs_path in visited:
            return AgentNetworkDependencies()

        visited.add(abs_path)

        # Infer context group from path if not provided
        if context_group is None:
            # Extract group from path like "registries/basic/coffee_finder.hocon"
            rel_path = os.path.relpath(hocon_path, self.registries_dir)
            parts = rel_path.split(os.sep)
            if len(parts) >= 2 and parts[0] in ["basic", "industry", "experimental", "tools"]:
                context_group = parts[0]

        # Infer context directory for coded tools (e.g., "basic/coffee_finder_advanced")
        context_dir = None
        if context_group:
            network_name = Path(hocon_path).stem  # Remove .hocon extension
            context_dir = f"{context_group}/{network_name}"

        # Analyze this network
        deps = self.analyze_network(hocon_path)

        # Resolve file paths for THIS network's coded tools and middleware (before recursion)
        resolved_coded_tools = []
        for class_path in deps.coded_tools:
            resolved_path = self.resolve_coded_tool_path(class_path, context_dir)
            if resolved_path:
                resolved_coded_tools.append(resolved_path)

        resolved_middleware = []
        for class_path in deps.middleware:
            resolved_path = self.resolve_coded_tool_path(class_path)
            if resolved_path:
                resolved_middleware.append(resolved_path)

        deps.coded_tools = resolved_coded_tools
        deps.middleware = resolved_middleware

        # Recursively analyze sub-networks (AFTER resolving this network's dependencies)
        for sub_network_ref in deps.sub_networks:
            sub_network_rel = self.resolve_sub_network(sub_network_ref)
            if sub_network_rel:
                sub_network_path = os.path.join(self.registries_dir, sub_network_rel)
                if os.path.exists(sub_network_path):
                    sub_deps = self.get_transitive_dependencies(sub_network_path, visited)

                    # Merge dependencies (deduplicate)
                    deps.hocon_includes.extend([i for i in sub_deps.hocon_includes if i not in deps.hocon_includes])
                    deps.coded_tools.extend([t for t in sub_deps.coded_tools if t not in deps.coded_tools])
                    deps.middleware.extend([m for m in sub_deps.middleware if m not in deps.middleware])
                    deps.sub_networks.extend([s for s in sub_deps.sub_networks if s not in deps.sub_networks])
                    deps.toolbox_tools.extend([t for t in sub_deps.toolbox_tools if t not in deps.toolbox_tools])
                    deps.mcp_tools.extend([m for m in sub_deps.mcp_tools if m not in deps.mcp_tools])

        return deps
