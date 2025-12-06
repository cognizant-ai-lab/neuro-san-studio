# MCP BMI STREAMABLE HTTP

The **MCP BMI STREAMABLE HTTP** is a simple agentic system that connects LLM to the MCP server using streamable http as
transport method. The main purpose is to show how one can connect to mcp server in coded tool.

---

## File

[mcp_bmi_sse.hocon](../../../registries/tools/mcp_bmi_streamable_http.hocon)

---

## Prerequisites

- This agent is **disabled by default**. To test it:
    - Manually enable it in the `manifest.hocon` file.
    - Run the MCP server:

      ```bash
      python bmi_server.py
      ```

    Located at: [`bmi_server.py`](../../../servers/mcp/bmi_server.py)

---

## Architecture Overview

### Frontman Agent: **bmi_provider**

- Acts as the entry point for external queries.
- Parses user input and prepares parameters for the tool.
- Integrates tool responses into a final answer.

### Tool: `bmi_calculator`

- Connects to the MCP server using `langchain-mcp-adapters`.
- Sends the request and receives the response.
- Source: [`bmi_calculator.py`](../../../coded_tools/tools/mcp_bmi_streamable_http/bmi_calculator.py)

### MCP Server

- Defines tool metadata:
    - **Name**: From function name
    - **Description**: From docstring
    - **Arguments Schema**: From type hints
- Default port: `8000` (can be customized)
- Source: [`bmi_server.py`](../../../servers/mcp/bmi_server.py)

---

## Debugging Hints

Check the following during development or troubleshooting:

- `langchain-mcp-adapters` is installed with a valid version
- MCP server is running
- Client is connected to the correct port

---
