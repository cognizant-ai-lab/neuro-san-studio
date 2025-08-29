# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
from copy import deepcopy
import logging
from typing import Any
from typing import Dict
from typing import Union

import aiofiles  # Import for asynchronous file operations
from neuro_san.interfaces.coded_tool import CodedTool

WRITE_TO_FILE = True
OUTPUT_PATH = "registries/"
AGENT_NETWORK_NAME = "AutomaticallyDesignedAgentNetwork"
HOCON_HEADER_START = (
    "{\n"
    "# Importing content from other HOCON files\n"
    "# The include keyword must be unquoted and followed by a quoted URL or file path.\n"
    "# File paths should be absolute or relative to the script's working directory, not the HOCON file location.\n"
    '# This "aaosa.hocon" file contains key-value pairs used for substitution.\n'
    "# Specifically, it provides values for the following keys:\n"
    "#   - aaosa_call\n"
    "#   - aaosa_command\n"
    "#   - aaosa_instructions\n"
    "# IMPORTANT:\n"
    "# Ensure that you run `python -m run` from the top level of the repository.\n"
    "# The path to this substitution file is **relative to the top-level directory**,\n"
    "# so running the script from elsewhere may result in file not found errors.\n"
    'include "registries/aaosa.hocon"\n'
    '    "llm_config": {\n'
    '        "model_name": "gpt-4o",\n'
    "    },\n"
    '    "commondefs": {\n'
    '        "replacement_strings": {\n'
    '            "instructions_prefix": """\n'
    "You are part of a "
)
HOCON_HEADER_REMAINDER = (
    " of assistants.\n"
    "Only answer inquiries that are directly within your area of expertise.\n"
    "Do not try to help for other matters.\n"
    "Do not mention what you can NOT do. Only mention what you can do.\n"
    '            """,\n'
    '            "demo_mode": "You are part of a demo system, so when queried, make up a realistic response as if you '
    'are actually grounded in real data or you are operating a real application API or microservice."\n'
    "        },\n"
    "    }\n"
    '"tools": [\n'
)
TOP_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": {\n'
    '                "description": """\n'
    "An assistant that answer inquiries from the user.\n"
    '                """\n'
    "            },\n"
    '            "instructions": """\n'
    "{instructions_prefix}\n"
    "%s\n"
    '            """ ${aaosa_instructions},\n'
    '            "tools": [%s]\n'
    "        },\n"
)
REGULAR_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": ${aaosa_call},\n'
    '            "instructions": """\n'
    "{instructions_prefix}\n"
    "%s\n"
    '            """ ${aaosa_instructions},\n'
    '            "command": ${aaosa_command},\n'
    '            "tools": [%s]\n'
    "        },\n"
)
LEAF_NODE_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": ${aaosa_call},\n'
    '            "instructions": """\n'
    "{instructions_prefix} {demo_mode}\n"
    "%s\n"
    '            """,\n'
    "        },\n"
)


async def modify_registry(the_agent_network_hocon_str, the_agent_network_name):
    """
    Writes the agent network to a file and updates the manifest.hocon file.
    :param the_agent_network_hocon_str: The agent network hocon string
    :param the_agent_network_name: The file name, without the .hocon extension
    :return:
    """
    # Write the agent network file
    file_path = OUTPUT_PATH + the_agent_network_name + ".hocon"
    async with aiofiles.open(file_path, "w") as file:
        await file.write(the_agent_network_hocon_str)
    # Update the manifest.hocon file
    manifest_path = OUTPUT_PATH + "manifest.hocon"
    manifest_entry = f'    "{the_agent_network_name}.hocon": true,'
    # Read the current manifest content
    async with aiofiles.open(manifest_path, "r") as file:
        manifest_content = await file.read()
    # Find the position to insert the new entry (before the closing brace)
    insert_position = manifest_content.rfind("}")
    if insert_position != -1:
        # Check if the entry already exists to avoid duplicates
        if f'"{the_agent_network_name}.hocon"' not in manifest_content:
            # Insert the new entry
            updated_content = (
                manifest_content[:insert_position] + "\n" + manifest_entry + manifest_content[insert_position:]
            )

            # Write the updated content back to the manifest file
            async with aiofiles.open(manifest_path, "w") as file:
                await file.write(updated_content)


class CreateAgentNetworkHocon(CodedTool):
    """
    CodedTool implementation which provides a way to get a full hocon of a designed agent network from the sly data
    """

    def __init__(self):
        self.agents = None

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "app_name" the name of the One Cognizant app for which the URL is needed.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                The full agent network hocon as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        # Use copy here since we may have to rearrange the dictionary to get the correct frontman
        self.agents = deepcopy(sly_data.get(AGENT_NETWORK_NAME))
        if not self.agents:
            return "Error: No network in sly data!"

        the_agent_network_name: str = args.get("agent_network_name", "")
        # Add the agent network name into sly data.
        sly_data["agent_name"] = the_agent_network_name
        if the_agent_network_name == "":
            return "Error: No agent_name provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>GetAgentNetworkHocon>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Network Name: %s", str(the_agent_network_name))
        the_agent_network_hocon_str = self.get_agent_network_hocon(the_agent_network_name)
        logger.info("The resulting agent network: \n %s", str(the_agent_network_hocon_str))
        if WRITE_TO_FILE:
            await modify_registry(the_agent_network_hocon_str, the_agent_network_name)
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return the_agent_network_hocon_str

    def get_agent_network_hocon(self, agent_network_name):
        """
        Returns a full agent network hocon.
        """
        # Make sure that the top agent is the first agent.
        # Find or set the top agent
        top_agent_name: str = None
        for name, agent in self.agents.items():
            if agent.get("top_agent"):
                top_agent_name = name
                break
        if not top_agent_name:
            # No top agent found, make the first one the top agent
            first_name: str = next(iter(self.agents))
            self.agents[first_name]["top_agent"] = True
            top_agent_name = first_name

        # Move top agent to front
        if top_agent_name != next(iter(self.agents)):
            top_agent: Dict[str, Any] = self.agents.pop(top_agent_name)
            self.agents = {top_agent_name: top_agent, **self.agents}

        agent_network_hocon = HOCON_HEADER_START + agent_network_name + HOCON_HEADER_REMAINDER
        for agent_name, agent in self.agents.items():
            tools = ""
            if agent.get("down_chains"):
                for j, down_chain in enumerate(agent["down_chains"]):
                    tools = tools + '"' + down_chain + '"'
                    if j < len(agent["down_chains"]) - 1:
                        tools = tools + ","
            if agent["top_agent"] is True:  # top agent
                an_agent = TOP_AGENT_TEMPLATE % (
                    agent_name,
                    agent["instructions"],
                    tools,
                )
            elif agent.get("down_chains"):
                an_agent = REGULAR_AGENT_TEMPLATE % (
                    agent_name,
                    agent["instructions"],
                    tools,
                )
            else:  # leaf node agent
                an_agent = LEAF_NODE_AGENT_TEMPLATE % (
                    agent_name,
                    agent["instructions"],
                )
            agent_network_hocon = agent_network_hocon + an_agent
        agent_network_hocon = agent_network_hocon + "]\n}\n"
        return agent_network_hocon
