# A2A RESEARCH REPORT

The **A2A RESEARCH REPORT** is a simple agentic system that uses coded tool as an A2A client to connect to the crewAI agent
running in an A2A server. The agent functionality is to write a report on a given research topic while the main purpose
of this agent network is to show how one can connect to A2A server using coded tool.

---

## File

[a2a_research_report.hocon](../../registries/a2a_research_report.hocon)

---

## Prerequisites

- This agent is **disabled by default**. To test it:
    - Manually enable it in the `manifest.hocon` file.
    - `pip install a2a-sdk crewai`
    - Run the A2A server:

    ```bash
    python server.py
    ```

    Located at: [`server.py`](../../servers/a2a/server.py)

---

## Architecture Overview

### Frontman Agent: **topic_identifier**

- Acts as the entry point for external queries.
- Extract topic user input and pass it to the tool.
- Integrates tool responses into a final answer.

### Tool: `research_report_crew`

- Act as an A2A client to the crewAI agents in an A2A server.
- Sends the request and receives the response.
- Source: [`a2a_research_report.py`](../../coded_tools/a2a_research_report/a2a_research_report.py)

### A2A Server

- There are 3 files in `servers/a2a`
    - **agent.py**: agent configuration adapted from [https://docs.crewai.com/quickstart](https://docs.crewai.com/quickstart)
    - **agent_executor.py**: run agent and prepare response message
    - **server.py**: connect to client and return response
- Default port: `9999` (can be customized)
- Source: [`server.py`](../../servers/a2a/server.py)

---

## Debugging Hints

Check the following during development or troubleshooting:

- `a2a` is installed on both the client and the server environments
- `crewai` is installed on the server environment
- A2A server is running
- Client is connected to the correct port

## Note

- The A2A protocol is still under development. The client and server code in this example reflect the version as of
May 14, 2025. Please note that the protocol may change in future updates.

---
