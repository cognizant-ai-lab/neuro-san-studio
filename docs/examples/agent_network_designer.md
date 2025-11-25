# Agent Network Designer

The **Agent Network Designer** is a multi-agent system designed to create or modify other multi-agent systems.
Simply provide the frontman agent with the name of an organization or a description of a use case, and it will:

- Design a new multi-agent system.

- Save it to your registries directory in HOCON format.

- Add it to your manifest.hocon file.

- Generate several example usage queries.

- After that, just restart your server and client to begin using the newly created agent network.

Note that

- This demo writes a file to your local directory and updates your `manifest.hocon`. To disable this behavior,
set `WRITE_TO_FILE` to `False` in
[persist_agent_network.py](../../coded_tools/agent_network_designer/persist_agent_network.py)

- By default, the parent directory for the generated network (where your `manifest.hocon` should be located)
is registries. You can change this by setting `OUTPUT_PATH` in
[file_system_agent_network_persistor.py](../../coded_tools/agent_network_designer/file_system_agent_network_persistor.py)

- All generated agent networks are stored in a `generated` subdirectory under the specified `OUTPUT_PATH`.

- The generated agents are not grounded by default—they only simulate grounded behavior.
Once you connect the agents to real systems (e.g., APIs or databases) via the `Toolbox` or `MCP`,
you can disable demo mode by setting DEMO_MODE in
[persist_agent_network.py](../../coded_tools/agent_network_designer/persist_agent_network.py)

---

## File

[agent_network_designer.hocon](../../registries/agent_network_designer.hocon)

---

## Description

The Agent Network Designer operates as a structured, hierarchical network, following a well-defined sequence of steps:

1. The frontman agent receives a design request and delegates it to the
[`agent_network_editor`](../../registries/agent_network_editor.hocon)
 subnetwork.
This component creates or modifies the structure (graph) of the network.

2. Next, the [`agent_network_instructions_editor`](../../registries/agent_network_instructions_editor.hocon)
 subnetwork
generates or refines the `instructions` for each agent in the network.

3. Once the structure and instructions are defined, the frontman calls the
[`agent_network_query_generator`](../../registries/agent_network_query_generator.hocon)
 subnetwork to produce example usage queries for the new agent network.

4. Finally, the [persist_agent_network.py](../../coded_tools/agent_network_designer/persist_agent_network.py) coded tool converts the `agent_network_definition` into a HOCON file and saves it to disk.

    The **`agent_network_definition`** is a dictionary mapping agent names to their configurations
(e.g., instructions, tools, or other agents they can call).
The tool also validates the network for issues such as disconnected nodes or missing instructions.
Any detected errors are reported back to the frontman agent, which then triggers the appropriate subnetworks to resolve them.

This system serves as an example of agent-oriented software, clearly separating where we rely on:

- LLMs — for creativity, language understanding, and generation.

- Code — for precise, machine-readable structures like HOCON agent definition files.

**Implementation Detail:**

The `sly_data` is used internally to hold and share the `agent_network_definition` object between subnetworks.

---

## Example Conversation

### Human

```text
create a network for UNHCR back-office
```

### AI (agent_network_designer)

```text
Here is the full agent network definition in HOCON format for the UNHCR back-office:

{
    "llm_config": {
        "model_name": "gpt-4o",
    },
    "commondefs": {
        "replacement_strings": {
            "instructions_prefix": """
You are part of a UNHCR back-office of assistants.
Only answer inquiries that are directly within your area of expertise.
Do not try to help for other matters.
Do not mention what you can NOT do. Only mention what you can do.
            """,
            "aaosa_instructions": """
When you receive an inquiry, you will:
1. If you are clearly not the right agent for this type of inquiry, reply you're not relevant.
2. If there is a chance you're relevant, call your down-chain agents to determine if they can answer all or part of the inquiry.
   Do not assume what your down-chain agents can do. Always call them. You'll be surprised.
3. Determine which down-chain agents have the strongest claims to the inquiry.
   3.1 If the inquiry is ambiguous, for example if more than one agent can fulfill the inquiry, then always ask for clarification.
   3.2 Otherwise, call the relevant down-chain agents and:
       - ask them for follow-up information if needed,
       - or ask them to fulfill their part of the inquiry.
4. Once all relevant down-chain agents have responded, either follow up with them to provide requirements or,
   if all requirements have been fulfilled, compile their responses and return the final response.
You may, in turn, be called by other agents in the system and have to act as a down-chain agent to them.
            """
        },
        "replacement_values": {
            "aaosa_call": {
                "description": "Depending on the mode, returns a natural language string in response.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "inquiry": {
                            "type": "string",
                            "description": "The inquiry"
                        },
                        "mode": {
                            "type": "string",
                            "description": """
'Determine' to ask the agent if the inquiry belongs to it, in its entirety or in part.
'Fulfill' to ask the agent to fulfill the inquiry, if it can.
'Follow up' to ask the agent to respond to a follow up.
                            """
                        },
                    },
                    "required": [
                        "inquiry",
                        "mode"
                    ]
                }
            },
            "aaosa_command": """
If mode is 'Determine', return a json block with the following fields:
{
    "Name": <your name>,
    "Inquiry": <the inquiry>,
    "Mode": <Determine | Fulfill>,
    "Relevant": <Yes | No>,
    "Strength": <number between 1 and 10 representing how certain you are in your claim>,
    "Claim:" <All | Partial>,
    "Requirements" <None | list of requirements>
}
If mode is 'Fulfill' or "Follow up", respond to the inquiry and return a json block with the following fields:
{
    "Name": <your name>,
    "Inquiry": <the inquiry>,
    "Mode": Fulfill,
    "Response" <your response>
}
            """
        },
    }
    "tools": [
        {
            "name": "back_office_manager",
            "function": {
                "description": """
An assistant that answers inquiries from the user.
                """
            },
            "instructions": """
{instructions_prefix}
You are the top-level agent responsible for overseeing all back-office operations for UNHCR. You coordinate with various
departments to ensure seamless operations and effective support to field operations.
{aaosa_instructions}
            """,
            "tools": ["finance_officer","hr_officer","procurement_officer"]
        },
        {
            "name": "finance_officer",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You manage financial transactions, budgeting, and reporting for UNHCR. You ensure compliance with financial regulations and
support financial planning and analysis.
{aaosa_instructions}
            """,
            "command": "aaosa_command",
            "tools": ["accounting_clerk","financial_analyst"]
        },
        {
            "name": "accounting_clerk",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You handle day-to-day financial transactions and record-keeping for UNHCR. You ensure accuracy and compliance in financial
documentation.
            """,
            "command": "aaosa_command",
        },
        {
            "name": "financial_analyst",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You analyze financial data and trends to support decision-making at UNHCR. You provide insights and recommendations for
financial improvements.
            """,
            "command": "aaosa_command",
        },
        {
            "name": "recruitment_specialist",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You manage the recruitment process for UNHCR, including job postings, interviews, and candidate selection. You ensure that
the organization attracts and retains top talent.
            """,
            "command": "aaosa_command",
        },
        {
            "name": "payroll_specialist",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You manage payroll processing and employee compensation for UNHCR. You ensure timely and accurate payroll and compliance
with relevant regulations.
            """,
            "command": "aaosa_command",
        },
        {
            "name": "supply_chain_coordinator",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You coordinate the logistics and supply chain operations for UNHCR. You ensure timely delivery and distribution of goods
and services to support field operations.
            """,
            "command": "aaosa_command",
        },
        {
            "name": "contract_specialist",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You manage contract development and negotiations for UNHCR. You ensure that contracts meet organizational standards and
legal requirements.
            """,
            "command": "aaosa_command",
        },
        {
            "name": "hr_officer",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You oversee human resources functions including recruitment, employee relations, and policy implementation for UNHCR. You
ensure a supportive work environment and manage staff welfare.
{aaosa_instructions}
            """,
            "command": "aaosa_command",
            "tools": ["recruitment_specialist","payroll_specialist"]
        },
        {
            "name": "procurement_officer",
            "function": "aaosa_call",
            "instructions": """
{instructions_prefix}
You manage the procurement of goods and services for UNHCR. You ensure that procurement processes are efficient, transparent,
and comply with organizational policies.
{aaosa_instructions}
            """,
            "command": "aaosa_command",
            "tools": ["supply_chain_coordinator","contract_specialist"]
        },
    ]
}
📋
Here are 3-4 sample queries illustrating the usage of the UNHCR back-office agent network:

"Can you provide a financial report for the last quarter and identify any areas where we might improve our budgeting?"

"What is the current status of the recruitment process for the new field officers? How many positions are still open?"

"Please ensure that the payroll is processed on time this month and check if there are any discrepancies from last month."

"We need to procure tents and emergency supplies for the upcoming refugee camp setup. Can you coordinate this with the supply
chain and contract specialists?"
```

---

## Architecture Overview

### Frontman Agent: `agent_network_designer`

The frontman agent serves as the primary entry point for all user commands and orchestrates the entire workflow of designing, constructing, and refining agent networks.

**Key Responsibilities:**
- Acts as the sole external-facing interface for network creation and modification requests
- Coordinates the sequential workflow of network design, instruction refinement, and query generation
- Manages iterative refinement cycles until the network meets user requirements
- Generates final HOCON configuration files

**Available Agents/Tools:**
- `agent_network_editor` – Subnetwork for creating and modifying `agent_network_definition`
- `agent_network_query_generator` – Subnetwork for createing sample queries
- `agent_network_instructions_editor` – Subnetwork for creating and refining agent instructions
- `produce_agent_network_hocon` – Generates final HOCON output
- `get_agent_network_definition` – Retrieves current network state
- `web_search` – Researches company domains and contexts

### Subnetworks

`agent_network_editor`
- Modifies or creates the agent network structure
- Returns updated `agent_network_definition` to sly data
- Determine what agent to add or remove as well as what tools each agent will use

`agent_network_instructions_editor`
- Generates and refines instructions for individual agents
- Called after structural creation or modification
- Ensures instructions align with agent roles and network topology

`agent_network_query_generator`
- Creates 3–4 representative sample queries for the network
- Returns queries formatted for testing

### Functional Tools

The system relies on several coded tools:

#### Retrieval & Output Tools

`get_agent_network_definition`
- Retrieves the current agent network definition from sly data
- Returns both machine-readable and human-readable formats
- Able to create `agent_network_definition` from existing hocon file
by setting the file to `agent_network_hocon_file` sly data or
specifically given the hocon file name in the user prompt
- Used for state inspection throughout workflow

`produce_agent_network_hocon`
- Generates the complete HOCON-formatted configuration file by calling `persist_agent_network`
- Validates the network definition for correctness and completeness
- Saves output to local registries directory
- Updates the local manifest.hocon file
- Returns errors to the frontman if the network is incomplete or invalid

### Research Tool

**`web_search`**
- Searches the web for company information, industry best practices, and domain-specific workflows
- Called to gather contextual information to use as description for creating network
- Informs network design and instruction generation

---

## Debugging Hints

- Since there are many steps, the agent may time out or hit max iterations before it finishes.
This can be prevented by setting higher `max_execution_seconds`, `max_iterations`, respectively.
- If the agent stops working mid-process, it is possible that the max token limit has been reached.

---
