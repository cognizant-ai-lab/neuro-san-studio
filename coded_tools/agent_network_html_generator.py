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

import asyncio
import json
import os
import webbrowser
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.persistence.agent_network_restorer import AgentNetworkRestorer
from pyvis.network import Network


class AgentNetworkHtmlGenerator(CodedTool):
    """
    CodedTool implementation which draw agent_network to html file
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
            to the coded tool and whose values are the values passed for
            them by the calling agent.  This dictionary is to be treated as
            read-only.

            The argument dictionary expects the following keys:
                "agent_name"

        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool
            implementation adding the data is not invoke()-ed more than
            once.

            Keys expected for this implementation are:
                "agent_name"
        :return: successful sent message ID or error message
        """

        # Try to get "agent_name" from args; if the corresponding HOCON file doesn't exist, fall back to sly_data.
        agent_name: str = args.get("agent_name")
        hocon_file = f"registries/{agent_name}.hocon"

        if not os.path.isfile(hocon_file):
            print(f"Cannot find agent network HOCON file for '{agent_name}' from args.")
            print("Attempting to get 'agent_name' from sly_data instead.")
            agent_name = sly_data.get("agent_network_name")
            hocon_file = f"registries/{agent_name}.hocon"

        # Final validation: ensure agent_name is set and the file exists.
        if not agent_name or not os.path.isfile(hocon_file):
            return f"Error: HOCON file not found for agent '{agent_name}'. Expected at: registries/{agent_name}.hocon"

        print(f"Generating HTML file for {agent_name}")

        # Create dict from hocon
        try:
            network_dict = AgentNetworkRestorer().restore("registries/" + agent_name + ".hocon").get_config()
        except FileNotFoundError as file_not_found_error:
            print(file_not_found_error)
            return f"Trying to load {agent_name}.hocon: {file_not_found_error}."

        # Generate html
        generate_html(agent_name, network_dict)

        # Open it on chrome
        webbrowser.get("open -a 'Google Chrome' %s").open(f"{agent_name}.html")

        return f"{agent_name}.html was successfully generated."

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)


def generate_html(agent_name: str, network_dict: Dict[str, Any]):
    """
    Create a html file from a dictionary.

    :param network_dict: .

    :return: successful sent message ID or error statement
    """

    net = Network(height="1000px", width="100%", directed=True)  # Changed to directed for hierarchy

    # Set hierarchical layout options
    net.set_options(
        """
    var options = {
    "nodes": {
        "font": { "color": "#ffffff" },
        "borderWidth": 2
    },
    "layout": {
        "hierarchical": {
            "enabled": true,
            "direction": "UD",
            "sortMethod": "directed",
            "nodeSpacing": 200,
            "levelSeparation": 150
        }
    },
    "interaction": {
        "hover": true,
        "dragNodes": true
    },
    "physics": {
        "enabled": false,
        "hierarchicalRepulsion": {
            "nodeDistance": 120
        }
    }
    }
    """
    )

    # First, identify root nodes and build dependency graph
    tools = network_dict.get("tools", [])
    all_tools = {tool["name"] for tool in tools}

    # Build a tools dictionary for easy lookup
    tools_dict = {tool["name"]: tool for tool in tools}

    # Find which nodes are referenced as tools (have incoming edges)
    referenced_tools = set()
    for node in tools:
        if "tools" in node:
            referenced_tools.update(node["tools"])

    # Root nodes are those not referenced by others
    root_nodes = all_tools - referenced_tools

    # Calculate levels using BFS from root nodes
    def calculate_levels():
        levels = {}
        queue = [(root, 0) for root in root_nodes]
        visited = set()

        while queue:
            node_name, level = queue.pop(0)

            if node_name in visited:
                continue
            visited.add(node_name)
            levels[node_name] = level

            # Add children to queue with next level
            if node_name in tools_dict and "tools" in tools_dict[node_name]:
                for child in tools_dict[node_name]["tools"]:
                    if child not in visited:
                        queue.append((child, level + 1))

        # Handle any orphaned nodes (shouldn't happen in well-formed data)
        for tool_name in all_tools:
            if tool_name not in levels:
                levels[tool_name] = max(levels.values()) + 1 if levels else 0

        return levels

    node_levels = calculate_levels()

    # Add nodes with calculated levels and different color for roots
    for node in tools:
        node_name = node["name"]
        tooltip = json.dumps(node, indent=4)
        level = node_levels[node_name]

        # Force rectangular box-shaped nodes
        net.add_node(
            node_name,
            label=node_name,
            color="#4169E1",  # Royal blue for all nodes,
            shape="box",
            widthConstraint={"minimum": 180, "maximum": 200},
            heightConstraint={"minimum": 80},
            font={"multi": "html"},
            title=tooltip,
            level=level  # Explicitly set calculated hierarchy level
        )

    # Add edges
    for node in [n for n in network_dict.get("tools", []) if "tools" in n]:
        node_name = node["name"]
        tools = node["tools"]
        for tool in tools:
            net.add_edge(node_name, tool)

    # Show the graph
    net.show(f"{agent_name}.html", notebook=False)
