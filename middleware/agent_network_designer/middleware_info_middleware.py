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

import json
import logging
import os
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

MIDDLEWARE_INFO: str = "middleware_info"
DEFAULT_MIDDLEWARE_INFO_FILE: str = os.path.join("middleware", "middleware_info.hocon")


class MiddlewareInfoMiddleware(AgentMiddleware):
    """
    Middleware that reads the available middleware catalog from a HOCON file and injects it
    into the system prompt before each model call.

    The catalog is loaded once per session and cached in sly_data under the key "middleware_info".
    This allows the LLM to reason about which middleware are available without requiring the
    information to be passed explicitly through the chat stream.
    """

    def __init__(self, sly_data: dict[str, Any]) -> None:
        """
        Initialize middleware info middleware.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    "middleware_info": a catalog of available middleware (populated on first call)
        """
        self.sly_data = sly_data
        self.logger = logging.getLogger(self.__class__.__name__)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """
        Inject the middleware catalog from sly_data (or loaded from file) into the system prompt
        before each model call.

        :param request: Model request containing messages and state
        :param handler: Handler to execute the model call
        :return: Model response from handler
        """
        middleware_info: dict[str, Any] | None = self.sly_data.get(MIDDLEWARE_INFO)

        if middleware_info is None:
            middleware_info_file: str = os.getenv(
                "MIDDLEWARE_INFO_FILE", DEFAULT_MIDDLEWARE_INFO_FILE
            )
            self.logger.debug(
                ">>>>>>>>>>>>>>>>>>>Loading Middleware Info from '%s'>>>>>>>>>>>>>>>>>>>",
                middleware_info_file,
            )
            try:
                hocon = AbstractAsyncConfigRestorer(file_purpose="get_middleware_info", must_exist=True)
                middleware_info = await hocon.async_restore(file_reference=middleware_info_file)
            except FileNotFoundError:
                self.logger.warning(
                    "WARNING: Middleware info file not found: %s. Skipping injection.", middleware_info_file
                )
                return await handler(request)

            # Cache for subsequent calls within the same session
            self.sly_data[MIDDLEWARE_INFO] = middleware_info

        if middleware_info:
            self.logger.debug(
                ">>>>>>>>>>>>>>>>>>>Injecting Middleware Info into System Prompt>>>>>>>>>>>>>>>>>>>"
            )
            info_prompt: str = self.format_middleware_info_prompt(middleware_info)

            system_message: BaseMessage | None = request.system_message
            if system_message is not None:
                original_content: str = system_message.content if isinstance(system_message.content, str) else ""
                system_message = SystemMessage(content=f"{original_content}\n\n{info_prompt}")
            else:
                system_message = SystemMessage(content=info_prompt)

            return await handler(request.override(system_message=system_message))

        return await handler(request)

    def format_middleware_info_prompt(self, middleware_info: dict[str, Any]) -> str:
        """
        Format the middleware catalog as a system prompt section.

        :param middleware_info: The middleware catalog dictionary
        :return: Formatted prompt string
        """
        info_str: str = json.dumps(middleware_info, indent=2)
        return f"## Available Middleware\n\n```json\n{info_str}\n```"
