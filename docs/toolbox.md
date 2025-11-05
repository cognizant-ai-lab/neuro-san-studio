# Toolbox

The **Toolbox** provides a centralized catalog of pre-configured tools
that agents can use within the Neuro SAN Studio framework.
It simplifies tool integration by offering ready-to-use implementations for common tasks
like web search, document retrieval, email management, and code execution.

## Using Toolbox Tools

To use a tool from the toolbox in your agent network configuration, reference it by name in the `toolbox` field:

```hocon
{
    "name": "your_agent_name"
    "toolbox": "tool_name_from_toolbox"
}
```

## Available Tools

### Agent Management

Tools for orchestrating multi-agent workflows and visualizing agent networks.

* **`call_agent`** — Invoke another agent to handle a specific inquiry
* **`agent_network_html_generator`** — Generate an interactive HTML visualization of an agent network

### Code Execution

Execute Python code dynamically for data analysis, plotting, and computation.

* **`anthropic_code_execution`** — Execute code using Anthropic's code execution tool
* **`openai_code_interpreter`** — Execute code using OpenAI's code interpreter

### Date and Time

Provide current date and time for a specified timezone (default to UTC). This tool is in NeuroSAN's default toolbox.

* **`get_current_date_time`** - Support both UTC offset and IANA timezone

### Email Management

Send and manage emails through Gmail integration.

* **`gmail_toolkit`** — Access Gmail functionality (read, search, compose)
* **`send_gmail_message_with_attachment`** — Send emails with file attachments

### HTTP Requests

Make HTTP requests to external APIs and web services. These tools are from NeuroSAN's default toolbox.

* **`requests_get`** — Perform HTTP GET requests
* **`requests_post`** — Perform HTTP POST requests
* **`requests_patch`** — Perform HTTP PATCH requests
* **`requests_put`** — Perform HTTP PUT requests
* **`requests_delete`** — Perform HTTP DELETE requests
* **`requests_toolkit`** — Bundle of all HTTP request tools (GET, POST, PATCH, PUT, DELETE)

### Project Management

Integrate with Atlassian products for issue tracking and documentation.

* **`jira_toolkit`** — Interact with Jira (search issues, create tickets, manage projects)

### Retrieval-Augmented Generation (RAG)

Retrieve and query information from various document sources.

* **`arxiv_rag`** — Search and retrieve information from arXiv research papers
* **`confluence_rag`** — Query Confluence documentation and wiki pages
* **`docling_rag`** — Extract and search content from multiple document formats
* **`pdf_rag`** — Query PDF documents
* **`webpage_rag`** - Query webpages
* **`wikipedia_rag`** — Retrieve information from Wikipedia articles

### Web Search

Perform real-time web searches using various search engines and APIs.

* **`anthropic_search`** — Web search via Anthropic's search tool
* **`brave_search`** — Search using Brave Search API
* **`ddgs_search`** — Search using DuckDuckGo (no API key required)
* **`google_search`** — Search using Google Custom Search Engine
* **`google_serper`** — Search using Google Serper API with advanced filtering
* **`openai_search`** — Web search via OpenAI's search tool
* **`tavily_search`** — AI-optimized search using Tavily API

## Configuration and Setup

Each tool may require specific API keys, environment variables, or dependencies.
Refer to the detailed configuration instructions in the [Toolbox HOCON file](../toolbox/toolbox_info.hocon)
for setup requirements.

## Learn More

* **[User Guide: Toolbox Section](user_guide.md#toolbox)** — Comprehensive guide on configuring and customizing tools
* **[Toolbox Configuration Reference](../toolbox/toolbox_info.hocon)** — Complete tool definitions and parameters
<!-- pyml disable-next-line line-length -->
* **[Default Toolbox](https://github.com/cognizant-ai-lab/neuro-san/blob/main/neuro_san/internals/run_context/langchain/toolbox/toolbox_info.hocon)** — NeuroSAN's default toolbox
