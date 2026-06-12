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

"""Walk a HOCON network's `tools` list to extract its file dependencies."""

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
from neuro_san.internals.run_context.utils.external_agent_parsing import ExternalAgentParsing
from pyparsing.exceptions import ParseException

LLM_CLASSES = {"openai", "anthropic", "google", "bedrock", "azure"}


@dataclass
class AgentNetworkDependencies:
    """File-path dependencies for an agent network."""

    coded_tools: List[str] = field(default_factory=list)
    middleware: List[str] = field(default_factory=list)
    sub_networks: List[str] = field(default_factory=list)
    toolbox_tools: List[str] = field(default_factory=list)
    mcp_tools: List[str] = field(default_factory=list)


class DependencyAnalyzer:
    """Resolve dependencies referenced by a HOCON agent network."""

    def __init__(self, registries_dir: str, coded_tools_dir: str, middleware_dir: str):
        self.registries_dir = registries_dir
        self.coded_tools_dir = coded_tools_dir
        self.middleware_dir = middleware_dir

    def analyze_network(self, hocon_path: str) -> AgentNetworkDependencies:
        """Parse one HOCON file and extract its references (one level, no recursion)."""
        deps = AgentNetworkDependencies()
        try:
            restorer = AbstractAsyncConfigRestorer(file_purpose="dependency analysis", must_exist=True)
            config = restorer.restore(file_reference=hocon_path)
        except (FileNotFoundError, ParseException, ValueError):
            return deps

        self._extract_from_config(config, deps)
        for attr in ("coded_tools", "middleware", "sub_networks", "toolbox_tools", "mcp_tools"):
            setattr(deps, attr, list(dict.fromkeys(getattr(deps, attr))))
        return deps

    @staticmethod
    def _extract_from_config(config: Dict[str, Any], deps: AgentNetworkDependencies) -> None:
        tools = config.get("tools", [])
        if not isinstance(tools, list):
            return

        middleware_classes: Set[str] = set()
        for tool_spec in tools:
            if not isinstance(tool_spec, dict):
                continue

            for mw_spec in tool_spec.get("middleware", []) or []:
                if isinstance(mw_spec, dict):
                    cls = mw_spec.get("class")
                    if isinstance(cls, str):
                        middleware_classes.add(cls)
                        deps.middleware.append(cls)

            cls = tool_spec.get("class")
            if isinstance(cls, str) and cls.lower() not in LLM_CLASSES and cls not in middleware_classes:
                deps.coded_tools.append(cls)

            toolbox = tool_spec.get("toolbox")
            if isinstance(toolbox, str):
                deps.toolbox_tools.append(toolbox)

            for tool_ref in tool_spec.get("tools", []) or []:
                DependencyAnalyzer._classify_tool_ref(tool_ref, deps)

    @staticmethod
    def _classify_tool_ref(tool_ref: Any, deps: AgentNetworkDependencies) -> None:
        """Route a single entry from a tool's `tools:` list into the right deps bucket.

        Sub-network refs (`/name`) and MCP URLs are bundled; external HTTP-agent URLs
        (e.g. `http://localhost:8080/math_guy`) are called at runtime and intentionally
        dropped. Dict-form refs (`{"url": ..., "tools": [...]}`) are MCP per neuro-san.
        """
        if isinstance(tool_ref, dict):
            if ExternalAgentParsing.is_mcp_tool(tool_ref):
                url = tool_ref.get("url")
                if isinstance(url, str):
                    deps.mcp_tools.append(url)
            return
        if not isinstance(tool_ref, str):
            return
        if tool_ref.startswith("/"):
            deps.sub_networks.append(tool_ref)
        elif ExternalAgentParsing.is_mcp_tool(tool_ref):
            deps.mcp_tools.append(tool_ref)

    def resolve_coded_tool_path(self, class_path: str, context_dir: Optional[str] = None) -> Optional[str]:
        """Map a Python class path (e.g. 'pkg.module.Class') to its source file under coded_tools/ or middleware/."""
        parts = class_path.split(".")

        if parts[0] in ("middleware", "coded_tools"):
            root = self.middleware_dir if parts[0] == "middleware" else self.coded_tools_dir
            module_file = os.path.join(root, *parts[1:-1]) + ".py"
            return f"{parts[0]}/" + "/".join(parts[1:-1]) + ".py" if os.path.exists(module_file) else None

        # Short reference like "order_api.OrderAPI" — resolve up the context hierarchy, the way
        # neuro-san does (abstract_class_activation._attempt_resolve): try the per-network dir
        # first, then strip one trailing level at a time down to coded_tools/ root. So a tool at
        # the group level (coded_tools/basic/accountant.py) is found even when the network's
        # context_dir is basic/music_nerd_pro (issue #1147).
        if len(parts) == 2 and context_dir:
            context_parts = context_dir.split("/")
            module = parts[0]
            for depth in range(len(context_parts), -1, -1):
                rel = "/".join([*context_parts[:depth], f"{module}.py"])
                if os.path.exists(os.path.join(self.coded_tools_dir, rel)):
                    return f"coded_tools/{rel}"

        # Long-form reference under coded_tools/
        if os.path.exists(os.path.join(self.coded_tools_dir, *parts[:-1]) + ".py"):
            return "coded_tools/" + "/".join(parts[:-1]) + ".py"

        # Package directory (__init__.py)
        if os.path.isdir(os.path.join(self.coded_tools_dir, *parts[:-1])):
            return "coded_tools/" + "/".join(parts[:-1])

        return None

    def resolve_sub_network(self, network_ref: str) -> Optional[str]:
        """Map a sub-network reference like '/agent_network_editor' to a path under registries/."""
        name = network_ref.lstrip("/")
        if not name.endswith(".hocon"):
            name = name + ".hocon"
        return name if os.path.exists(os.path.join(self.registries_dir, name)) else None

    def get_transitive_dependencies(
        self, hocon_path: str, visited: Optional[Set[str]] = None
    ) -> AgentNetworkDependencies:
        """Recursively collect dependencies from a network and its sub-networks."""
        if visited is None:
            visited = set()
        abs_path = os.path.abspath(hocon_path)
        if abs_path in visited:
            return AgentNetworkDependencies()
        visited.add(abs_path)

        # context_dir lets us resolve short-form coded-tool refs ("module.Class") relative
        # to the network's group directory. A network at `<registries>/basic/foo.hocon` lives
        # under group `basic`, so its context_dir is `basic/foo`. Top-level networks
        # (`<registries>/foo.hocon`) have no group context.
        rel_path = os.path.relpath(hocon_path, self.registries_dir)
        parts = rel_path.split(os.sep)
        context_group = parts[0] if len(parts) >= 2 else None
        context_dir = f"{context_group}/{Path(hocon_path).stem}" if context_group else None

        deps = self.analyze_network(hocon_path)
        deps.coded_tools = [p for p in (self.resolve_coded_tool_path(c, context_dir) for c in deps.coded_tools) if p]
        deps.middleware = [p for p in (self.resolve_coded_tool_path(m) for m in deps.middleware) if p]

        for sub_ref in list(deps.sub_networks):
            sub_rel = self.resolve_sub_network(sub_ref)
            if not sub_rel:
                continue
            sub_deps = self.get_transitive_dependencies(os.path.join(self.registries_dir, sub_rel), visited)
            for attr in ("coded_tools", "middleware", "sub_networks", "toolbox_tools", "mcp_tools"):
                merged = getattr(deps, attr) + [x for x in getattr(sub_deps, attr) if x not in getattr(deps, attr)]
                setattr(deps, attr, merged)
        return deps
