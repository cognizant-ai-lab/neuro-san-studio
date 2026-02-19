# Agent Network Architect

The **Agent Network Architect** is a modular, multi-agent system that automates the design, visualization, testing, and sharing
of agent networks. It performs the following key actions:

- Invokes the external `agent_network_designer` agent to generate a `.hocon` configuration file.
- Uses the `agent_network_html_generator` toolbox tool to create an HTML visualization of the network.
- Demonstrates the functionality of the generated network by calling the `NsflowSelenium` coded tool.
- Sends an email with the `.hocon` and HTML files attached using the `send_gmail_hocon_html` coded tool.

---

## File

[agent_network_architect.hocon](../../registries/agent_network_architect.hocon)

---

## Prerequisites

To run this agent, ensure the following are installed and configured:

- **neuro-san>=0.5.38**
- **Chrome browser**
- **Gmail support**:

    ```bash
    pip install -U langchain-google-community\[gmail\]
    ```

- Set up Gmail API credentials:
    - Follow the [instructions](https://developers.google.com/workspace/gmail/api/quickstart/python#authorize_credentials_for_a_desktop_application)
    - Download the `credentials.json` file and place it at the root of the repo.
- **Selenium and WebDriver Manager**:

    ```bash
    pip install selenium webdriver-manager
    ```

- Install Chrome browser

**Additional setup for NsflowSelenium:**

- Start the `nsflow` service in a separate terminal.
- Use **non-default** ports for neuro-san HTTP and nsflow. The default ports are 8080 for HTTP and
4173 for nsflow. For example, you can run:

    ```bash
    python -m run --server-http-port 8081 --nsflow-port 4174
    ```

---

## Architecture Overview

### Frontman Agent: **Agent Network Architect**

- Serves as the central orchestrator for user requests.
- Parses the request and routes tasks to supporting tools.
- Automatically calls `agent_network_html_generator` after receiving a response from `agent_network_designer`.
- If requested, sends the generated `.hocon` and `.html` files via email.
- Uses sample queries from the designer to test the agent network when no specific user query is provided.

### Supporting Tools

1. **agent_network_designer**
    - Generates a `.hocon` file based on an agent name or use case.
    - Saves the file to the [registries](../../registries/) and update the [manifest](../../registries/manifest.hocon).
    - Returns the created agent network and sample queries for testing.

2. **agent_network_html_generator**
   - A toolbox tool that runs automatically after the designer completes.
   - Generates and saves an HTML visualization of the agent network.
   - Opens the HTML file in Chrome.

3. **agent_network_tester**
   - Calls the `NsflowSelenium` coded tool to launch the agent network in a Chrome instance.
   - Uses Selenium to submit a query and capture the agent's response.
   - Automatically closes the browser after interaction.
   - Wait times for each step (element detection, input submission, browser close) are configurable in the `.hocon` file.
   - Returns the query and response to the frontman.

4. **email_sender**
   - Uses the coded tool `send_gmail_hocon_html` to send an HTML email with the `.hocon` and `.html` files attached.

> **Note:**
    For tools that require an agent_name, if the corresponding .hocon file does not exist, the system will attempt to fall
    back to the agent_name provided in sly_data.
    Similarly, if attachment paths (e.g. .hocon, .html files) are not explicitly provided or the files do not exist, the
    system will try to construct them based on the agent_name from sly_data.

---

## Debugging Tips

If something isn't working as expected, check the following:

- Ensure all prerequisites are installed and properly configured.
- Confirm that the `Agent Network Architect` correctly extracts the agent name from the `agent_network_designer` response.
- Adjust timeouts in the `.hocon` for `agent_network_tester` as needed.
- Review logs to ensure correct tool invocation and seamless data flow between components.

---
