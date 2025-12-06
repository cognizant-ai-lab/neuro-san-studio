# Agent Network HTML Creator

The **Agent Network HTML Creator** generates an HTML visualization of a specified agent network and opens it in the Chrome
browser.

---

## File

[agent_network_html_creator.hocon](../../../registries/tools/agent_network_html_creator.hocon)

---

## Prerequisites

To run this agent, ensure the following:

- **Chrome** browser is installed.

- `neuro-san` **version 0.5.37 or higher** is available.

---

## Architecture Overview

### Frontman Agent: **Agent Network HTML Creator**

- Acts as the main entry point for user interactions.
- Extracts the `agent_name` from user input and delegates the task to the tool `agent_network_html_generator`.

### Tool: `agent_network_html_generator`

- Creates an HTML-based graph representation of the specified agent network.
- If the `agent_name` is not provided or the corresponding file is invalid or missing, the tool will attempt to retrieve
the name from `sly_data`.
- Automatically opens the generated HTML file in the Chrome browser.

---

## Debugging Tips

If you encounter issues, check the following:

- Confirm that `neuro-san` **>= 0.5.37** is installed.

- Ensure **Chrome** browser is installed and accessible.

- Verify that the specified agent network name is valid and not missing.

---
