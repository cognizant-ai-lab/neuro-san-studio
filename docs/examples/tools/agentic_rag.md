# Agentic RAG Assistant

The **Agentic RAG Assistant** is a modular, multi-agent system designed to answer user queries by intelligently retrieving,
searching, and integrating content from websites, document-based knowledge, and Slack channels. It orchestrates a set of
specialized tools through a central coordinator agent that handles delegation and response synthesis.

This system demonstrates how Retrieval-Augmented Generation (RAG) and tool usage can be seamlessly combined for flexible
enterprise question-answering.

---

## File

[agentic_rag.hocon](../../../registries/tools/agentic_rag.hocon)

---

## Description

The assistant is built around a **Front Man** agent that acts as the main point of contact with users. This agent determines
the best course of action—whether it be querying a web search engine, retrieving knowledge from PDF documents, or checking
a Slack channel—and delegates accordingly. The system is structured for scalability, adaptability, and easy integration
into business workflows.

- **Modular Task Delegation**: Tools are independently defined and can be flexibly composed in a graph-based or hierarchical
fashion.
- **Conversational Orchestration**: The front agent abstracts complexity, ensuring users experience a seamless and fluid
interaction.
- **RAG-based Retrieval**: Supports intelligent document Q&A via vectorstore-backed retrieval pipelines.
- **Live Source Access**: Enables up-to-date query resolution via Bing search or Slack message retrieval.

---

## Example Conversation

### Human

```text
what is the Evaluation Criteria in the rfp?
```

### AI (Agentic RAG Assistant)

```text
The evaluation criteria in the RFP are as follows:

    1. Any award made pursuant to this RFP will be based upon the proposal with appropriate information contained in the
    RFP.
    2. Vendors must address all matters raised in the RFP.
    3. Statements made about the performance and specifications of the proposed solution will be considered.
    4. Consideration is given to operational, technical, cost, and management requirements.
    5. Evaluation of offers will be based upon the Vendor’s responsiveness.

These criteria are used to assess the suitability of proposals and ensure they meet the necessary requirements outlined
in the RFP.
```

---

## Architecture Overview

### Frontman Agent: **Agentic RAG Assistant**

- Primary entry point for external user queries.
- Parses the inquiry and determines which tools to invoke.
- Integrates answers from tools to form a cohesive response.

### Supporting Tools

1. **website_search**
   - Powered by `ddgs_search`.
   - Retrieves up-to-date web results based on the query.
   - Additional info on [DDGS Search](https://github.com/deedy5/ddgs).

2. **rag_retriever**
   - Uses a Retrieval-Augmented Generation pipeline.
   - Accepts a `query` and returns answers based on embedded PDF documents.
   - Useful for answering domain-specific or internal document-based questions.

3. **slack_tool**
   - Interfaces with `slack` to retrieve recent messages from a specified channel.
   - Helpful for referencing ongoing conversations or updates.

---

## Functional Tools

These tools are independently defined and invoked by the frontman agent:

- **Bing Search Tool (`website_search`)**
    - Retrieves public web data using Bing.
    - Accepts configurable arguments like number of results.

- **RAG PDF Retriever (`rag_retriever`)**
    - Loads a remote PDF, builds an in-memory vectorstore, and answers questions from it.
    - Ideal for scenarios where precise answers are locked inside static documents.

- **Slack Message Retriever (`slack_tool`)**
    - Pulls messages from specified Slack channels.
    - Useful for blending informal organizational context with structured knowledge.

---

## Debugging Hints

Check the following during development or troubleshooting:

- Ensure the **agent** tool is correctly identified as the frontman (no parameters in its function definition).
- Make sure all tools listed under `"tools"` in the frontman agent exist and are loadable.
- Confirm that required arguments (like `query` or `channel_name`) are passed correctly.
- Validate vectorstore loading and document parsing for the RAG tool.
- Look at logs to ensure smooth delegation across tool calls and proper response integration.

---
