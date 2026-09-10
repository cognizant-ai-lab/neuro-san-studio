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

from neuro_san_studio.coded_tools.utils.byok_api_key import ByokApiKey

DEFAULT_OPENAI_MODEL = "gpt-4o-2024-08-06"

# Where a Bring-Your-Own-Key (BYOK) client puts its OpenAI key inside sly_data["llm_config"],
# and the server-side environment variable used when the client did not send one. The names
# match what neuro-san uses for agents' llm_config so one client convention covers both.
OPENAI_API_KEY_NAME = "openai_api_key"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


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
    def get_api_key(sly_data: dict[str, Any] | None) -> str | None:
        """
        Resolve the OpenAI API key for a tool call.

        The BYOK key in sly_data["llm_config"]["openai_api_key"] wins; the OPENAI_API_KEY
        environment variable is the fallback. Shared by every coded tool that talks to OpenAI
        directly so the precedence rule lives in one place.

        :param sly_data: The sly_data dictionary handed to the calling coded tool. May be None.
        :return: The API key to use, or None when neither source provides one.
        """
        return ByokApiKey.resolve(sly_data, OPENAI_API_KEY_NAME, OPENAI_API_KEY_ENV)

    @staticmethod
    async def arun(
        query: str,
        builtin_tool: str,
        openai_model: str | None = DEFAULT_OPENAI_MODEL,
        sly_data: dict[str, Any] | None = None,
        **additional_kwargs: dict[str, Any],
    ) -> list[dict[str, Any]] | str:
        """
        Invoke an OpenAI built-in tool through ChatOpenAI and return its content blocks.

        :param query: Request from the user prompt.
        :param builtin_tool: The name of the built-in OpenAI tool to invoke.
        :param openai_model: The OpenAI model to use when calling the tool.
            Defaults to "gpt-4o-2024-08-06" if not provided.
        :param sly_data: The sly_data dictionary of the calling coded tool. When it carries a
            BYOK key under llm_config.openai_api_key, that key authenticates the call instead
            of the OPENAI_API_KEY environment variable.
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
            # A BYOK key from sly_data must win over the server's OPENAI_API_KEY, so resolve
            # it here instead of letting ChatOpenAI read the environment on its own. When
            # neither source has a key this is None and ChatOpenAI raises its usual
            # missing-credentials OpenAIError, which the except below turns into the error string.
            api_key: str | None = OpenAITool.get_api_key(sly_data)

            # Instantiate the chat model using specified model.
            # The "output_version" key format output from built-in tool invocations into
            # the message’s content field, rather than additional_kwargs.
            openai_llm = ChatOpenAI(model=openai_model, output_version="responses/v1", api_key=api_key)
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
