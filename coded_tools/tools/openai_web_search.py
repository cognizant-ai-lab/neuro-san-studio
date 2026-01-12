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

from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.openai_tool import OpenAITool


class OpenAIWebSearch(CodedTool):
    """
    A CodedTool implementation for invoking OpenAI web search tool using LangChain's ChatOpenAI.

    See https://platform.openai.com/docs/guides/tools?api-mode=responses
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
        # See https://platform.openai.com/docs/guides/tools-web-search?api-mode=responses
        additional_kwargs: dict[str, Any] = args.get("additional_kwargs", {})

        return await OpenAITool.arun(query, "web_search_preview", openai_model, **additional_kwargs)
