# Gemini Image Generation

The **Gemini Image Generation** is a task-oriented agentic system designed to help users create images through natural
language descriptions. It leverages Google's Gemini image generation capabilities, providing users with AI-generated
images based on their creative prompts and specifications.

---

## File

[gemini_image_generation.hocon](../../../registries/tools/gemini_image_generation.hocon)

---

## Description

At the core of the system is the Image Generator agent, which serves as the primary interface between the user and
Google's Gemini image generation capabilities. When a user gives an instruction—such as "generate an image of a gray
tabby cat hugging an otter with an orange scarf" or "draw a picture of a cute fuzzy cat with an umbrella"—the agent
intelligently routes the request to the appropriate image generation tool. The generated image is automatically
displayed in the user's browser and can optionally be saved to disk.

The system supports multiple Gemini models including the efficient `gemini-2.5-flash-image` (`Nano Banana`) and the
advanced `gemini-3-pro-image-preview` (`Nano Banana Pro`), which offers additional features like Google Search
integration and higher resolution options.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

```bash
pip install google-genai
```

Note: If langchain-google-genai is already installed in your environment, this package is already included.

### Environment Variables

```bash
export GOOGLE_API_KEY="your_google_api_key_here"
# or
export GEMINI_API_KEY="your_gemini_api_key_here"
```

For more information on setting up Gemini, see:

- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)

- [Gemini Image Generation Guide](https://ai.google.dev/gemini-api/docs/image-generation)

---

## Example Conversation

### Human

```text
Generate an image of gray tabby cat hugging an otter with an orange scarf
```

### AI (Image Generator)

```text
Image generation completed.
```

---

## Architecture Overview

### Frontman Agent: image_generator

- Main entry point for user image generation requests.
- Interprets natural language descriptions and delegates tasks to the image generation tool.
- Processes results and provides feedback about the generated image.
- Handles the display and optional saving of generated images.

### Tools: gemini_image_generation

This agent is a coded tool that can be called from the toolbox with the name `gemini_image_generation`, which leverages
Google's Gemini image generation capabilities.

#### Tool Arguments and Parameters

**From Calling Agent:**

- `query`: The image description derived from user inquiry (required)
- `aspect_ratio`: Aspect ratio for the generated image (optional)
  - Allowed values: "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
- `image_size`: Size of the generated image (optional, only for `gemini-3-pro-image-preview`)
  - Allowed values: "1K", "2K", "4K"
- `google_search`: Whether to use Google Search for image generation (optional, only for `gemini-3-pro-image-preview`)
  - Defaults to `false`

**From User Configuration:**

- `gemini_model`: Gemini model to use for generation (defaults to "gemini-2.5-flash-image")
  - Allowed values: "gemini-2.5-flash-image", "gemini-3-pro-image-preview"
- `save_image_file`: Boolean flag to save the generated image to disk (defaults to `false`)
- `open_in_browser`: Boolean flag to automatically open the image in browser (defaults to `false`)

For additional parameters and details, see
[Gemini Image Generation Documentation](https://ai.google.dev/gemini-api/docs/image-generation)

---

## Key Features

### Multi-Model Support

- **gemini-2.5-flash-image**: Fast, efficient image generation for everyday use
- **gemini-3-pro-image-preview**: Advanced model with additional capabilities including higher resolutions and Google
Search integration

### Flexible Image Configuration

- Multiple aspect ratios supported (square, portrait, landscape, cinematic)
- Configurable image sizes (1K, 2K, 4K) for pro model
- Google Search integration for enhanced image generation context

### File Management

- Optional permanent file saving with customizable filenames
- Temporary file creation for preview
- Automatic browser opening for immediate viewing
- Returns `file:///` URI scheme paths for local access

### Multimodal Output

- Generates images with optional accompanying text descriptions
- Supports both text and image response modalities

---

## Debugging Hints

When developing or debugging the Gemini Image Generation Assistant, keep the following in mind:

- **API Key Validation**: Ensure your `GOOGLE_API_KEY` or `GEMINI_API_KEY` is valid and has access to image generation
capabilities.
- **Model Availability**: Verify that the specified `gemini_model` is available in your Google AI account.
- **Package Installation**: Confirm that google-genai package is properly installed.
- **Tool Registration**: Ensure the `gemini_image_generation` toolbox is correctly registered and mapped to the
GeminiImageGeneration coded tool.
- **Query Formatting**: Check that user inquiries are properly formatted and passed to the image generation tool.
- **Browser Access**: Ensure the system can open a web browser to display generated images.
- **File Permissions**: If `save_image_file` is enabled, verify write permissions in the target directory.
- **Model-Specific Features**: Remember that `image_size` and `google_search` are only available for
`gemini-3-pro-image-preview`.

- **Response Handling**: Monitor for both text and image parts in the response, as models may return text alongside
images.
- **Error Handling**: Monitor for Google API errors and ensure graceful error handling.
- **Rate Limits**: Be aware of API rate limits that may affect image generation frequency.

### Common Issues

- **Import Errors**: Ensure google-genai package is installed correctly
- **Authentication Failures**: Verify API key is set and valid (check both `GOOGLE_API_KEY` and `GEMINI_API_KEY`
environment variables)
- **Model Errors**: Confirm the specified Gemini model is accessible and supports image generation
- **Feature Availability**: Verify that advanced features like `image_size` and `google_search` are only used with
`gemini-3-pro-image-preview`
- **Invalid Aspect Ratios**: Ensure aspect ratio values match the allowed options
- **Browser Display Failures**: Check that webbrowser module can successfully open files
- **File Save Errors**: Verify write permissions and disk space when saving images
- **Missing Image Data**: Check that the response contains inline_data with image MIME type
- **Response Parsing Issues**: Ensure proper handling of multimodal responses with both text and image parts

---

## Resources

- [Gemini API Documentation](https://ai.google.dev/gemini-api/docs)
  Complete guide to Google's Gemini API and its capabilities.
- [Gemini Image Generation Guide](https://ai.google.dev/gemini-api/docs/image-generation)
  Detailed specifications and parameters for Gemini's image generation capabilities.
- [Nano Banana Documentation](https://ai.google.dev/gemini-api/docs/nanobanana)
  Information about Gemini's nano banana and nano banana pro models.
- [Google AI Developer Documentation](https://ai.google.dev/)
  Central hub for all Google AI developer resources.
- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)  
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.
- [Agent HOCON Reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md)  
  Schema specifications for agent configuration files.
