
# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
# END COPYRIGHT

import logging
from typing import Any

from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox


class AgentNetworkValidator:
    """Validator for both structure and instructions of agent network definition."""

    def __init__(self, network: dict[str, dict[str, Any]]):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.network = network

    def validate_network_keywords(self) -> list[str]:
        """
        Validation of the agent network keywords. Currently, only required "instructions" for non-function agents.

        :return: List of errors indicating agents and missing keywords
        """
        errors: list[str] = []

        self.logger.info("Validating agent network keywords...")

        for agent_name, agent in self.network.items():
            if agent.get("instructions") == "":
                error_msg = f"{agent_name} 'instructions' cannot be empty."
                errors.append(error_msg)

        self.logger.warning(str(errors))

        return errors

    def validate_network_structure(self) -> list[str]:
        """
        Comprehensive validation of the agent network structure.

        :return: List of any issues found.
        """
        errors: list[str] = []

        self.logger.info("Validating agent network structure...")

        # Find top agents
        top_agents = self._find_all_top_agents()

        if len(top_agents) == 0:
            errors.append("No top agent found in network")
        elif len(top_agents) > 1:
            errors.append(f"Multiple top agents found: {sorted(top_agents)}. Expected exactly one.")

        # Find cyclical agents
        cyclical_agents = self._find_cyclical_agents()
        if cyclical_agents:
            errors.append(f"Cyclical dependencies found in agents: {sorted(cyclical_agents)}")

        # Find unreachable agents (only meaningful if we have exactly one top agent)
        unreachable_agents = set()
        if len(top_agents) == 1:
            unreachable_agents = self._find_unreachable_agents(next(iter(top_agents)))
            if unreachable_agents:
                errors.append(f"Unreachable agents found: {sorted(unreachable_agents)}")

        # Validate that agent tools have corresponding nodes
        missing_nodes = self._find_missing_agent_nodes()
        if missing_nodes:
            for agent, missing_tools in missing_nodes.items():
                tools_str = ", ".join(f"'{tool}'" for tool in missing_tools)
                errors.append(
                    f"Agent '{agent}' references non-existent agent(s) in tools: {tools_str}"
                )

        self.logger.warning(str(errors))

        return errors

    def validate_toolbox_agents(self) -> list[str]:
        """
        Make sure that the toolbox agents have matching tools in toolbox.

        :return: List of error indicating any agents with no matching tools.
        """
        errors: list[str] = []

        self.logger.info("Validating toolbox agents...")

        # Get a dict of tools or error message if no toolbox found.
        tools: dict[str, Any] | str = GetToolbox().invoke(None, None)

        for agent_name, agent in self.network.items():
            if agent.get("instructions") is None:  # This is a toolbox agent
                if isinstance(tools, str):
                    errors.append(f"Toolbox is unavailable. Cannot create Toolbox agent '{agent_name}'.")
                if agent_name not in tools:
                    errors.append(f"Toolbox agent '{agent_name}' has no matching tool in toolbox.")

        return errors

    def validate_url(self) -> list[str]:
        """
        Check if URL of MCP servers and subnetworks are valid.

        :return: List of errors indicating invalid URL
        """
        errors: list[str] = []

        # Gather all URLs from MCP servers and subnetworks.
        subnetworks: dict[str, Any] | str = GetSubnetwork().invoke(None, None)
        if isinstance(subnetworks, dict):
            subnetworks: list = list(subnetworks.keys())
        else:
            subnetworks = []
        mcp_servers: list[str] = GetMcpTool().mcp_servers
        urls: list[str] = subnetworks + mcp_servers

        self.logger.info("Validating URLs for MCP tools and subnetwork...")

        for agent_name, agent in self.network.items():
            if agent.get("tools"):
                tools: list[str] = agent.get("tools")
                if tools:
                    for tool in tools:
                        if self._is_url_or_path(tool) and tool not in urls:
                            error_msg = f"Agent '{agent_name}' has invalid URL or path in tools: '{tool}'"
                            errors.append(error_msg)

        return errors

    def _find_all_top_agents(self) -> set[str]:
        """
        Find all top agents - agents that have down-chains but are not down-chains of others.

        :return: Set of top agent names
        """
        as_down_chains = set()
        has_down_chains = set()

        for agent_name, agent_config in self.network.items():
            down_chains: list[str] = agent_config.get("tools", [])
            if down_chains:
                has_down_chains.add(agent_name)
                as_down_chains.update(down_chains)

        return has_down_chains - as_down_chains

    def _find_cyclical_agents(self) -> set[str]:
        """
        Find agents that are part of cyclical dependencies using DFS.

        :return: Set of agent names that are part of cycles
        """
        # Step 1: Initialize state tracking for all agents
        # 0 = unvisited, 1 = currently being processed, 2 = fully processed
        state: dict[str, int] = {agent: 0 for agent in self.network.keys()}

        # Step 2: Set to collect all agents that are part of cycles
        cyclical_agents: set[str] = set()

        # Step 3: Start DFS from each unvisited agent to ensure we check all components
        # (the network might have disconnected parts)
        for agent in self.network.keys():
            if state[agent] == 0:  # Only start DFS from unvisited agents
                # Start DFS with empty path - this agent is the root of this search
                self._dfs_cycle_detection(agent, [], state, cyclical_agents)

        # Step 4: Return all agents that were found to be part of cycles
        return cyclical_agents

    def _dfs_cycle_detection(self, agent: str, path: list[str], state: dict[str, int], cyclical_agents: set[str]):
        """
        Perform Depth-First Search (DFS) traversal to detect cycles starting from a specific agent.

        :param agent: Current agent being visited
        :param path: Current path from start to current agent (for cycle identification)
        :param state: Dictionary tracking visit state of all agents (0=unvisited, 1=processing, 2=completed)
        :param cyclical_agents: Set to collect all agents that are part of any cycle
        """
        # Step 1: Check if we've encountered an agent currently being processed (back edge = cycle)
        if state[agent] == 1:
            # Cycle detected! The agent is already in our current processing path
            cycle_start_idx = path.index(agent)  # Find where the cycle starts in our path
            cycle_agents = set(path[cycle_start_idx:] + [agent])  # Extract all agents in the cycle
            cyclical_agents.update(cycle_agents)  # Add them to our result set
            return

        # Step 2: Skip if this agent was already fully processed in a previous DFS
        if state[agent] == 2:
            return  # Already completed, no need to process again

        # Step 3: Mark agent as currently being processed (prevents infinite recursion)
        state[agent] = 1

        # Step 4: Add current agent to the path (to track the route we took to get here)
        path.append(agent)

        # Step 5: Get all child agents (down_chains) of current agent
        down_chains: list[str] = self.network.get(agent, {}).get("tools", [])

        # Step 6: Recursively visit each child agent
        for child_agent in down_chains:
            # Only visit child if it exists in our network (safety check)
            if child_agent in self.network:
                self._dfs_cycle_detection(child_agent, path, state, cyclical_agents)

        # Step 7: Backtrack - remove current agent from path as we're done processing it
        path.pop()

        # Step 8: Mark agent as fully processed (all its descendants have been explored)
        state[agent] = 2

    def _find_unreachable_agents(self, top_agent: str) -> set[str]:
        """
        Find agents that are unreachable from the top agent using Depth-First Search (DFS) traversal.

        :param top_agent: The single top agent to start from
        :return: Set of unreachable agent names
        """
        # Step 1: Initialize set to track all agents we can reach from top agent
        reachable_agents: set[str] = set()

        # Step 2: Initialize visited set to track DFS traversal (prevents infinite loops in cycles)
        visited: set[str] = set()

        # Step 3: Start DFS traversal from the top agent to find all reachable agents
        self._dfs_reachability_traversal(top_agent, visited, reachable_agents)

        # Step 4: Get complete set of all agents in the network
        all_agents: set[str] = set(self.network.keys())

        # Step 5: Calculate unreachable agents by subtracting reachable from all agents
        unreachable_agents: set[str] = all_agents - reachable_agents

        # Step 6: Return the set of agents that cannot be reached from top agent
        return unreachable_agents

    def _is_url_or_path(self, tool: str) -> bool:
        """
        Check if a tool string is a URL or file path (not an agent name).

        :param tool: The tool string to check
        :return: True if tool is a URL or path, False otherwise
        """
        return (tool.startswith("/") or
                tool.startswith("http://") or
                tool.startswith("https://"))

    def _dfs_reachability_traversal(self, agent: str, visited: set[str], reachable_agents: set[str]):
        """
        Perform DFS traversal to find all agents reachable from a specific starting agent.

        :param agent: Current agent being visited
        :param visited: Set of agents already visited in this traversal (prevents infinite loops)
        :param reachable_agents: Set to collect all agents that can be reached
        """
        # Step 1: Check if we've already visited this agent or if it doesn't exist in network
        if agent in visited or agent not in self.network:
            return  # Skip already visited agents or non-existent agents

        # Step 2: Mark current agent as visited to prevent revisiting
        visited.add(agent)

        # Step 3: Add current agent to our reachable set
        reachable_agents.add(agent)

        # Step 4: Get all child agents (down_chains) of current agent
        down_chains: list[str] = self.network.get(agent, {}).get("tools", [])

        # Step 5: Recursively visit each child agent to continue the traversal
        for child_agent in down_chains:
            # Skip URL/path tools - they're not agents
            if not self._is_url_or_path(child_agent):
                # Visit each child - the recursion will handle visited check and network existence
                self._dfs_reachability_traversal(child_agent, visited, reachable_agents)

    def _find_missing_agent_nodes(self) -> dict[str, list[str]]:
        """
        Find agents referenced in "tools" lists that don't have corresponding nodes in the network.

        :return: Dictionary mapping agent names to list of tools that reference non-existent agents
                Format: {agent_name: [missing_tool1, missing_tool2, ...]}
        """
        missing_nodes: dict[str, list[str]] = {}

        # Iterate through all agents in the network
        for agent_name, agent_data in self.network.items():
            tools = agent_data.get("tools", [])

            # Check each tool in the agent's tools list
            for tool in tools:
                # Skip URL/path tools - they're not agents and don't need nodes
                if self._is_url_or_path(tool):
                    continue

                # If tool is an agent reference but has no node in network, it's invalid
                if tool not in self.network:
                    if agent_name not in missing_nodes:
                        missing_nodes[agent_name] = []
                    missing_nodes[agent_name].append(tool)

        return missing_nodes

    def get_top_agent(self) -> str:
        """
        Get the single top agent from a valid network.

        :return: Name of the top agent
        :raises ValueError: If network doesn't have exactly one top agent
        """
        top_agents = self._find_all_top_agents()

        if len(top_agents) == 0:
            raise ValueError("No top agent found in network")
        if len(top_agents) > 1:
            raise ValueError(f"Multiple top agents found: {sorted(top_agents)}. Expected exactly one.")

        return next(iter(top_agents))
