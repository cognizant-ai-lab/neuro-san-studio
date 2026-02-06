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

from copy import deepcopy
from typing import Any

from leaf_common.config.file_of_class import FileOfClass
from leaf_common.persistence.easy.easy_hocon_persistence import EasyHoconPersistence
from neuro_san.internals.graph.filters.dictionary_common_defs_config_filter import DictionaryCommonDefsConfigFilter
from neuro_san.internals.graph.filters.string_common_defs_config_filter import StringCommonDefsConfigFilter

from coded_tools.agent_network_designer.agent_network_assembler import AgentNetworkAssembler


class DeployableAgentNetworkAssembler(AgentNetworkAssembler):
    """
    Implementation of AgentNetworkAssembler that puts the network definition into
    a dictionary format suitable for deployment with a Reservation.
    """

    def __init__(self, demo_mode: bool):
        """
        Constructor
        """
        # Only want to do these things once.
        persistence = EasyHoconPersistence()
        file_of_class = FileOfClass(__file__)

        if demo_mode:
            template_file: str = file_of_class.get_file_in_basis("deployable_template_demo.hocon")
        else:
            template_file: str = file_of_class.get_file_in_basis("deployable_template.hocon")
        self.template: dict[str, Any] = persistence.restore(file_reference=template_file)

        aaosa_file: str = file_of_class.get_file_in_basis("../../registries/aaosa.hocon")
        self.aaosa_defs: dict[str, Any] = persistence.restore(file_reference=aaosa_file)

    def assemble_agent_network(
        self, network_def: dict[str, Any], top_agent_name: str, agent_network_name: str, sample_queries: list[str]
    ) -> dict[str, Any]:
        """
        Assemble the agent network from the definition.

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent
        :param agent_network_name: The file name, without the .hocon extension
        :param sample_queries: List of sample queries for the agent network

        :return: Some representation of the agent network
        """
        # Move top agent to front so it is listed first
        if top_agent_name != next(iter(network_def)):
            top_agent: dict[str, Any] = network_def.pop(top_agent_name)
            network_def = {top_agent_name: top_agent, **network_def}

        # Start out with a copy of the template, but remove the tools and commondefs
        agent_network: dict[str, Any] = deepcopy(self.template)
        agent_network["tools"] = []
        del agent_network["commondefs"]

        # Add metadata if sample queries are provided
        if sample_queries:
            agent_network["metadata"] = {"sample_queries": sample_queries}

        agent_name: str = None
        agent_def: dict[str, Any] = {}
        for agent_name, agent_def in network_def.items():

            # Find bits and pieces from the agent definition in the larger network definition
            tools: list[str] = agent_def.get("tools", None)

            # Set up replacement strings and values for the filter
            # Note that these are only set up for per-agent replacement values.
            string_replacements: dict[str, Any] = {
                "agent_name": agent_name,
                "agent_instructions": agent_def.get("instructions"),
                "agent_network_name": agent_network_name,
            }
            value_replacements: dict[str, Any] = {"tools": tools}

            # Find what node template to use from the tools
            template_index: int = -1
            if agent_name == top_agent_name:
                # Top agent
                template_index = 0
            elif agent_def.get("tools"):
                # Regular agent
                template_index = 1
            elif agent_def.get("instructions"):
                # Leaf agent
                template_index = 2
            else:
                # Toolbox agent
                template_index = 3

            # Filter the appropriate node in the template based on what we gathered above.
            agent_spec_template: dict[str, Any] = deepcopy(self.template["tools"][template_index])
            agent_spec: dict[str, Any] = self.filter_agent(
                agent_spec_template, string_replacements, value_replacements
            )

            # Add agent to tools
            agent_network["tools"].append(agent_spec)

        return agent_network

    def filter_agent(
        self, agent_spec: dict[str, Any], string_replacements_in: dict[str, Any], value_replacements_in: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Common filters

        We need to use the CommonDefs filters from neuro_san in order to insert the common AAOSA
        instructions/call/command in the right places.

        This is because we are not actually creating a hocon file that can benefit from all the
        "include" business that hocons afford. We are simply creating a dictionary and all that
        search/replace that hocon does for us we have to do ourselves.
        """
        # Create a network spec so the ConfigFilters from neuro_san can work on it
        network_spec: dict[str, Any] = {"tools": [agent_spec]}

        # Get commondefs from the template
        empty: dict[str, Any] = {}
        commondefs: dict[str, Any] = self.template.get("commondefs", empty)

        # Set up string replacements and include AAOSA stuff that we have to do
        # ourselves because we are creating a dictionary and not a hocon file.
        string_replacements: dict[str, str] = {
            "aaosa_command": self.aaosa_defs.get("aaosa_command"),
            "aaosa_instructions": self.aaosa_defs.get("aaosa_instructions"),
        }
        string_replacements.update(string_replacements_in)
        string_replacements.update(commondefs.get("replacement_strings", empty))

        # Similarly set up dictionary value replacements
        value_replacements: dict[str, Any] = {
            "aaosa_call": self.aaosa_defs.get("aaosa_call"),
        }
        value_replacements.update(value_replacements_in)
        value_replacements.update(commondefs.get("replacement_values", empty))

        # Apply the filters
        string_filter = StringCommonDefsConfigFilter(string_replacements)
        network_spec = string_filter.filter_config(network_spec)

        dict_filter = DictionaryCommonDefsConfigFilter(value_replacements)
        network_spec = dict_filter.filter_config(network_spec)

        # Retrieve the modified agent spec
        return network_spec["tools"][0]
