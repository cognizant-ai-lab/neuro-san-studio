# OpenAI Code Interpreter

The **OpenAI Code Interpreter** is a task-oriented agentic system designed to help users execute code and perform computational tasks efficiently. It leverages OpenAI's built-in code interpreter tool through a specialized toolkit, providing users with the ability to run Python code, generate visualizations, perform data analysis, and create computational solutions through natural language commands.

---

## File

[openai_code_interpreter.hocon](../../../registries/tools/openai_code_interpreter.hocon)

---

## Description

At the core of the system is the OpenAI Code Interpreter Assistant agent, which serves as the primary interface between the user and OpenAI's built-in code interpreter capabilities. When a user gives an instruction—such as "analyze this dataset and create visualizations" or "solve this mathematical problem with code"—the agent intelligently routes the request to the appropriate code interpreter tool.

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
Can you analyze the sales data I have and create a comprehensive report with visualizations? The data shows: Q1: $120K, Q2: $150K, Q3: $135K, Q4: $180K.
```

### AI (OpenAI Code Interpreter Assistant)

```text
I'll analyze your quarterly sales data and create a comprehensive report with visualizations.

*[Executes code to process data and generate analysis]*

## Sales Data Analysis Report

### Key Performance Metrics:
- **Total Annual Sales**: $585,000
- **Average Quarterly Sales**: $146,250
- **Best Performance**: Q4 with $180,000 (23% above average)
- **Growth Rate**: 50% increase from Q1 to Q4
- **Quarter-over-Quarter Growth**: Q1→Q2: +25%, Q2→Q3: -10%, Q3→Q4: +33%

### Visualizations Created:
1. **Quarterly Sales Bar Chart**: Shows clear upward trend with Q4 peak
2. **Growth Rate Line Graph**: Illustrates the 50% annual growth trajectory
3. **Performance Distribution Pie Chart**: Shows Q4 representing 31% of annual sales

### Key Insights:
- **Strong Recovery**: Despite Q3 dip, Q4 showed exceptional 33% growth
- **Seasonal Patterns**: Possible holiday season boost in Q4
- **Growth Momentum**: Consistent year-over-year improvement trend

### Recommendations:
- Investigate Q4 success factors for replication
- Analyze Q3 performance decline causes
- Plan capacity for sustained growth trajectory

The analysis shows a healthy business with strong growth momentum and exceptional Q4 performance. Would you like me to perform any additional analysis or create different types of visualizations?
```

---

## Architecture Overview

### Frontman Agent: coder

- Main entry point for user coding and computational requests.

- Interprets natural language instructions and delegates tasks to the code interpreter tool.

- Coordinates execution results and provides comprehensive feedback on computational outputs.

- Manages conversation flow and follow-up interactions.

---

### Tools: code_executor

This agent is a coded tool that can be called from the toolbox with the name `anthropic_code_execution`,
which leverages Anthropic's built-in code execution capabilities.

#### Tool Arguments and Parameters

- `query`: The user's natural language request for code execution

- `openai_model`: Model used for code generation ("gpt-4o-2024-08-06" as default)

- `container`: Execution container configuration (automatically created if not specified)

- `additional_kwargs`: Optional parameters for fine-tuning execution behavior

---

## Debugging Hints

When developing or debugging the OpenAI Code Interpreter Assistant, keep the following in mind:

- **API Key Validation**: Ensure your `OPENAI_API_KEY` is valid and has access to code interpreter functionality.

- **Model Availability**: Verify that `openai_model` is available in your OpenAI account tier.

- **Code Interpreter Access**: Confirm your account has access to OpenAI's code interpreter tool.

- **Tool Registration**: Ensure the `openai_code_interpreter` toolbox is correctly registered and mapped to the OpenAICodeInterpreter coded tool.

- **LangChain Version**: Verify langchain-openai>=0.3.26 is installed for proper tool support.

- **Quota Management**: Monitor API usage and code interpreter quota limits.

### Common Issues

- **Import Errors**: Ensure langchain-openai>=0.3.26 is installed

- **Authentication Failures**: Verify API key is set and valid

- **Code Interpreter Access**: Check that your account has code interpreter permissions

- **Model Errors**: Confirm the specified GPT model is accessible

- **Container Issues**: Verify container creation and management functionality

- **Quota Exceeded**: Monitor code interpreter usage against account limits

- **Library Limitations**: Some specialized libraries may not be pre-installed

---

## Resources

- [OpenAI Tools Guide](https://platform.openai.com/docs/guides/tools?api-mode=responses)  
  Complete guide to OpenAI's built-in tools and their capabilities.

- [OpenAI Code Interpreter Documentation](https://platform.openai.com/docs/guides/code-interpreter)  
  Detailed documentation for OpenAI's code interpreter functionality.

- [LangChain OpenAI Responses API](https://python.langchain.com/docs/integrations/chat/openai/#responses-api)  
  Documentation on using OpenAI's Responses API within the LangChain framework.

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)  
  Complete API reference for OpenAI's services and endpoints.

- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)  
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.