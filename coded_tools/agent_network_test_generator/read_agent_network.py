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

import asyncio
import logging
from typing import Any
from typing import Union

from leaf_common.persistence.easy.easy_hocon_persistence import EasyHoconPersistence
from neuro_san.interfaces.coded_tool import CodedTool


class ReadAgentNetwork(CodedTool):
    """
    CodedTool implementation that reads a target agent network HOCON file
    and returns a structured summary of its agents, instructions, metadata,
    sample queries, and sly_data schemas suitable for generating test cases.
    """

    @staticmethod
    def _extract_agent_info(tool: dict[str, Any]) -> dict[str, Any]:
        """
        Extract relevant information from a single tool/agent definition.

        :param tool: A single tool definition dictionary from the network HOCON.
        :return: A dictionary summarising the agent's key attributes.
        """
        agent_info: dict[str, Any] = {
            "name": tool.get("name", ""),
        }
        if tool.get("instructions"):
            agent_info["instructions"] = tool["instructions"]

        function_def: dict[str, Any] = tool.get("function", {})
        if function_def.get("description"):
            agent_info["description"] = function_def["description"]
        if function_def.get("parameters"):
            agent_info["parameters"] = function_def["parameters"]
        if function_def.get("sly_data_schema"):
            agent_info["sly_data_schema"] = function_def["sly_data_schema"]

        if tool.get("tools"):
            agent_info["tools"] = tool["tools"]
        if tool.get("class"):
            agent_info["class"] = tool["class"]
        if tool.get("toolbox"):
            agent_info["toolbox"] = tool["toolbox"]

        return agent_info

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Reads the specified agent network HOCON file and extracts relevant
        information for test case generation.

        :param args: A dictionary with the following keys:
                "agent_network_hocon_file": the path to the agent network HOCON file
                    relative to the registries directory (e.g., "basic/coffee_finder_advanced.hocon").

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                A dictionary containing the full agent network summary.
            otherwise:
                A text string error message.
        """
        logger = logging.getLogger(self.__class__.__name__)

        hocon_file: str = args.get("agent_network_hocon_file", "")
        if not hocon_file:
            return "Error: No 'agent_network_hocon_file' provided."

        # Ensure the path includes the registries prefix
        if not hocon_file.startswith("registries/"):
            hocon_file = "registries/" + hocon_file

        logger.info(">>>>>>>>>>>>>>>>>>>Reading Agent Network HOCON>>>>>>>>>>>>>>>>>>")
        logger.info("HOCON file: %s", hocon_file)

        try:
            hocon = EasyHoconPersistence(full_ref=hocon_file, must_exist=True)
            network_hocon: dict[str, Any] = hocon.restore()
        except (FileNotFoundError, TypeError) as exc:
            error_msg = f"Error: Could not read HOCON file '{hocon_file}': {exc}"
            logger.error(error_msg)
            return error_msg

        # Extract the agent name (stem of the hocon file path without .hocon extension)
        agent_name: str = hocon_file.replace("registries/", "").replace(".hocon", "")

        agents_summary: list[dict[str, Any]] = [
            self._extract_agent_info(tool) for tool in network_hocon.get("tools", [])
        ]

        result: dict[str, Any] = {
            "agent_name": agent_name,
            "metadata": network_hocon.get("metadata", {}),
            "agents": agents_summary,
        }

        # Store in sly_data for downstream tools
        sly_data["target_agent_name"] = agent_name
        sly_data["target_network_summary"] = result

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        logger.info("Extracted %d agents from network '%s'", len(agents_summary), agent_name)
        return result

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
