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

from anthropic import AnthropicError
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage

from neuro_san_studio.coded_tools.utils.byok_api_key import ByokApiKey

# Current-generation default (claude-3-7-sonnet-20250219 is retired); networks override it per
# tool via the "anthropic_model" arg.
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"

# Where a Bring-Your-Own-Key (BYOK) client puts its Anthropic key inside sly_data["llm_config"],
# and the server-side environment variable used when the client did not send one. The names
# match what neuro-san uses for agents' llm_config so one client convention covers both.
ANTHROPIC_API_KEY_NAME = "anthropic_api_key"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"


class AnthropicTool:
    """
    An implementation for invoking Anthropic built-in tools using LangChain's ChatAnthropic.

    Supported tools include (but are not limited to):
        - "code_execution"
        - "web_search"

    Only "code_execution" and "web_search" have been tested.

    See https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
    """

    logger = logging.getLogger(__name__)

    @staticmethod
    def get_api_key(sly_data: dict[str, Any] | None) -> str | None:
        """
        Resolve the Anthropic API key for a tool call.

        The BYOK key in sly_data["llm_config"]["anthropic_api_key"] wins; the ANTHROPIC_API_KEY
        environment variable is the fallback. Shared by every coded tool that talks to Anthropic
        directly so the precedence rule lives in one place.

        :param sly_data: The sly_data dictionary handed to the calling coded tool. May be None.
        :return: The API key to use, or None when neither source provides one.
        """
        return ByokApiKey.resolve(sly_data, ANTHROPIC_API_KEY_NAME, ANTHROPIC_API_KEY_ENV)

    @staticmethod
    async def arun(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        query: str,
        tool_type: str,
        tool_name: str,
        anthropic_model: str | None = DEFAULT_ANTHROPIC_MODEL,
        betas: list[str] | None = None,
        sly_data: dict[str, Any] | None = None,
        **additional_kwargs: dict[str, Any],
    ) -> list[dict[str, Any]] | str:
        """
        Invoke an Anthropic built-in tool through ChatAnthropic and return its content blocks.

        :param query: Request from the user prompt.
        :param tool_type: The versioned type of the built-in Anthropic tool, e.g. "web_search_20250305".
        :param tool_name: The name of the built-in Anthropic tool, e.g. "web_search".
        :param anthropic_model: The Anthropic model to use when calling the tool.
            Defaults to "claude-sonnet-5" if not provided.
        :param betas: Some tools are still in beta and requires this parameter.
        :param sly_data: The sly_data dictionary of the calling coded tool. When it carries a
            BYOK key under llm_config.anthropic_api_key, that key authenticates the call instead
            of the ANTHROPIC_API_KEY environment variable.
        :param additional_kwargs: Additional keyword arguments to pass to the selected tool.
            Refer to https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview

        :return:
            In case of successful execution:
                Tool results
            otherwise:
                a text string an error message in the format:
                "Anthropic Error: <error message>"
        """

        if not anthropic_model:
            anthropic_model = DEFAULT_ANTHROPIC_MODEL

        AnthropicTool.logger.info(">>>>>>>>>> Invoking Anthropic Tool <<<<<<<<<<")
        AnthropicTool.logger.info("Query: %s", query)
        AnthropicTool.logger.info("Anthropic Model: %s", anthropic_model)
        AnthropicTool.logger.info("Built-in Tool Type: %s", tool_type)
        AnthropicTool.logger.info("Built-in Tool Name: %s", tool_name)
        AnthropicTool.logger.info("Additional Keyword Arguments: %s", additional_kwargs)

        try:
            # A BYOK key from sly_data must win over the server's ANTHROPIC_API_KEY, so resolve
            # it here instead of letting ChatAnthropic read the environment on its own. None
            # (neither source has a key) is accepted at construction; the request then fails
            # exactly as it did before this resolution existed.
            api_key: str | None = AnthropicTool.get_api_key(sly_data)

            # Instantiate the chat model using specified model.
            anthropic_llm = ChatAnthropic(model=anthropic_model, api_key=api_key)

            tool: dict[str, Any] = {"type": tool_type, "name": tool_name} | additional_kwargs

            # Invoke with the provided query and tool,
            # "tool_choice" is set to {"type": "any"} to force the model to use tool.
            result: AIMessage = await anthropic_llm.ainvoke(
                query, betas=betas, tools=[tool], tool_choice={"type": "any"}
            )
            content: list[dict[str, Any]] = result.content
            AnthropicTool.logger.info("Result from Anthropic Tool: %s", content)
            return content

        except AnthropicError as anthropic_error:
            AnthropicTool.logger.error("Anthropic Error: %s", anthropic_error)
            return f"Anthropic Error: {anthropic_error}"
