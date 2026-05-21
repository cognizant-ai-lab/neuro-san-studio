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
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from openai import OpenAIError

DEFAULT_OPENAI_MODEL = "gpt-4o-2024-08-06"


# pylint: disable=too-few-public-methods
class OpenAITool:
    """
    An implementation for invoking OpenAI built-in tools using LangChain's ChatOpenAI.

    Supported tools include (but are not limited to):
        - "code_interpreter"
        - "web_search_preview"
        - "file_search"
        - "image_generation"
        - "mcp"

    Only "code_interpreter" and "web_search_preview" have been tested.

    See https://platform.openai.com/docs/guides/tools?api-mode=responses
    """

    logger = logging.getLogger(__name__)

    @staticmethod
    async def arun(
        query: str,
        builtin_tool: str,
        openai_model: str | None = DEFAULT_OPENAI_MODEL,
        **additional_kwargs: dict[str, Any],
    ) -> list[dict[str, Any]] | str:
        """
        :param query: Request from the user prompt.
        :param builtin_tool: The name of the built-in OpenAI tool to invoke.
        :param openai_model: The OpenAI model to use when calling the tool.
            Defaults to "gpt-4o-2024-08-06" if not provided.
        :param additional_kwargs: Additional keyword arguments to pass to the selected tool.
            Tool-specific requirements:
                - "web_search_preview": no additional kwargs needed.
                - "code_interpreter": requires "container" to be set.
            Refer to https://python.langchain.com/docs/integrations/chat/openai/#responses-api

        :return:
            In case of successful execution:
                Tool results
            otherwise:
                a text string an error message in the format:
                "OpenAI Error: <error message>"
        """

        if not openai_model:
            openai_model = DEFAULT_OPENAI_MODEL

        OpenAITool.logger.info(">>>>>>>>>> Invoking OpenAI Tool <<<<<<<<<<")
        OpenAITool.logger.info("Query: %s", query)
        OpenAITool.logger.info("OpenAI Model: %s", openai_model)
        OpenAITool.logger.info("Built-in Tool: %s", builtin_tool)
        OpenAITool.logger.info("Additional Keyword Arguments: %s", additional_kwargs)

        try:
            # Instantiate the chat model using specified model.
            # The "output_version" key format output from built-in tool invocations into
            # the message’s content field, rather than additional_kwargs.
            openai_llm = ChatOpenAI(model=openai_model, output_version="responses/v1")
            tool: dict[str, Any] = {"type": builtin_tool} | additional_kwargs

            # Invoke with the provided query and tool,
            # "tool_choice" is set to "required" to force the model to use tool.
            result: AIMessage = await openai_llm.ainvoke(query, tools=[tool], tool_choice="required")
            content: list[dict[str, Any]] = result.content_blocks
            OpenAITool.logger.info("Result from OpenAI Tool: %s", content)
            return content

        except OpenAIError as openai_error:
            OpenAITool.logger.error("OpenAI Error: %s", openai_error)
            return f"OpenAI Error: {openai_error}"
