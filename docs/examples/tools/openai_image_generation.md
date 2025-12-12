# OpenAI Image Generation

The **OpenAI Image Generation** is a task-oriented agentic system designed to help users create images through natural language descriptions. It leverages OpenAI's built-in image generation tool through a specialized toolkit, providing users with AI-generated images based on their creative prompts and specifications.

---

## File

[openai_image_generation.hocon](../../../registries/tools/openai_image_generation.hocon)

---

## Description

At the core of the system is the Image Generator agent, which serves as the primary interface between the user and OpenAI's built-in image generation capabilities. When a user gives an instruction—such as "generate an image of a gray tabby cat hugging an otter with an orange scarf" or "draw a picture of a cute fuzzy cat with an umbrella"—the agent intelligently routes the request to the appropriate image generation tool. The generated image is automatically displayed in the user's browser, and can optionally be saved to disk.

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
Generate an image of gray tabby cat hugging an otter with an orange scarf
```

### AI (Image Generator)

```text
I've generated the image for you! The image shows a gray tabby cat warmly hugging an otter wearing a bright orange scarf. The scene captures a heartwarming moment between these two adorable animals.
```

---

## Architecture Overview

### Frontman Agent: image_generator

- Main entry point for user image generation requests.

- Interprets natural language descriptions and delegates tasks to the image generation tool.

- Processes results and provides feedback about the generated image.

- Handles the display and optional saving of generated images.

### Tools: openai_image_generation

This agent is a coded tool that can be called from the toolbox with the name `openai_image_generation`,
which leverages OpenAI's built-in image generation capabilities.

#### Tool Arguments and Parameters

- `query`: The image description derived from user inquiry (note: the model may revise this prompt for optimal results)

- `openai_model`: Model used for image generation (defaults to "gpt-5")

- `save_image_file`: Boolean flag to save the generated image to disk (defaults to `true`)

- `additional_kwargs`: Optional parameters for fine-tuning image generation behavior
  - `quality`: Image quality setting (e.g., "medium", "high")
  - Additional parameters as documented in [OpenAI's image generation guide](https://platform.openai.com/docs/guides/tools-image-generation)

---

## Debugging Hints

When developing or debugging the OpenAI Image Generation Assistant, keep the following in mind:

- **API Key Validation**: Ensure your `OPENAI_API_KEY` is valid and has access to preview tools.

- **Model Availability**: Verify that the specified `openai_model` is available in your OpenAI account tier.

- **Preview Tool Access**: Confirm your account has access to the image generation tool.

- **Tool Registration**: Ensure the `openai_image_generation` toolbox is correctly registered and mapped to the OpenAIImageGeneration coded tool.

- **LangChain Version**: Verify langchain-openai>=0.3.26 is installed for Responses API support.

- **Query Formatting**: Check that user inquiries are properly formatted and passed to the image generation tool.

- **Browser Access**: Ensure the system can open a web browser to display generated images.

- **File Permissions**: If `save_image_file` is enabled, verify write permissions in the target directory.

- **Revised Prompts**: Monitor logs to see how OpenAI revises user prompts for optimal image generation.

- **Error Handling**: Monitor for OpenAI API errors and ensure graceful error handling.

- **Rate Limits**: Be aware of API rate limits that may affect image generation frequency.

### Common Issues

- **Import Errors**: Ensure langchain-openai>=0.3.26 is installed

- **Authentication Failures**: Verify API key is set and valid

- **Preview Tool Access**: Check that your account has image generation tool permissions

- **Model Errors**: Confirm the specified GPT model is accessible and supports image generation

- **Tool Not Found**: Verify that the image generation tool is available in your account

- **Responses API Issues**: Ensure proper configuration for the Responses API integration

- **Browser Display Failures**: Check that webbrowser module can successfully open files

- **File Save Errors**: Verify write permissions and disk space when saving images

---

## Resources

- [OpenAI Tools Guide](https://platform.openai.com/docs/guides/tools?api-mode=responses)  
  Complete guide to OpenAI's built-in tools and their capabilities.

- [OpenAI Image Generation Tool Documentation](https://platform.openai.com/docs/guides/tools-image-generation)  
  Detailed specifications and parameters for OpenAI's image generation tool.

- [LangChain OpenAI Responses API](https://python.langchain.com/docs/integrations/chat/openai/#responses-api)  
  Documentation on using OpenAI's Responses API within the LangChain framework.

- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)  
  Complete API reference for OpenAI's services and endpoints.

- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)  
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.
