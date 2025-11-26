# Anthropic Web Search

The **Anthropic Web Search** is a task-oriented agentic system designed to help users search and retrieve information from the web efficiently. It leverages Anthropic's built-in web search tool through a specialized toolkit, providing users with accurate, up-to-date information from across the internet through natural language queries.

---

## File

[anthropic_web_search.hocon](../../../registries/tools/anthropic_web_search.hocon)

---

## Description

At the core of the system is the Web Search Assistant agent, which serves as the primary interface between the user and Anthropic's built-in web search capabilities. When a user gives an instruction—such as "find recent news about AI" or "search for information about renewable energy trends"—the agent intelligently routes the request to the appropriate web search tool.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

```bash
pip install langchain-anthropic>=0.3.13
```

### Environment Variable

```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

For more information on setting up Anthropic tools, see:

- [Anthropic Tool Use Overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)

- [LangChain Anthropic Integration](https://python.langchain.com/docs/integrations/chat/anthropic/#built-in-tools)

---

## Example Conversation

### Human

```text
Can you search for the latest developments in quantum computing research?
```

### AI (Anthropic Web Search)

```text
I found several recent developments in quantum computing research. Here are the key highlights:

**Breakthrough in Error Correction**: IBM announced a significant advancement in quantum error correction, achieving a 50% reduction in error rates using their new quantum processor architecture.

**Google's Quantum Advantage**: Recent studies show Google's quantum computer solved a complex optimization problem 10,000 times faster than classical computers.

**Commercial Applications**: Several startups are now offering quantum computing services for drug discovery and financial modeling, marking the transition from research to practical applications.

Would you like me to search for more specific information about any of these developments?
```

---

## Architecture Overview

### Frontman Agent: searcher

- Main entry point for user search inquiries and information requests.

- Interprets natural language queries and delegates tasks to the web search tool.

- Processes and contextualizes search results to provide comprehensive, relevant responses.

- Handles follow-up questions and iterative search refinements.

### Tools: website_search

This agent is a coded tool that can be called from the toolbox with the name `anthropic_search`,
which leverages Anthropic's built-in web search capabilities.

#### Tool Arguments and Parameters

- `query`: The search query derived from user inquiry that `searcher` passes to the tool

- `anthropic_model`: Model used for search processing ("claude-3-7-sonnet-20250219" as default)

- `additional_kwargs`: Optional parameters for fine-tuning search behavior

---

## Debugging Hints

When developing or debugging the Web Search Assistant, keep the following in mind:

- **API Key Validation**: Ensure your `ANTHROPIC_API_KEY` is valid and has access to built-in tools.

- **Model Availability**: Verify that `anthropic_model` is available in your Anthropic account tier.

- **Tool Registration**: Confirm that the `anthropic_search` toolbox is correctly registered and mapped to the AnthropicWebSearch coded tool.

- **Query Formatting**: Check that user inquiries are properly formatted and passed to the search tool.

- **Error Handling**: Monitor for AnthropicError exceptions and ensure graceful error handling.

- **Rate Limits**: Be aware of API rate limits that may affect search frequency.

- **Beta Features**: Some Anthropic tools may require beta access or special parameters.

### Common Issues

- **Import Errors**: Ensure langchain-anthropic>=0.3.13 is installed

- **Authentication Failures**: Verify API key is set and valid

- **Tool Not Found**: Check that the web_search_20250305 tool type is available

- **Model Errors**: Confirm the specified Claude model is accessible

---

## Resources

- [Anthropic Tool Use Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)  
  Complete guide to Anthropic's built-in tools and their capabilities.

- [LangChain Anthropic Integration](https://python.langchain.com/docs/integrations/chat/anthropic/#built-in-tools)  
  Documentation on using Anthropic tools within the LangChain framework.

- [Web Search Tool Specifications](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/web-search-tool)  
  Detailed specifications and parameters for Anthropic's web search tool.

- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)  
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.
