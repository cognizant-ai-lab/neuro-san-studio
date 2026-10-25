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

from copy import copy as shallow_copy
from copy import deepcopy
from typing import Any

from leaf_common.config.file_of_class import FileOfClass
from neuro_san.internals.graph.filters.dictionary_common_defs_config_filter import DictionaryCommonDefsConfigFilter
from neuro_san.internals.graph.filters.string_common_defs_config_filter import StringCommonDefsConfigFilter
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler
from middleware.agent_network_designer.persistence.agent_network_metadata_block import AgentNetworkMetadataBlock


class DeployableAgentNetworkAssembler(AgentNetworkAssembler):
    """
    Implementation of AgentNetworkAssembler that puts the network definition into
    a dictionary format suitable for deployment with a Reservation.
    """

    def __init__(self, demo_mode: bool):
        """
        Constructor
        """
        # Initialize file locations; content is restored lazily in assemble_agent_network().
        file_of_class = FileOfClass(__file__)

        self.template_file: str = None
        if demo_mode:
            self.template_file: str = file_of_class.get_file_in_basis("deployable_template_demo.hocon")
        else:
            self.template_file: str = file_of_class.get_file_in_basis("deployable_template_standard.hocon")

        self.aaosa_file: str = file_of_class.get_file_in_basis("../../../registries/aaosa.hocon")

        self.template: dict[str, Any] = None
        self.aaosa_defs: dict[str, Any] = None

    # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments
    async def assemble_agent_network(
        self,
        network_def: dict[str, Any],
        top_agent_name: str,
        agent_network_name: str,
        sample_queries: list[str],
        client_token_mcp_headers: dict[str, list[str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Assemble the agent network from the definition.

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent
        :param agent_network_name: The file name, without the .hocon extension
        :param sample_queries: List of sample queries for the agent network
        :param client_token_mcp_headers: Optional mapping of client-token MCP
                server URL to the header names the conversation supplied for it,
                driving the front man's sly_data_schema (see the base class)
        :param metadata: Metadata block to carry forward (see the base class);
                None builds the block from sample_queries alone

        :return: Some representation of the agent network
        """
        use_network_def: dict[str, Any] = shallow_copy(network_def)

        restorer = AbstractAsyncConfigRestorer("AgentNetworkDesigner template HOCON reader")
        self.template = await restorer.async_restore(file_reference=self.template_file)
        self.aaosa_defs = await restorer.async_restore(file_reference=self.aaosa_file)

        # Move top agent to front so it is listed first
        if top_agent_name != next(iter(use_network_def)):
            top_agent: dict[str, Any] = use_network_def.pop(top_agent_name)
            use_network_def = {top_agent_name: top_agent, **use_network_def}

        # Start out with a copy of the template, but remove the tools and commondefs
        agent_network: dict[str, Any] = deepcopy(self.template)
        agent_network["tools"] = []
        del agent_network["commondefs"]

        # The metadata block is carried forward whole (issue #1398): neuro-san serves
        # config["metadata"] to clients as-is and no validator inspects it, and the reservation
        # storage writers add their own keys (reservation, stored_at) to whatever block is
        # present. A temporary network gets no studio timestamps, so the block is omitted when
        # there is nothing to say, as it always was without queries.
        metadata_block: dict[str, Any] = (
            AgentNetworkMetadataBlock(metadata, f"agent network {agent_network_name}")
            .merge_sample_queries(sample_queries)
            .as_dict()
        )
        if metadata_block:
            agent_network["metadata"] = metadata_block

        # None when the network uses no client-token MCP servers.
        sly_data_schema: dict[str, Any] | None = self.build_mcp_sly_data_schema(
            use_network_def, client_token_mcp_headers
        )

        agent_name: str = None
        agent_def: dict[str, Any] = {}
        for agent_name, agent_def in use_network_def.items():
            # Find bits and pieces from the agent definition in the larger network definition.
            # Note that `or` pattern is used to avoid issues if the field is set to None.
            tools: list[str] = agent_def.get("tools") or []
            agent_instructions: str = (agent_def.get("instructions") or "").strip()
            agent_description: str = (agent_def.get("description") or "").strip()

            # Set up replacement strings and values for the filter
            # Note that these are only set up for per-agent replacement values.
            string_replacements: dict[str, Any] = {
                "agent_name": agent_name,
                "agent_instructions": agent_instructions,
                "agent_network_name": agent_network_name,
            }
            value_replacements: dict[str, Any] = {"tools": tools}

            # Find what node template to use from the normalized values to stay consistent
            # with what will be rendered after stripping.
            template_index: int = -1
            if agent_name == top_agent_name:
                # Top agent
                template_index = 0
            elif tools:
                # Regular agent
                template_index = 1
            elif agent_instructions:
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

            # Set function.description directly from the agent_network_definition,
            # analogous to ${aaosa_call}{ "description": "..." } in HOCON.
            if isinstance(agent_spec.get("function"), dict):
                if agent_name == top_agent_name:
                    agent_spec["function"]["description"] = (
                        agent_description or "An assistant that answers inquiries from the user."
                    )
                    # Injected after filter_agent() on purpose: there is no
                    # template placeholder to delete for the no-MCP case, and
                    # the URL keys never pass through the string filter's
                    # {placeholder} replacement.
                    if sly_data_schema:
                        agent_spec["function"]["sly_data_schema"] = sly_data_schema
                else:
                    agent_spec["function"]["description"] = agent_description

            # Add agent to tools
            agent_network["tools"].append(agent_spec)

        return agent_network

    def filter_agent(
        self, agent_spec: dict[str, Any], string_replacements_in: dict[str, Any], value_replacements_in: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Fill in an agent template with neuro-san's CommonDefs filters.

        The deployed spec is a plain dictionary with no include of aaosa.hocon and no commondefs section
        (assemble_agent_network drops it), so the AAOSA instructions and call, the template's commondefs and the
        agent's own values are all filled in here.

        :param agent_spec: A copy of one of the template's agent templates
        :param string_replacements_in: Placeholder names, without braces, mapped to the strings that replace
                "{name}"
        :param value_replacements_in: Values that replace any string value equal to their key, such as the
                agent's tools list for "tools"
        :return: The filled-in agent spec
        """
        # Get commondefs from the template
        empty: dict[str, Any] = {}
        commondefs: dict[str, Any] = self.template.get("commondefs", empty)

        # Set up string replacements and include AAOSA stuff that we have to do
        # ourselves because we are creating a dictionary and not a hocon file.
        string_replacements: dict[str, str] = {
            "aaosa_instructions": self.aaosa_defs.get("aaosa_instructions"),
        }
        string_replacements.update(string_replacements_in)
        string_replacements.update(commondefs.get("replacement_strings", empty))

        # neuro-san's string filter leaves "{name}" as written when its replacement is empty, so remove those
        # placeholders from the template here, before the agent's own text goes in.
        empty_keys: list[str] = []
        for key, value in string_replacements.items():
            if isinstance(key, str) and isinstance(value, str) and not value:
                empty_keys.append(key)

        # Create a network spec so the ConfigFilters from neuro_san can work on it
        network_spec: dict[str, Any] = {"tools": [self._remove_placeholders(agent_spec, empty_keys)]}

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

    @staticmethod
    def _remove_placeholders(value: Any, keys: list[str]) -> Any:
        """
        Remove the "{key}" placeholders of the given keys from every string value in a template value. Dict keys
        are left as they are.

        :param value: A template value: a string, or a list or dict holding strings at any depth
        :param keys: The keys whose placeholders to remove
        :return: A copy of the value without those placeholders; a value of any other type comes back as it is
        """
        # A string: delete each placeholder, for example "{demo_mode}" becomes "". This is the only case that
        # changes anything; the other cases only walk down to the strings.
        if isinstance(value, str):
            for key in keys:
                value = value.replace("{" + key + "}", "")
            return value

        # A list: handle each item the same way, keeping their order. A new list is built, so the template the
        # caller passed in is left unchanged.
        if isinstance(value, list):
            items: list[Any] = []
            for item in value:
                items.append(DeployableAgentNetworkAssembler._remove_placeholders(item, keys))
            return items

        # A dict, such as an agent template or its "allow" block: handle each value and keep each key as it is,
        # as neuro-san's filter does. A new dict is built here too.
        if isinstance(value, dict):
            entries: dict[Any, Any] = {}
            for name, item in value.items():
                entries[name] = DeployableAgentNetworkAssembler._remove_placeholders(item, keys)
            return entries

        # Anything else, such as a number, a boolean or None, holds no placeholder and is returned as it is.
        return value
