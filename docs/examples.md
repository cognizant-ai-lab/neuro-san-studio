# Examples

Here are a few examples ordered by level of complexity.

<!-- TOC -->

* [Examples](#examples)
  * [🔰 Basic Examples](#-basic-examples)
    * [Music Nerd](#music-nerd)
    * [Music Nerd Pro](#music-nerd-pro)
    * [Music Nerd Local](#music-nerd-local)
    * [Music Nerd Pro Local](#music-nerd-pro-local)
    * [Music Nerd Pro Sly](#music-nerd-pro-sly)
    * [Music Nerd Pro Sly Local](#music-nerd-pro-sly-local)
    * [Music Nerd LLM Fallbacks](#music-nerd-llm-fallbacks)
    * [Coffee Finder](#coffee-finder)
    * [Coffee Finder Advanced](#coffee-finder-advanced)
  * [🧰 Tool Integration Examples](#-tool-integration-examples)
    * [Anthropic Code Execution](#anthropic-code-execution)
    * [Anthropic Web Search](#anthropic-web-search)
    * [OpenAI Code Interpreter](#openai-code-interpreter)
    * [OpenAI Web Search](#openai-web-search)
    * [Gmail Assistant](#gmail-assistant)
    * [Agent Network HTML Creator](#agent-network-html-creator)
    * [Agentforce](#agentforce)
    * [Agentspace](#agentspace)
    * [MCP BMI STREAMABLE HTTP](#mcp-bmi-streamable-http)
    * [A2A RESEARCH REPORT](#a2a-research-report)
    * [PDF RAG Assistant](#pdf-rag-assistant)
    * [Confluence RAG Assistant](#confluence-rag-assistant)
    * [Agentic RAG Assistant](#agentic-rag-assistant)
    * [Wikipedia RAG Assistant](#wikipedia-rag-assistant)
    * [ArXiv RAG Assistant](#arxiv-rag-assistant)
    * [ServiceNow AI Agents](#servicenow-ai-agents)
  * [🏢 Industry-Specific Examples](#-industry-specific-examples)
    * [Intranet Agents](#intranet-agents)
    * [Intranet Agents With Tools](#intranet-agents-with-tools)
    * [Airline Policy 360 Assistant](#airline-policy-360-assistant)
    * [Real Estate Agent](#real-estate-agent)
    * [Consumer Decision Assistant Agents](#consumer-decision-assistant-agents)
    * [Therapy Vignette Supervision](#therapy-vignette-supervision)
    * [Banking Operations](#banking-operations)
    * [Retail Operations and Customer Service Assistant](#retail-operations-and-customer-service-assistant)
    * [Insurance Underwriting Agents](#insurance-underwriting-agents)
    * [Sentiment Analysis of News Sources](#sentiment-analysis-of-news-sources)
  * [🧪 Experimental and Research](#-experimental-and-research)
    * [Agent Network Designer](#agent-network-designer)
    * [Agent Network Architect](#agent-network-architect)
    * [KWIK Agents](#kwik-agents)
    * [CRUSE](#cruse)
    * [Conscious Assistant](#conscious-assistant)
    * [Log Analyzer](#log-analyzer)
    * [WWAW](#wwaw)

<!-- TOC -->

## 🔰 Basic Examples

Introductory examples designed to help users get started with Neuro SAN.

### Music Nerd

[Music Nerd](./examples/music_nerd.md) is a basic agent network with a single agent,
used as a "Hello world!" example. It can also be used to test for follow-up questions and deterministic answers.

### Music Nerd Pro

[Music Nerd Pro](./examples/music_nerd_pro.md) is a simple agent network with a frontman agent and a "Coded Tool."
This is a good way to learn about how to call Python code from an agent.

**Tags:** `tool`

### Music Nerd Local

[Music Nerd Local](./examples/music_nerd_local.md) is an exact copy of
[Music Nerd](./examples/music_nerd.md) that uses an LLM that runs locally with Ollama.

**Tags:** `llm_config`

### Music Nerd Pro Local

[Music Nerd Pro Local](./examples/music_nerd_pro_local.md) is an exact copy
of [Music Nerd Pro](./examples/music_nerd_pro.md) that uses a **tool-calling** LLM that runs locally with Ollama.

**Tags:** `tool`, `llm_config`

### Music Nerd Pro Sly

[Music Nerd Pro Sly](./examples/music_nerd_pro_sly.md) is a copy of
[Music Nerd Pro](./examples/music_nerd_pro.md) that uses `sly_data` to keep track of a variable.
This is a good way to learn about how to manage a state in a conversation.

**Tags:** `tool`, `sly_data`

### Music Nerd Pro Sly Local

[Music Nerd Pro Sly Local](./examples/music_nerd_pro_sly_local.md) is a copy of
[Music Nerd Pro Sly](./examples/music_nerd_pro_sly.md) that uses
a **tool-calling** LLM that runs locally with Ollama.

**Tags:** `tool`, `sly_data`, `llm_config`

### Music Nerd LLM Fallbacks

[Music Nerd LLM Fallbacks](./examples/music_nerd_llm_fallbacks.md) is a copy of
[Music Nerd Pro](./examples/music_nerd_pro.md) that uses a `fallbacks` list in
its `llm_config` to automatically try another LLM config if the first one fails.

**Tags:** `llm_config` `llm_fallbacks`

### Coffee Finder

[Coffee Finder](./examples/coffee_finder.md) is an agent network that helps
users find coffee at any time of the day. It shows how multiple agents can
provide the same service and how the AAOSA instructions can be used to choose
the best option depending on the context.

**Tags:** `AAOSA`

### Coffee Finder Advanced

[Coffee Finder Advanced](./examples/coffee_finder_advanced.md) is an agent network that helps
users find places that sell coffee and place orders.
This is a good example to:
* Learn how to use the `AAOSA` instructions to find and choose between options.
* Learn how agents can ask for clarification and follow up with questions.
* Learn how to use tools to call Python code.
* Learn how agents can ask for additional information.

**Tags:** `AAOSA` `tool` `time` `sly_data` `memory`

## 🧰 Tool Integration Examples

Examples that demonstrate how to integrate external tools and services.

### Anthropic Code Execution

[Code Execution Assistant](./examples/anthropic_code_execution.md) is a task-oriented agentic system designed to help
users execute code and perform computational tasks efficiently. It leverages Anthropic's built-in code execution tool
through a specialized toolkit, providing users with the ability to run Python code, generate visualizations,
perform data analysis, and create files through natural language commands.

**Tags:** `tool`, `Anthropic`

### Anthropic Web Search

[Anthropic Web Search](./examples/anthropic_web_search.md) is a task-oriented agentic system designed to help users
search and retrieve information from the web efficiently. It leverages Anthropic's built-in web search tool through
a specialized toolkit, providing users with accurate, up-to-date information from across the internet through
natural language queries.

**Tags:** `tool`, `Anthropic`

### OpenAI Code Interpreter

[OpenAI Code Interpreter](./examples/openai_code_interpreter.md) is a task-oriented agentic system designed to help
users execute code and perform computational tasks efficiently. It leverages OpenAI's built-in code interpreter tool
through a specialized toolkit, providing users with the ability to run Python code, generate visualizations,
perform data analysis, and create computational solutions through natural language commands.

**Tags:** `tool`, `OpenAI`

### OpenAI Web Search

[OpenAI Web Search](./examples/openai_web_search.md) is a task-oriented agentic system designed to help users search
and retrieve information from the web efficiently. It leverages OpenAI's built-in web search tool through a specialized
toolkit, providing users with accurate, up-to-date information from across the internet through
natural language queries.

**Tags:** `tool`, `OpenAI`

### Gmail Assistant

[Gmail Assistant](./examples/gmail.md) is a conversational agent that helps users manage their Gmail inbox using natural
language. It can search, read, draft, and send emails by delegating tasks to specialized tools in the Gmail Toolkit.

**Tags:** `tool`, `Gmail`, `API`

### Agent Network HTML Creator

[Agent Network HTML Creator](./examples/agent_network_html_creator.md) visualizes the structure of a specified multi-agent
system by generating an interactive HTML graph and opening it in Chrome. It helps users quickly understand the relationships
and roles of agents within the network.

**Tags:** `tool`, `HTML`

### Agentforce

[Agentforce](./examples/agentforce.md) is an agent network that delegates to a Salesforce Agentforce agent
to interact with a CRM system.

**Tags:** `tool`, `API`

### Agentspace

[Agentspace](./examples/agentspace_adapter.md) is an agent network that delegates to a Google Agentspace agent to
interact with different datastore connectors on Google Cloud.

**Tags:** `tool`, `API`

### MCP BMI STREAMABLE HTTP

[MCP BMI STREAMABLE HTTP](./examples/mcp_bmi_streamable_http.md) is an agent that calls a tool in MCP server via
streamable http to calculate BMI. It serves as an example of how to connect to MCP servers in coded tools.

**Tags:** `tool`, `MCP`

### A2A RESEARCH REPORT

[A2A RESEARCH REPORT](./examples/a2a_research_report.md) is an agent that uses a coded tool as an A2A client to connect
to crewAI agents in an A2A server to write a report on a provided topic. This is an example of how to link
neuro-san with other agentic frameworks.

**Tags:** `tool`, `A2A`, `CrewAI`

### PDF RAG Assistant

[PDF RAG Assistant](./examples/pdf_rag.md) is an agent-based system that answers user queries by retrieving information
from specified PDF files using Retrieval-Augmented Generation (RAG). It processes input through a frontman agent and a
PDF retrieval tool, enabling accurate responses from static documents.

**Tags:** `tool`, `RAG`

### Confluence RAG Assistant

[Confluence RAG Assistant](./examples/confluence_rag.md) answers user queries using RAG over Confluence pages by loading
page content (and optional attachments), building a vector store, and retrieving relevant info to respond.

**Tags** `tool`, `RAG`

### Agentic RAG Assistant

[Agentic RAG Assistant](./examples/agentic_rag.md) is a modular multi-agent system that answers user queries by
retrieving information from the web, PDF documents, and Slack channels. It mimics a smart assistant that delegates tasks
to specialized tools and compiles responses into clear, helpful answers.

**Tags:** `tool`, `API`, `RAG`

### Wikipedia RAG Assistant

[Wikipedia RAG Assistant](./examples/wikipedia_rag.md) answers user queries by searching Wikipedia, fetching the most
relevant articles, and synthesizing their content into accurate, detailed answers (no vector store required).

**Tags:** `tool`, `RAG`

### ArXiv RAG Assistant

[ArXiv RAG Assistant](./examples/arxiv_rag.md) is an agent-based system that queries arXiv, pulls the best-matching
research papers (abstracts or full text) and produces accurate responses to user queries (no vector store needed).

**Tags:** `tool`, `RAG`

### ServiceNow AI Agents

[ServiceNow AI Agents](./examples/now_agents.md) is a comprehensive integration system that enables natural language
interaction with ServiceNow's Agentic AI platform. It provides discovery, communication, and response retrieval
capabilities for 100+ specialized AI agents within ServiceNow instances for IT service management, HR operations,
procurement, and other enterprise processes.

**Tags:** `tool`, `API`, `ServiceNow`, `Enterprise`

## 🏢 Industry-Specific Examples

Examples tailored to specific industry applications.

### Intranet Agents

[Intranet Agents](examples/intranet_agents.md) is a multi-agent system that mimics the intranet of a major corporation.
It allows you to interact and get information from various departments such as IT, Finance, Legal, HR, etc.

**Tags:** `AAOSA`

### Intranet Agents With Tools

[Intranet Agents With Tools](examples/intranet_agents_with_tools.md) is a multi-agent system that mimics the intranet of
a major corporation. It allows you to interact and get information from various departments such as IT, Finance, Legal,
HR, etc. Some of the down-chain agents call coded tools.

**Tags:** `tool`, `API`, `AAOSA`

### Airline Policy 360 Assistant

[Airline Policy 360 Assistant](./examples/airline_policy.md) is a sophisticated multi-agent system designed to manage
and respond to customer inquiries by referring to related airline policies with structured delegation. It mimics a
real-world helpdesk with specialized teams, each handling a specific domain of airline policies such as baggage,
flights, international travel, and more.

**Tags:** `tool`, `API`, `AAOSA`

### Real Estate Agent

[Real Estate Agent](examples/real_estate.md) is a multi-agent system that provides help with real estate transaction
inquiries. The top-level "front-man" agent receives a question, and in coordination with down-chain agents, provides an
answer. Some of the down-chain agents call coded tools.

**Tags:** `tool`, `AAOSA`, `external_network`

### Consumer Decision Assistant Agents

[Consumer Decision Assistant](examples/consumer_decision_assistant.md) is a multi-agent system that calls other (B2C)
multi-agent systems that are not necessarily aligned.

**Tags:** `tool`, `AAOSA`,  `external_network`

### Therapy Vignette Supervision

[Therapy Vignette Supervision](examples/therapy_vignette_supervision.md) is an agentic therapy supervision group. Give
it a therapy vignette, and it will produce a consensus treatment plan after the various therapy experts offer their
opinion.

**Tags:** `AAOSA`

### Banking Operations

[Banking Operations](examples/banking_ops.md) is a multi-agent system that simulates an end-to-end banking support
framework covering account servicing, fraud prevention, credit underwriting, and wealth management. Specialized agents
collaborate to deliver bank policy-compliant responses to users, with the system currently operating in demo mode.

**Tags:** `AAOSA`

### Retail Operations and Customer Service Assistant

[Retail Operations and Customer Service Assistant](examples/retail_ops_and_customer_service.md) is a modular,
multi-agent system that simulates a real-world helpdesk, automating the management of orders, returns, refunds, and
product queries while ensuring compliance with company policies. It uses domain-specific task delegation across
specialized agents, each handling a particular query or retail operation, and is currently in demo mode.

**Tags:** `AAOSA`

### Insurance Underwriting Agents

[Insurance Underwriting Agent](examples/insurance_underwriting_agents.md) is a hierarchical, multi-agent system that
automates Hartford’s business insurance workflows, replicating a real-world operations desk. It seamlessly coordinates
information flow across multiple agents (teams), managing underwriting and claims processes. Key tasks include ACORD form
validation, risk assessment, underwriting decisions, and claims intake. The system is currently in demo mode.

**Tags:** `AAOSA`

### Sentiment Analysis of News Sources

[Sentiment Analysis of News Sources](examples/news_sentiment_analysis.md) is a multi-agent system that analyzes
news coverage from The New York Times, The Guardian, and Al Jazeera to reveal emotional framing across geopolitical
perspectives. Using keyword-driven sentiment analysis, it automates news retrieval, sentiment scoring, and report
generation to provide concise, data-backed insights on sentiment polarity, tone variations, and media bias.

**Tags:** `tool`, `API`, `AAOSA`

## 🧪 Experimental and Research

Cutting-edge examples for research and experimentation.

### Agent Network Designer

[Agent Network Designer](examples/agent_network_designer.md) is a multi-agent system to create multi-agent systems.
Enter the name of an organization or describe the use-case and will create an agent network hocon for you and save it to
your registries directory and give you some usage examples.

**Tags:** `tool`

### Agent Network Architect

[Agent Network Architect](examples/agent_network_architect.md) is an automated, multi-agent system that designs, visualizes,
tests, and shares agent networks. It begins by generating a .hocon configuration file using an external designer agent, then
creates an interactive HTML graph of the network, runs a live demonstration using Selenium with Nsflow, and optionally emails
the results. This network streamlines the end-to-end workflow for building and showcasing agent systems.

**Tags:** `tool`, `external_network`, `HTML`, `nsflow`, `Gmail`

### KWIK Agents

[KWIK_agents](examples/kwik_agents.md) is a basic multi-agent system with memory.

**Tags:** `tool`, `memory`

### CRUSE

[CRUSE](examples/cruse.md) is an agent that can dynamically attach to any agent in your registry and make it run with a
context reactive user experience. This is a good example of how to switch down-chain agents dynamically using coded
tools and sly_data.

**Tags:** `tool`, `ui`, `app`

### Conscious Assistant

[Conscious Agent](examples/conscious_agent.md) is a multi-agent system used within the conscious assistant and
serves as a good example of how to run an agent permanently.

**Tags:** `tool`, `memory`, `app`

### Log Analyzer

[Log Analyzer](examples/log_analyzer.md) is a multi-agent system used within the log analyzer app and serves as a
good example of how to run an agent network on an agent network log for various validations.

**Tags:** `AAOSA`, `app`

### WWAW

[wwaw.md](examples/wwaw.md) stands for worldwide agentic web, and is an app to generate an arbitrarily sized agent
network using the web as the template for the agent connections and content.
**Tags:** `scale`, `app`
