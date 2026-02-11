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
from typing import Any

from anthropic import Anthropic
from anthropic._response import BinaryAPIResponse
from anthropic.types.beta.file_metadata import FileMetadata
from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.anthropic_tool import AnthropicTool

CODE_EXECUTION_TOOL_TYPE = "code_execution_20250522"
CODE_EXECUTION_BETA = "code-execution-2025-05-22"


class AnthropicCodeExecution(CodedTool):
    """
    A CodedTool implementation for invoking Anthropic code execution tool using LangChain's ChatAnthopic.

    See https://python.langchain.com/docs/integrations/chat/anthropic/#code-execution
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> list[dict[str, Any]] | str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent or user. This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                - from calling agent
                    - "query" (str): Request from the user prompt.
                - from user
                    - "anthropic_model" (str): Anthropic model to call the tool. Default to claude-3-7-sonnet-20250219.
                    - "save_file" (bool): Whether or not to save generated files.
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

        # The Anthropic model to use when calling the tool.
        anthropic_model: str = args.get("anthropic_model")

        save_file: bool = args.get("save_file", False)

        # Additional keyword arguments to pass to the selected tool.
        # See https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/code-execution-tool
        additional_kwargs: dict[str, Any] = args.get("additional_kwargs", {})

        content: list[dict[str, Any]] = await AnthropicTool.arun(
            query=query,
            tool_type=CODE_EXECUTION_TOOL_TYPE,
            tool_name="code_execution",
            anthropic_model=anthropic_model,
            betas=[CODE_EXECUTION_BETA],
            **additional_kwargs
        )

        # If there are generated files and user wants to save them
        file_ids: list[str] = self.extract_file_ids(content)
        if file_ids and save_file:
            self.save_file(file_ids)

        return content

    def extract_file_ids(self, content: list[dict[str, Any]]) -> list[str]:
        """
        Extract file IDs from the response content

        :param content: Content of the response that may contain the file ids.

        :return: List of file ids.
        """
        file_ids: list[str] = []
        for item in content:
            if item.get("type") == "code_execution_tool_result":
                content_item: dict[str, Any] = item.get("content")
                content: list[dict[str, str]] = content_item.get("content")
                if content:
                    for file in content:
                        file_ids.append(file.get("file_id"))
        return file_ids

    def save_file(self, file_ids: list[str]):
        """
        Save the file on disk.

        :param file_ids: ID of the files to save.
        """
        # Initialize the client
        client = Anthropic()

        for file_id in file_ids:
            # Get the file name e.g. output.png
            file_metadata: FileMetadata = client.beta.files.retrieve_metadata(file_id)
            filename: str = file_metadata.filename

            # Download from Anthropic container and save the file on disk
            file_content: BinaryAPIResponse = client.beta.files.download(file_id)
            file_content.write_to_file(filename)
            logging.info("Downloaded: %s", filename)

            # Creates file:// URL and open it
            full_path = os.path.abspath(filename)
            file_url = Path(full_path).as_uri()
            # Use webbrowser because it works on all platforms
            webbrowser.open(file_url)
