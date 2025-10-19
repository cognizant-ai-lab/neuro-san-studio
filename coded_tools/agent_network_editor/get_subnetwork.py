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
import os
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.persistence.registry_manifest_restorer import RegistryManifestRestorer
from neuro_san.internals.graph.registry.agent_network import AgentNetwork

DEFAULT_MANIFEST_FILE = os.path.join("registries", "manifest.hocon")


class GetSubnetwork(CodedTool):
    """
    CodedTool implementation which provides a way to get subnetwork names and descriptions from the manifest file
    """

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    None

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
                the names and descriptions as keys and values of a dictionary.
            otherwise:
                a text string of an error message in the format:
                "Error: <error message>"
        """
        logger = logging.getLogger(self.__class__.__name__)
        os.environ["AGENT_MANIFEST_FILE"] = os.getenv("AGENT_MANIFEST_FILE", DEFAULT_MANIFEST_FILE)
        manifest_file: str | list[str] = os.environ["AGENT_MANIFEST_FILE"]
        try:
            logger.info(">>>>>>>>>>>>>>>>>>>Getting Subnetwork Descriptions from Manifest>>>>>>>>>>>>>>>>>>>")
            logger.info("Manifest file: %s", str(manifest_file))
            networks: dict[str, AgentNetwork] = RegistryManifestRestorer().restore()
            logger.info("Successfully loaded agent networks info from %s", str(manifest_file))
        except FileNotFoundError as not_found_err:
            error_msg = f"Error: Failed to load agent networkds info from {manifest_file}. {str(not_found_err)}"
            logger.warning(error_msg)
            return error_msg

        subnetworks_dict: dict[str, str] = {}
        for name, network in networks.items():
            front_man: str = network.find_front_man()
            desc: str = network.get_agent_tool_spec(front_man).get("function", {}).get("description")
            subnetworks_dict["/" + name] = desc

        return subnetworks_dict

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
