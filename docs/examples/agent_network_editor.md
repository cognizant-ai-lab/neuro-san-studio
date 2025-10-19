# Agent Network Editor

The **Agent Network Editor** is a multi-agent system for create or modify `agent_network_definition`. It serves as a subnetwork within the [`agent_network_designer`](../../registries/agent_network_designer.hocon), focusing specifically on building and editing the structure (graph) of the agent network. It is responsible for generating and editing the structure of an agent network according to given specifications.
It operates autonomously within its defined scope — responding only to queries related to network structure and relationships between agents.

This network is also highly useful for testing and experimenting with how agent structures are formed.
Because the prompt for this network directly influences how agents and their relationships are generated, it plays a crucial role in shaping the resulting graph.
Refining this prompt can significantly improve the coherence, hierarchy, and balance of the overall agent network.

## Agent Network Definition

The `agent_network_definition` is a dictionary that maps agent names to their corresponding configurations.
Each configuration may include:

- `instructions` – defines the agent’s behavior and purpose.
Any node that contains instructions represents an agent node.

- `tools` – defines the tools or other agents that this agent can call.
These may include:

    - Downstream agents (other agents in the network)

    - Toolbox tools (nodes without `instructions`)

    - External subnetworks or MCP tools, which appear only as entries in the tools list and do not have dedicated nodes.

Nodes without `instructions` are considered toolbox nodes — simple references to tools from the `Toolbox`.
Subnetworks and MCP tools are not represented as nodes; they are referenced directly in the `tools` list.
Subnetworks always start with "/" while MCP tools are represented by the server's URL.

### Example

```json
{
    "bank_manager": {
      "instructions": "<instructions for bank_manager>",
      "tools": [
        "customer_service_representative",
        "loan_officer",
        "financial_advisor",
        "google_search"
      ]
    },
    "customer_service_representative": {
      "instructions": "<instructions for customer_service_representative>",
      "tools": [
        "teller",
        "/banking_ops"
      ]
    },
    "loan_officer": {
      "instructions": "<instructions for loan_officer>",
      "tools": []
    },
    "teller": {
      "instructions": "<instructions for teller>",
      "tools": []
    },
    "financial_advisor": {
      "instructions": "<instructions for financial_advisor>",
      "tools": []
    },
    "google_search": {}
  }
```

---

## File

[agent_network_editor.hocon](../../registries/agent_network_editor.hocon)

---

## How It Works

The frontman, `agent_network_editor`, has multiple coded tools that can be called in different scenarios.

### Initialization and Tool Discovery

At the start of each session, the editor always call the following functions to discover available tools and resources:

- `get_toolbox`
    — returns a dictionary where each key is a tool name and the value contains tool description.
    - The available toolbox can be set with environment variable `AGENT_TOOLBOX_INFO_FILE`. If not provided,
    [toolbox_info.hocon](../../toolbox/toolbox_info.hocon) will be used.

- `get_subnetwork`
    — returns a dictionary of subnetworks, mapping each name to its frontman's description.
    - The available manifest can be set with environment variable `AGENT_MANIFEST_FILE`. If omitted,
    [manifest.hocon](../../registries/manifest.hocon) will be used.

- `get_mcp_tool`
    — returns a dictionary of MCP server URLs and the capabilities of tools provided by each server.
    - The available MCP servers can be set with environment variable `MCP_CLIENTS_INFO_FILE`. If not provided,
    [mcp_info.hocon](../../mcp/mcp_info.hocon) will be used.

These sources define what can be included in the agent network.

When adding tools to an agent, the following priority order is followed:

1. Subnetworks

2. Toolbox tools

3. MCP tools

### Operational Modes

The network supports two main operational modes:

1. Create Mode triggers `create_new_network`. This will reset `agent_network_definition` and create non-connected agent and toolbox nodes

2. Modify Mode uses `get_agent_network` to retrieve the current `agent_network_definition` before making any modifications.

### Agent Operations

- Adding agents — Use `add_agent_to_network` to create one non-connected node.

- Updating agents — Use `update_agent_in_network` to modify connections and add or remove tools from `get_subnetwork` or `get_mcp_tool`.

- Removing agents — Use `remove_agent_from_network`.

### Validation

- Before finalizing the network, call `validate_structure` to ensure the network satisfies all design rules and structural constraints.

## Design Rules

- The network must always form a directed acyclic graph (DAG).

- Exactly one top-level agent must exist after all edits.

- The top-level agent connects only to mid-level agents — not directly to the lowest-level ones.

- At least one branch must have a depth of three or more agents.

- No isolated agents are allowed; all must remain connected.

- Tools are added only when their purpose or description clearly matches the agent’s role or responsibilities.

## Debugging Hints

Designing or modifying an agent network often involves iterative refinement.
If the generated structure is not as expected, or if validation fails, consider the following debugging steps and best practices:

- Refine the prompt

    The quality, organization, and logical flow of the generated graph are highly dependent on the clarity of the prompt.
    Try rewording or expanding the prompt to give more context about roles, hierarchy, or relationships between agents.

- Verify toolbox and subnetwork descriptions

    Ensure that:

    - Each tool in the Toolbox has a clear and accurate description that conveys its purpose and usage.

    - Each subnetwork, the front-man has a detailed and context-rich description.

    These descriptions directly influence how the network assigns tools.

- Check environment variables

    Confirm that all relevant environment variables are correctly set and accessible to the running process.

    Missing or misconfigured environment variables can prevent certain tools or MCP connections from being discovered or properly loaded.

- Incremental testing

    When building complex agent networks, try adding or modifying a few agents at a time.

- Review logs and tool outputs

    Make sure that each tool returns the expected output.

---
