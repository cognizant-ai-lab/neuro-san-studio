# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import logging
import os
import webbrowser
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

# pylint: disable=import-error
from google.genai import Client
from google.genai.types import Blob
from google.genai.types import GenerateContentConfig
from google.genai.types import GenerateContentResponse
from google.genai.types import ImageConfig
from neuro_san.interfaces.coded_tool import CodedTool


class GeminiImageGeneration(CodedTool):
    """
    A CodedTool implementation for invoking Gemini image generation (nano banana and nano banana pro).

    See
    - https://ai.google.dev/gemini-api/docs/nanobanana
    - https://ai.google.dev/gemini-api/docs/image-generation
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent or user. This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                - from calling agent
                    - "query" (str): Request from the user prompt.
                    - "aspect_ratio" (str): Aspect ratio for the generated image. E.g., "16:9".
                    - "image_size" (str): Size of the generated image. E.g., "1K", "2K".
                    - "google_search" (bool): Whether or not to use google search for the generated image.
                        Only available for gemini-3-pro-image-preview. Default to False.
                - from user
                    - "gemini_model" (str): Gemini model to call the tool. Default to gemini-2.5-flash-image.
                    - "save_image_file" (bool): Whether to save the generated image file. Default to False.
                    - "open_in_browser" (bool): Whether to open the generated image in the web browser.
                        Default to False.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                Tool results
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """

        # Extract arguments
        (query, gemini_model, open_in_browser, save_image_file, image_config, tools) = self.extract_arguments(args)

        # Call Gemini model for image generation
        response: GenerateContentResponse = await self.get_response(query, gemini_model, image_config, tools)

        # Extract text and image blocks
        text: str = ""
        for part in response.parts:
            if part.text:
                # Model may or may not return text along with image
                self.logger.info("Generated Text: %s", part.text)
                text = part.text
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                image_block: Blob = part.inline_data
                self.display_image(image_block, save_image_file, open_in_browser)

        # Return generated text if available; otherwise indicate completion
        return text or "Image generation completed."

    def extract_arguments(
        self, args: dict[str, Any]
    ) -> tuple[str, str, bool, bool, dict[str, Any], list[dict[str, Any]]]:
        """
        Extract arguments from the args dictionary.
        :param args: Argument dictionary.
        :return: Tuple of extracted arguments.
        """

        # LLM-generated arguments

        # The prompt for image generation.
        query: str = args.get("query")
        if not query:
            raise ValueError("No query provided.")

        # Optional configurations for image generation.
        aspect_ratio: str = args.get("aspect_ratio")
        image_size: str = args.get("image_size")

        # User-defined arguments

        # The Gemini model to use when calling the tool.
        gemini_model: str = args.get("gemini_model", "gemini-2.5-flash-image")
        # Whether or not to open the generated image in the web browser.
        open_in_browser: bool = args.get("open_in_browser", False)
        # Whether or not to save image file on disk.
        save_image_file: bool = args.get("save_image_file", False)
        # Whether or not to use google search for the generated image.  Only available for gemini-3-pro-image-preview.
        google_search: bool = args.get("google_search", False)

        # Set configurations for image generation and tools
        image_config: dict[str, Any] = {}
        if aspect_ratio:
            image_config["aspect_ratio"] = aspect_ratio

        tools: list[dict[str, Any]] = []
        if gemini_model == "gemini-3-pro-image-preview":
            if image_size:
                image_config["image_size"] = image_size
            if google_search:
                tools.append({"google_search": {}})

        return query, gemini_model, open_in_browser, save_image_file, image_config, tools

    async def get_response(
        self, query: str, gemini_model: str, image_config: dict[str, Any], tools: list[dict[str, Any]]
    ) -> GenerateContentResponse:
        """
        Asynchronous version of the Gemini image generation call.
        :param query: The prompt for image generation.
        :param gemini_model: The Gemini model to use when calling the tool.
        :param image_config: Configurations for image generation.
        :param tools: Configurations for tools.
        :return: GenerateContentResponse from Gemini API.
        """

        # Initialize Gemini client
        client = Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        # Call Gemini model for image generation
        response: GenerateContentResponse = await client.aio.models.generate_content(
            model=gemini_model,
            contents=query,
            config=GenerateContentConfig(
                response_modalities=["Text", "Image"], image_config=ImageConfig(**image_config), tools=tools
            ),
        )
        return response

    def display_image(self, image_block: Blob, save_image_file: bool, open_in_browser: bool) -> None:
        """
        Extract image data from image blob, display it, and save it if specified.
        :param image_block: Image data including binary data and file type
        :param save_image_file: Whether or not to save image file on disk
        :param open_in_browser: Whether or not to open the generated image in the web browser
        """

        # Get binary image data
        image_data: bytes = image_block.data

        # Get file type
        mime_type: str = image_block.mime_type
        file_type: str = mime_type.split("/")[-1]

        # Determine file path
        if save_image_file:
            path = Path(f"generated_image.{file_type}")
        else:
            with NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp:
                path = Path(tmp.name)

        # Write file
        path.write_bytes(image_data)

        file_uri = path.absolute().as_uri()
        self.logger.info("Saved video to: %s", file_uri)

        if open_in_browser:
            webbrowser.open(file_uri)
