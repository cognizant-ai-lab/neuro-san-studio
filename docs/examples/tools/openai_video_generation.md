# OpenAI Video Generation

The **OpenAI Video Generation** is a task-oriented agentic system designed to help users create, remix, and describe
videos through natural language descriptions. It leverages OpenAI's built-in video generation tool through a
specialized toolkit, providing users with AI-generated videos based on their creative prompts and specifications.

---

## File

[openai_video_generation.hocon](../../../registries/tools/openai_video_generation.hocon)

---

## Description

At the core of the system is the Video Generator agent, which serves as the primary interface between the user and
OpenAI's built-in video generation capabilities. When a user gives an instruction—such as "generate a video of a gray
tabby cat hugging an otter with an orange scarf" or "create a video of a cute fuzzy cat with an umbrella under the
rain"—the agent intelligently routes the request to the appropriate video generation tool. The generated video is
automatically displayed in the user's browser and can optionally be saved to disk.

The system also includes a Video Describer tool that analyzes generated videos by extracting frames and using
vision-capable language models to provide detailed descriptions of the video content.

---

## Prerequisites

This agent network requires the following setup:

### Python Dependencies

```bash
pip install langchain-openai>=0.3.26 opencv-python aiohttp
```

### Environment Variables

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

For more information on setting up OpenAI tools, see:

- [OpenAI Video Generation Guide](https://platform.openai.com/docs/guides/video-generation)

---

## Example Conversation

### Human

```text
Generate a video of gray tabby cat hugging an otter with an orange scarf
```

### AI (Video Generator)

```text
Video generation completed with id vid_abc123xyz. Saved to: file:///path/to/vid_abc123xyz.mp4
```

### Human

```text
Describe what's in the video you just created
```

### AI (Video Generator)

```text
The video shows a gray tabby cat warmly embracing an otter that is wearing a bright orange scarf. The scene captures a
heartwarming moment between these two adorable animals, with gentle movements and affectionate interaction throughout
the clip.
```

---

## Architecture Overview

### Frontman Agent: video_generator

- Main entry point for user video generation, remixing, and description requests.
- Interprets natural language descriptions and delegates tasks to the appropriate tools.
- Processes results and provides feedback about generated videos, including file paths.
- Handles the display and optional saving of generated videos.

### Tools

#### openai_video_generation

This agent is a coded tool that can be called from the toolbox with the name `openai_video_generation`, which leverages
OpenAI's built-in video generation capabilities.

##### Tool Arguments and Parameters

- `query`: The video description derived from user inquiry (required)
- `video_id`: Optional ID of an existing video to remix
- `openai_model`: Model used for video generation (defaults to "sora-2", allowed values: "sora-2", "sora-2-pro")
- `save_video_file`: Boolean flag to save the generated video to disk (defaults to `false`)
- `open_in_browser`: Boolean flag to automatically open the video in browser (defaults to `false`)
- `seconds`: Clip duration in seconds (allowed values: "4", "8", "12"; defaults to "4")
- `size`: Output resolution formatted as width x height (allowed values: "720x1280", "1280x720", "1024x1792",
"1792x1024"; defaults to "720x1280")

For additional parameters, see
[OpenAI Video Generation API Reference](https://platform.openai.com/docs/api-reference/videos)

Note: `input_reference` is not currently supported.

#### video_describer

This coded tool analyzes video content by extracting frames and using a vision-capable language model to describe what
happens in the video.

##### Tool Arguments and Parameters

- `file_path`: Path to the video file to be described (required)
- `openai_model`: OpenAI model to use for description (defaults to "gpt-4o"; must support image input)

---

## Key Features

### Video Generation

- Creates videos from text prompts using OpenAI's Sora models
- Supports multiple durations (4, 8, or 12 seconds)
- Offers various resolution options for different aspect ratios
- Asynchronous processing with status polling
- Automatic timeout handling (600 seconds default)

### Video Remixing

- Modify existing videos with new prompts
- Build upon previously generated content
- Maintain video ID references for iterative editing

### Video Description

- Automatically extracts frames from videos
- Uses vision-capable language models to analyze content
- Provides detailed descriptions of video scenes and actions

### File Management

- Optional permanent file saving
- Temporary file creation for preview
- Automatic browser opening for immediate viewing
- Returns `file:///` URI scheme paths for local access

---

## Debugging Hints

When developing or debugging the OpenAI Video Generation Assistant, keep the following in mind:

- **API Key Validation**: Ensure your `OPENAI_API_KEY` is valid and has access to video generation capabilities.
- **Model Availability**: Verify that the specified `openai_model` is available in your OpenAI account tier.
- **Video Generation Access**: Confirm your account has access to the video generation tool.
- **Tool Registration**: Ensure the `openai_video_generation` toolbox is correctly registered and mapped to the
OpenAIVideoGeneration coded tool.
- **LangChain Version**: Verify langchain-openai>=0.3.26 is installed for proper integration.
- **Query Formatting**: Check that user inquiries are properly formatted and passed to the video generation tool.
- **Browser Access**: Ensure the system can open a web browser to display generated videos.
- **File Permissions**: If `save_video_file` is enabled, verify write permissions in the target directory.
- **Timeout Configuration**: The default timeout is 600 seconds; adjust `max_execution_seconds` if needed for longer
videos.
- **Polling Interval**: Status checks occur every 5 seconds; monitor logs for progress updates.
- **Video Frame Extraction**: Ensure opencv-python is properly installed for the video describer tool.
- **Error Handling**: Monitor for OpenAI API errors and ensure graceful error handling.
- **Rate Limits**: Be aware of API rate limits that may affect video generation frequency.

### Common Issues

- **Import Errors**: Ensure all dependencies (langchain-openai>=0.3.26, opencv-python, aiohttp) are installed
- **Authentication Failures**: Verify API key is set and valid
- **Video Generation Access**: Check that your account has video generation permissions
- **Model Errors**: Confirm the specified model is accessible and supports video generation
- **Timeout Errors**: Video generation may take several minutes; ensure timeout is set appropriately
- **Browser Display Failures**: Check that webbrowser module can successfully open files
- **File Save Errors**: Verify write permissions and disk space when saving videos
- **Frame Extraction Issues**: Ensure opencv-python is installed and video file paths are valid
- **Status Polling Failures**: Check network connectivity and API availability
- **Remix Errors**: Verify that the video ID being remixed exists and is accessible

---

## Resources

- [OpenAI Video Generation Guide](https://platform.openai.com/docs/guides/video-generation)
  Complete guide to OpenAI's video generation capabilities and best practices.
- [OpenAI Video API Reference](https://platform.openai.com/docs/api-reference/videos)
  Detailed specifications and parameters for OpenAI's video generation API.
- [LangChain OpenAI Integration](https://python.langchain.com/docs/integrations/chat/openai/)
  Documentation on using OpenAI's services within the LangChain framework.
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
  Complete API reference for OpenAI's services and endpoints.
- [Coded Tools Implementation Guide](https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#coded-tools)
  Learn how to implement and integrate custom coded tools in Neuro-SAN Studio.
- [Agent HOCON Reference](https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/agent_hocon_reference.md)
  Schema specifications for agent configuration files.