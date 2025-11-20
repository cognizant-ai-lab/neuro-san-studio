# OpenAI Web Search

The **OpenAI Web Search** is a task-oriented agentic system designed to help users search and retrieve information from the web efficiently. It leverages OpenAI's built-in web search tool through a specialized toolkit, providing users with accurate, up-to-date information from across the internet through natural language queries.

---

## File

[openai_web_search.hocon](../../../registries/tools/openai_web_search.hocon)

---

## Description

At the core of the system is the OpenAI Web Search Assistant agent, which serves as the primary interface between the user and OpenAI's built-in web search capabilities. When a user gives an instruction—such as "find recent news about climate change" or "search for information about machine learning trends"—the agent intelligently routes the request to the appropriate web search tool.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

```bash
pip install langchain-openai>=0.3.26
```

### Environment Variables

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

For more information on setting up OpenAI tools, see:

- [OpenAI Tools Guide](https://platform.openai.com/docs/guides/tools?api-mode=responses)

- [LangChain OpenAI Responses API](https://python.langchain.com/docs/integrations/chat/openai/#responses-api)

---

## Example Conversation

### Human

```text
Can you search for the latest developments in renewable energy technology?
```

### AI (OpenAI Web Search Assistant)

```text
I found several significant recent developments in renewable energy technology:

**Solar Energy Breakthroughs**: New perovskite-silicon tandem solar cells have achieved record efficiency of 33.7%, representing a major leap in photovoltaic technology that could dramatically reduce solar energy costs.

**Wind Power Innovations**: Offshore wind turbines are now reaching unprecedented heights of 280 meters, with individual turbines capable of powering 20,000 homes. The latest designs include floating platforms for deep-water installations.

**Energy Storage Advances**: Next-generation lithium-iron-phosphate batteries are showing 95% capacity retention after 10,000 charge cycles, solving one of renewable energy's biggest challenges - reliable energy storage.

**Green Hydrogen Progress**: Electrolysis efficiency improvements have reduced the cost of green hydrogen production by 40% in the past year, making it increasingly viable as a clean fuel alternative.

Would you like me to search for more specific information about any of these developments, or explore other aspects of renewable energy technology?
```

---

## Architecture Overview

### Frontman Agent: searcher

- Main entry point for user search inquiries and information requests.

- Interprets natural language queries and delegates tasks to the web search tool.

- Processes and contextualizes search results to provide comprehensive, relevant responses.

- Handles follow-up questions and iterative search refinements.

### Tools: website_search

This agent is a coded tool that can be called from the toolbox with the name `openai_search`,
which leverages OpenAI's built-in web search capabilities.

#### Tool Arguments and Parameters

- `query`: The search query derived from user inquiry

- `openai_model`: Model used for search processing ("gpt-4o-2024-08-06" as default)

- `additional_kwargs`: Optional parameters for fine-tuning search behavior

---

## Debugging Hints

When developing or debugging the OpenAI Web Search Assistant, keep the following in mind:

- **API Key Validation**: Ensure your `OPENAI_API_KEY` is valid and has access to preview tools.

- **Model Availability**: Verify that `openai_meodel` is available in your OpenAI account tier.

- **Preview Tool Access**: Confirm your account has access to the `web_search_preview` tool.

- **Tool Registration**: Ensure the `openai_search` toolbox is correctly registered and mapped to the OpenAIWebSearch coded tool.

- **LangChain Version**: Verify langchain-openai>=0.3.26 is installed for Responses API support.

- **Query Formatting**: Check that user inquiries are properly formatted and passed to the search tool.

- **Error Handling**: Monitor for OpenAI API errors and ensure graceful error handling.

- **Rate Limits**: Be aware of API rate limits that may affect search frequency.

### Common Issues

- **Import Errors**: Ensure langchain-openai>=0.3.26 is installed

- **Authentication Failures**: Verify API key is set and valid

- **Preview Tool Access**: Check that your account has preview tool permissions

- **Model Errors**: Confirm the specified GPT model is accessible

- **Tool Not Found**: Verify that web_search_preview is available in your account

- **Responses API Issues**: Ensure proper configuration for the Responses API integration

---

## Resources

- [OpenAI Tools Guide](https://platform.openai.com/docs/guides/tools?api-mode=responses)  
  Complete guide to OpenAI's built-in tools and their capabilities.

- [OpenAI Web Search Tool Documentation](https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses)  
  Detailed specifications and parameters for OpenAI's web search tool.

- [LangChain OpenAI Responses API](https://python.langchain.com/docs/integrations/chat/openai/#responses-api)  
  Documentation on using OpenAI's Responses API within the LangChain framework.

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)  
  Complete API reference for OpenAI's services and endpoints.

- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)  
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.
