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
import webbrowser
from base64 import b64decode
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.openai_tool import OpenAITool


class OpenAIImageGeneration(CodedTool):
    """
    A CodedTool implementation for invoking OpenAI image generation tool using LangChain's ChatOpenAI.

    See https://platform.openai.com/docs/guides/tools?api-mode=responses
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
                        Note that the model may revise the prompt for the user.
                        The revised prompt can be seen it the log.
                - from user
                    - "openai_model" (str): OpenAI model to call the tool. Default to gpt-4o-2024-08-06.
                    - "additional_kwargs" (dict): Any additional arguments for the tool.

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

        # Get query from args
        query: str = args.get("query")
        if not query:
            return "Error: No query provided."

        # User-defined arguments

        # The OpenAI model to use when calling the tool.
        openai_model: str = args.get("openai_model")

        # Additional keyword arguments to pass to the selected tool.
        # See https://platform.openai.com/docs/guides/tools-image-generation
        additional_kwargs: dict[str, Any] = args.get("additional_kwargs", {})
        save_image_file: bool = args.get("save_image_file", False)

        # This should be a list of content blocks if success and a string of error text otherwise.
        content_blocks: list[dict[str, Any]] | str = await OpenAITool.arun(
            query, "image_generation", openai_model, **additional_kwargs
        )

        if isinstance(content_blocks, str):
            # Return an error message if content_blocks is a string
            return content_blocks

        # Extract text and image blocks
        text_block = next((block for block in content_blocks if block.get("type") == "text"), {})
        image_block = next((block for block in content_blocks if block.get("type") == "image"), {})

        if image_block:
            self.display_image(image_block, save_image_file)

        return text_block.get("text", "")

    def display_image(self, image_block: dict[str, Any], save_image_file: bool = False) -> None:
        """
        Extract image from image block, display it, and save it if specified.
        :param image_block: Image data including base64 data and file type
        :param save_image_file: Whether or not to save image file on disk
        """

        base64_string: str = image_block.get("base64")
        if not base64_string:
            return

        # Decode base64 to binary image data
        image_data: bytes = b64decode(base64_string)

        # Get file type
        mime_type: str = image_block.get("mime_type", "image/png")
        file_type: str = mime_type.split("/")[-1]

        # Log revised prompt
        self.logger.info(
            "The image was generated using the following revised prompt: %s",
            image_block.get("extra", {}).get("revised_prompt"),
        )

        # Save permanent file if requested
        if save_image_file:
            image_id: str = image_block.get("id", "image")
            file_path = Path(f"{image_id}.{file_type}")
            file_path.write_bytes(image_data)
            # Log file path
            self.logger.info("Image saved to: %s", file_path.absolute())

        # Create temp file and open in browser
        with NamedTemporaryFile("wb", delete=False, suffix=f".{file_type}") as file:
            file.write(image_data)
            temp_path = file.name

        webbrowser.open(f"file://{temp_path}")
