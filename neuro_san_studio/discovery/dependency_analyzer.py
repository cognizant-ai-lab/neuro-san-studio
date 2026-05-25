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
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer
from pyparsing.exceptions import ParseException


@dataclass
class AgentNetworkDependencies:
    """Complete dependency graph for an agent network."""

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

    async def analyze_network(self, hocon_path: str) -> AgentNetworkDependencies:
        """
        Parse HOCON file and extract all dependency references.

        Uses AbstractAsyncConfigRestorer which automatically resolves includes
        and handles both .hocon and .json files.

        Args:
            hocon_path: Absolute path to HOCON file

        Returns:
            Dependency object with all referenced files/tools
        """
        dependencies = AgentNetworkDependencies()

        # Parse HOCON with AbstractAsyncConfigRestorer (auto-resolves includes)
        try:
            restorer = AbstractAsyncConfigRestorer(file_purpose="agent network dependency analysis", must_exist=True)
            config = await restorer.async_restore(file_reference=hocon_path)
            self._extract_from_config(config, dependencies)

        except FileNotFoundError:
            print(f"Warning: HOCON file not found: {hocon_path}")
            return dependencies

        except ParseException as parse_error:
            print(f"Warning: Failed to parse {hocon_path}: {parse_error}")
            return dependencies

        except Exception as e:
            print(f"Warning: Unexpected error parsing {hocon_path}: {e}")
            return dependencies

        # Deduplicate lists
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
            config: Parsed HOCON config dictionary (from AbstractAsyncConfigRestorer)
            dependencies: AgentNetworkDependencies to populate
        """
        llm_classes = {"openai", "anthropic", "google", "bedrock", "azure"}
        middleware_class_paths = set()

        # Extract from tools array
        tools = config.get("tools", [])
        if not isinstance(tools, list):
            return

        for tool_spec in tools:
            if not isinstance(tool_spec, dict):
                continue

            # Extract middleware first
            middleware_list = tool_spec.get("middleware", [])
            if isinstance(middleware_list, list):
                for mw_spec in middleware_list:
                    if isinstance(mw_spec, dict) and "class" in mw_spec:
                        class_path = mw_spec["class"]
                        if isinstance(class_path, str):
                            middleware_class_paths.add(class_path)
                            dependencies.middleware.append(class_path)

            # Extract coded tools (class field)
            if "class" in tool_spec:
                class_path = tool_spec["class"]
                if isinstance(class_path, str):
                    if class_path.lower() not in llm_classes and class_path not in middleware_class_paths:
                        dependencies.coded_tools.append(class_path)

            # Extract toolbox
            if "toolbox" in tool_spec:
                toolbox = tool_spec["toolbox"]
                if isinstance(toolbox, str):
                    dependencies.toolbox_tools.append(toolbox)

            # Extract sub-networks and MCP from tools list
            tools_list = tool_spec.get("tools", [])
            if isinstance(tools_list, list):
                for tool_name in tools_list:
                    if isinstance(tool_name, str):
                        if tool_name.startswith("/"):
                            dependencies.sub_networks.append(tool_name)
                        elif tool_name.startswith("https://"):
                            dependencies.mcp_tools.append(tool_name)

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

    async def get_transitive_dependencies(
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
            if len(parts) >= 2 and parts[0] in ["basic", "industry", "experimental", "tools", "root"]:
                context_group = parts[0]

        # Infer context directory for coded tools (e.g., "basic/coffee_finder_advanced")
        context_dir = None
        if context_group:
            network_name = Path(hocon_path).stem  # Remove .hocon extension
            context_dir = f"{context_group}/{network_name}"

        # Analyze this network (NOW ASYNC)
        deps = await self.analyze_network(hocon_path)

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

        # Recursively analyze sub-networks (NOW ASYNC)
        for sub_network_ref in deps.sub_networks:
            sub_network_rel = self.resolve_sub_network(sub_network_ref)
            if sub_network_rel:
                sub_network_path = os.path.join(self.registries_dir, sub_network_rel)
                if os.path.exists(sub_network_path):
                    sub_deps = await self.get_transitive_dependencies(sub_network_path, visited)

                    # Merge dependencies (deduplicate)
                    deps.coded_tools.extend([t for t in sub_deps.coded_tools if t not in deps.coded_tools])
                    deps.middleware.extend([m for m in sub_deps.middleware if m not in deps.middleware])
                    deps.sub_networks.extend([s for s in sub_deps.sub_networks if s not in deps.sub_networks])
                    deps.toolbox_tools.extend([t for t in sub_deps.toolbox_tools if t not in deps.toolbox_tools])
                    deps.mcp_tools.extend([m for m in sub_deps.mcp_tools if m not in deps.mcp_tools])

        return deps
