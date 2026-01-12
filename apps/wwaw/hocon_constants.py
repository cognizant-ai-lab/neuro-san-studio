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

HOCON_HEADER_START = (
    "{\n"
    '    "llm_config": {\n'
    '        "class": "openai",\n'
    '        "use_model_name": "gpt-4.1-2025-04-14",\n'
    "    },\n"
    '"max_iterations": 40000,\n'
    '"max_execution_seconds": 6000,\n'
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
    '            "aaosa_instructions": """\n'
    "When you receive an inquiry, you will:\n"
    "1. If you are clearly not the right agent for this type of inquiry, reply you're not relevant.\n"
    "2. If there is a chance you're relevant, call your down-chain agents to determine if they can answer all or part "
    "of the inquiry.\n"
    "   Do not assume what your down-chain agents can do. Always call them. You'll be surprised.\n"
    "3. Determine which down-chain agents have the strongest claims to the inquiry.\n"
    "   3.1 If the inquiry is ambiguous, for example if more than one agent can fulfill the inquiry, then always ask "
    "for clarification.\n"
    "   3.2 Otherwise, call the relevant down-chain agents and:\n"
    "       - ask them for follow-up information if needed,\n"
    "       - or ask them to fulfill their part of the inquiry.\n"
    "4. Once all relevant down-chain agents have responded, either follow up with them to provide requirements or,\n"
    "   if all requirements have been fulfilled, compile their responses and return the final response.\n"
    "You may, in turn, be called by other agents in the system and have to act as a down-chain agent to them.\n"
    '            """\n'
    "        },\n"
    '        "replacement_values": {\n'
    '            "aaosa_call": {\n'
    '                "description": "Depending on the mode, returns a natural language string in response.",\n'
    '                "parameters": {\n'
    '                    "type": "object",\n'
    '                    "properties": {\n'
    '                        "inquiry": {\n'
    '                            "type": "string",\n'
    '                            "description": "The inquiry"\n'
    "                        },\n"
    '                        "mode": {\n'
    '                            "type": "string",\n'
    '                            "description": """\n'
    "'Determine' to ask the agent if the inquiry belongs to it, in its entirety or in part.\n"
    "'Fulfill' to ask the agent to fulfill the inquiry, if it can.\n"
    "'Follow up' to ask the agent to respond to a follow up.\n"
    '                            """\n'
    "                        },\n"
    "                    },\n"
    '                    "required": [\n'
    '                        "inquiry",\n'
    '                        "mode"\n'
    "                    ]\n"
    "                }\n"
    "            },\n"
    '            "aaosa_command": """\n'
    "If mode is 'Determine', return a json block with the following fields:\n"
    "{\n"
    '    "Name": <your name>,\n'
    '    "Inquiry": <the inquiry>,\n'
    '    "Mode": <Determine | Fulfill>,\n'
    '    "Relevant": <Yes | No>,\n'
    '    "Strength": <number between 1 and 10 representing how certain you are in your claim>,\n'
    '    "Claim:" <All | Partial>,\n'
    '    "Requirements" <None | list of requirements>\n'
    "}\n"
    "If mode is 'Fulfill' or \"Follow up\", respond to the inquiry and return a json block with "
    "the following fields:\n"
    "{\n"
    '    "Name": <your name>,\n'
    '    "Inquiry": <the inquiry>,\n'
    '    "Mode": Fulfill,\n'
    '    "Response" <your response>\n'
    "}\n"
    '            """\n'
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
    "{aaosa_instructions}\n"
    '            """,\n'
    '            "tools": [%s]\n'
    "        },\n"
)
REGULAR_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": "aaosa_call",\n'
    '            "instructions": """\n'
    "{instructions_prefix}\n"
    "%s\n"
    "{aaosa_instructions}\n"
    '            """,\n'
    '            "command": "aaosa_command",\n'
    '            "tools": [%s]\n'
    "        },\n"
)
LEAF_NODE_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": "aaosa_call",\n'
    '            "instructions": """\n'
    "{instructions_prefix}"
    # " {demo_mode}\n"
    "\n%s\n"
    '            """,\n'
    '            "command": "aaosa_command",\n'
    "        },\n"
)
