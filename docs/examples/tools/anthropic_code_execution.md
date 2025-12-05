# Anthropic Code Execution

The **Code Execution Assistant** is a task-oriented agentic system designed to help users execute code and perform computational tasks efficiently. It leverages Anthropic's built-in code execution tool through a specialized toolkit, providing users with the ability to run Python code, generate visualizations, perform data analysis, and create files through natural language commands.

---

## File

[anthropic_code_execution.hocon](../../../registries/tools/anthropic_code_execution.hocon)

---

## Description

At the core of the system is the Code Execution Assistant agent, which serves as the primary interface between the user and Anthropic's built-in code execution capabilities. When a user gives an instruction—such as "create a bar chart of sales data" or "analyze this dataset and find correlations"—the agent intelligently routes the request to the appropriate code execution tool.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

```bash
pip install langchain-anthropic>=0.3.13
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

### System Requirements

  - Appplications for opening generated files (charts, reports, etc.)

For more information on setting up Anthropic tools, see:

- [Anthropic Tool Use Overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)

- [Anthropic Code Execution Tool](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/code-execution-tool)

- [LangChain Anthropic Integration](https://python.langchain.com/docs/integrations/chat/anthropic/#code-execution)

---

## Example Conversation

### Human

```text
Can you create a visualization showing the trend of monthly sales data: January: $50K, February: $65K, March: $45K, April: $70K, May: $80K?
```

### AI (Anthropic Code Execution)

```text
I'll create a visualization of your monthly sales data showing the trend over the 5-month period.

*[Executes code to generate chart]*

I've created a line chart visualization showing your monthly sales trend. The chart displays:

- **Sales Growth**: Overall upward trend from January ($50K) to May ($80K)

- **Peak Month**: May with $80K in sales

- **Dip**: March showed a temporary decrease to $45K

- **Recovery**: Strong recovery in April ($70K) leading to the peak in May

The chart has been saved as 'sales_trend_chart.png' and should open automatically in your browser. The visualization includes proper labels, gridlines, and formatting to clearly show your sales progression over the 5-month period.

Would you like me to perform any additional analysis on this data, such as calculating growth rates or creating different types of visualizations?
```

---

## Architecture Overview

### Frontman Agent: coder

- Main entry point for user coding and computational requests.

- Interprets natural language instructions and delegates tasks to the code execution tool.

- Relays user messages directly to the execution tool without creating code itself (as per instructions).

- Coordinates file handling and provides feedback on generated outputs.

### Tools: code_executor

This agent is a coded tool that can be called from the toolbox with the name `anthropic_code_execution`,
which leverages Anthropic's built-in code execution capabilities.

#### Tool Arguments and Parameters

- `query`: The user's natural language request for code execution

- `anthropic_model`: Model used for code generation ("claude-3-7-sonnet-20250219" as default)

- `save_file`: Boolean flag to automatically save generated files (Default to `false`)

- `additional_kwargs`: Optional parameters for fine-tuning execution behavior

#### File Management

- **File ID Extraction**: Automatically identifies generated files from execution results

- **Metadata Retrieval**: Fetches file information including names and types

- **Download & Save**: Downloads files from Anthropic's container to local filesystem

- **Auto-Open**: Automatically opens generated files in the default browser/application

---

## Debugging Hints

When developing or debugging the Code Execution Assistant, keep the following in mind:

- **API Key Validation**: Ensure your `ANTHROPIC_API_KEY` is valid and has access to beta features.

- **Model Availability**: Verify that `anthropic_model` is available in your Anthropic account tier.

- **Beta Access**: Verify access to the code execution beta (`code-execution-2025-05-22`).

- **Tool Registration**: Ensure the `anthropic_code_execution` toolbox is correctly registered and mapped to the AnthropicCodeExecution coded tool.

- **File Permissions**: Check that the application has write permissions for saving generated files.

### Common Issues

- **Import Errors**: Ensure langchain-anthropic>=0.3.13 is installed

- **Authentication Failures**: Verify API key is set and has beta access

- **Tool Not Found**: Check that the code_execution_20250522 tool type is available

- **File Save Errors**: Confirm write permissions and available disk space

- **Beta Access Denied**: Verify your Anthropic account has access to code execution beta

- **File Opening Issues**: Check default application associations for generated file types

---

## Resources

- [Anthropic Code Execution Tool Documentation](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/code-execution-tool)  
  Complete guide to Anthropic's code execution capabilities and parameters.

- [LangChain Anthropic Code Execution](https://python.langchain.com/docs/integrations/chat/anthropic/#code-execution)  
  Documentation on using Anthropic code execution within the LangChain framework.

- [Anthropic Tool Use Overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)  
  General documentation for Anthropic's built-in tools and their capabilities.

- [Anthropic Files API](https://docs.anthropic.com/en/api/files)  
  API reference for managing files generated by code execution.

- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)  
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.
