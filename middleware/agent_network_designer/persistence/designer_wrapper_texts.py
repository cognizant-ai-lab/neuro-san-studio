# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
"""
The fixed texts the agent network designer wraps around every agent's own instructions when it saves a network.
"""


class DesignerWrapperTexts:  # pylint: disable=too-few-public-methods
    """
    The wording of the wrapper the designer adds around each agent's own instructions on save.

    An agent's "instructions" in agent_network_definition is only the agent's own text. Every save adds the
    wrapper back, and which pieces an agent gets depends on its role:

    - the prefix, for every LLM agent;
    - the front man's three fixed lines, for the top agent;
    - the demo sentence, for leaf agents when demo mode is on;
    - the AAOSA instructions, for the top agent and agents with tools. Their text lives in
      registries/aaosa.hocon, the file every generated network includes, so it is not repeated here.

    HoconAgentNetworkAssembler builds its header and top-agent template from these constants, and
    DesignerInstructionUnwrapper strips them again from a definition whose instructions already hold them, so the
    two cannot drift apart. deployable_template.hocon and deployable_template_demo.hocon are HOCON and cannot import
    them; a test pins their copies to these values.

    Data only: the rules for stripping the texts belong to DesignerInstructionUnwrapper.
    """

    # The words the prefix opens with. The network name and a period follow them, then PREFIX_RULES, so the file
    # for a network called coffee_shop starts every agent with
    # "You are part of a team of assistants in coffee_shop." and the rules.
    PREFIX_OPENING: str = "You are part of a team of assistants in"

    # The three lines after the prefix's opening sentence.
    PREFIX_RULES: str = (
        "Only answer inquiries that are directly within your area of expertise.\n"
        "Do not try to help for other matters.\n"
        "Do not mention what you can NOT do. Only mention what you can do."
    )

    # Networks generated before 22a84541 (2025-10-09) opened the prefix with
    # "You are part of a <network name> of assistants." instead, followed by the same PREFIX_RULES. The designer no
    # longer writes it, but copies of it can still sit inside the instructions of such networks.
    LEGACY_PREFIX_OPENING: str = "You are part of a"
    LEGACY_PREFIX_CLOSING: str = "of assistants."

    # The lines the top-agent template writes inside the front man's own triple-quoted body, ahead of its text.
    FRONT_MAN_LINES: str = (
        "Never express irrelevance unless you have first consulted all your tools.\n"
        "Once you have determined the relevant tools, do not express that to the user, rather,\n"
        "call all the relevant tools and make sure the command is fully serviced and express the end result."
    )

    # The value of the "demo_mode" key a generated network defines when demo mode is on, which the leaf template
    # puts between the prefix and the leaf's own text. It holds no double quote or backslash, so the header can
    # write it as a double-quoted HOCON string as is.
    DEMO_SENTENCE: str = (
        "You are part of a demo system, so when queried, make up a realistic response as if you are actually "
        "grounded in real data or you are operating a real application API or microservice."
    )
