# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import asyncio
import logging
import re
from typing import Any

from leaf_common.persistence.easy.easy_hocon_persistence import EasyHoconPersistence
from neuro_san.interfaces.coded_tool import CodedTool

AGENT_NETWORK_DEFINITION = "agent_network_definition"
AGENT_NETWORK_HOCON_FILE = "agent_network_hocon_file"


class GetAgentNetworkDefinition(CodedTool):
    """
    CodedTool implementation which provides a way to get agent network definition in a user-specified args or sly data.

    Agent network definition is a structured representation of an agent network, expressed as a dictionary.
    Each key is an agent name, and its value is an object containing:
    - an instructions to the agent
    - a list of down-chain agents (agents reporting to it)
    """

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                     "agent_network_definition": an outline of an agent network

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "agent_network_definition": an outline of an agent network

        :return:
            In case of successful execution:
                the agent network definition as a dictionary.
            otherwise:
                a text string of an error message in the format:
                "Error: <error message>"
        """
        logger = logging.getLogger(self.__class__.__name__)

        # Priority order: user_network_def > network_hocon_file > sly_data > user_hocon_sly_data
        network_def = None

        # Check for user-specified definition
        if args.get("agent_network_definition"):
            logger.info(">>>>>>>>>>>>>>>>>>>Using User-Specified Agent Network Definition>>>>>>>>>>>>>>>>>>>")
            network_def = args.get("agent_network_definition")

        # Try to parse from hocon file name that the agent extracts from user input
        elif args.get("agent_network_hocon_file"):
            logger.info(">>>>>>>>>>>>>>>>>>>Reading & Parsing Agent Network HOCON File>>>>>>>>>>>>>>>>>>>")
            network_def = self._hocon_to_definition(args.get("agent_network_hocon_file"))

        # Fall back to sly data
        # First, check to see if there is a generated agent network definition
        elif sly_data.get(AGENT_NETWORK_DEFINITION):
            logger.info(">>>>>>>>>>>>>>>>>>>Getting Agent Network Definition from Sly Data>>>>>>>>>>>>>>>>>>>")
            network_def = sly_data.get(AGENT_NETWORK_DEFINITION)

        # Lastly, check to see if the user provides HOCON file via sly data
        else:
            logger.info(
                ">>>>>>>>>>>>>>>>>>>Reading & Parsing Agent Network HOCON File "
                "from Key 'agent_network_hocon_file' in Sly Data>>>>>>>>>>>>>>>>>>>"
            )
            network_def = self._hocon_to_definition(sly_data.get(AGENT_NETWORK_HOCON_FILE))

        # Store in sly_data and validate
        if network_def:
            sly_data[AGENT_NETWORK_DEFINITION] = network_def
            logger.info("The resulting agent network definition: \n %s", str(network_def))
            logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
            return network_def

        error_msg = "Error: No agent network definition found!"
        logger.warning(error_msg)
        return error_msg

    def _hocon_to_definition(self, network_hocon_file: dict[str, Any]) -> dict[str, Any]:
        """
        Convert hocon file path into agent network definition
        :param network_hocon_file: Agent network hocon file path

        :return: Agent network definition
        """

        # Converting hocon file to dict
        try:
            network_hocon_file = "registries/" + network_hocon_file
            hocon = EasyHoconPersistence(full_ref=network_hocon_file, must_exist=True)
            network_hocon = hocon.restore()
        except FileNotFoundError:
            return None

        # Only extract agents info and only "instructions" and "tools" parts
        agents: list[dict[str, Any]] = network_hocon.get("tools")
        network_def = {}
        for agent in agents:
            agent_name: str = agent.get("name")
            network_def[agent_name] = {}
            instructions: str = agent.get("instructions")
            if instructions:
                # Extract only the unique instructions (remove aaosa instructions, instructions prefix, and demo mode)
                custom_instructions: str = self._extract_custom_instructions(instructions)
                network_def[agent_name]["instructions"] = custom_instructions
            tools: list[str] = agent.get("tools")
            if tools:
                network_def[agent_name]["down_chains"] = tools

        return network_def

    def _extract_custom_instructions(self, instructions: str) -> str:
        """
        Extract the custom part of instructions, excluding aaosa instructions, instructions prefix, and demo mode.
        :param instructions: The full instructions of an agent.

        :return: The part of instructions that is unique to the agent.
        """

        # Pattern for instruction prefix (matches any agent name)
        prefix_pattern = (
            r"You are part of a \w+ of assistants\.\s*Only answer inquiries that are directly within "
            r"your area of expertise\.\s*Do not try to help for other matters\.\s*"
            r"Do not mention what you can NOT do\. Only mention what you can do\."
        )

        # Aaosa and demo mode text (exact match)
        try:
            use_file = "registries/aaosa.hocon"
            hocon = EasyHoconPersistence(full_ref=use_file, must_exist=True)
            config: dict[str, Any] = hocon.restore()
            aaosa_instructions = config.get("aaosa_instructions", "")
        except FileNotFoundError:
            aaosa_instructions = ""
        demo_mode = (
            "You are part of a demo system, so when queried, make up a realistic response as if "
            "you are actually grounded in real data or you are operating a real application API or microservice."
        )

        # Clean and normalize the input
        custom_part: str = instructions.strip()
        custom_part = re.sub(r'\s+', ' ', custom_part)  # Normalize whitespace

        # Remove instruction prefix using regex
        custom_part = re.sub(prefix_pattern, "", custom_part).strip()

        # Remove demo mode text
        custom_part = custom_part.replace(aaosa_instructions.strip(), "").strip()

        # Remove demo mode text
        custom_part = custom_part.replace(demo_mode.strip(), "").strip()

        # Clean up any extra whitespace
        custom_part = " ".join(custom_part.split())

        return custom_part

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
