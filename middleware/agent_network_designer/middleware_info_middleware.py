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
from pathlib import Path
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

from coded_tools.agent_network_editor.and_logger import AndLogger
from middleware.agent_network_designer.catalog_load_error import CatalogLoadError
from middleware.agent_network_designer.hocon_catalog_cache import HoconCatalogCache

# Relative to the working directory, matching the repo/scaffold layout when the
# server is started from the top of the repository or of an `ns init` project.
DEFAULT_MIDDLEWARE_INFO_FILE: str = str(Path("middleware", "agent_network_designer", "middleware_info.hocon"))
# The copy of the catalog that ships right next to this module — the fallback when
# the working directory has no repo/project-layout copy (e.g. `ns run` inside a
# scaffolded project, or an installed wheel).
BUNDLED_MIDDLEWARE_INFO_FILE: str = str(Path(__file__).with_name("middleware_info.hocon"))


class MiddlewareInfoMiddleware(AgentMiddleware):
    """
    Middleware that reads the available middleware catalog from a HOCON file and injects it
    into the system prompt before each model call, so the LLM can reason about which
    middleware are available without the information passing through the chat stream.

    The catalog is loaded once per process through HoconCatalogCache (see ProcessGlobals
    entry 7), which also handles path resolution (env var, working-directory layout, the
    copy bundled beside this module) and freshness; the prompt section is rendered once
    per load rather than once per model call.

    This middleware only enriches the prompt — it is not a security gate that must
    fail closed — so a catalog that cannot be loaded degrades to a warning and an
    uninjected prompt rather than failing the model call.
    """

    @staticmethod
    def _format_middleware_info_prompt(middleware_info: dict[str, Any]) -> str:
        """
        Format the middleware catalog as a system prompt section.

        Run once per catalog load (via the cache's transform), not once per model
        call — the catalog is immutable per fingerprint, so the rendered section is
        a pure function of the file.

        :param middleware_info: The middleware catalog dictionary
        :return: Formatted prompt string
        """
        info_str: str = json.dumps(middleware_info, indent=2)
        return f"## Available Middleware\n\n```json\n{info_str}\n```"

    # Process-wide cache of (catalog, rendered prompt section) — see ProcessGlobals
    # entry 7. Access goes through the class by name (not cls) so a hypothetical
    # subclass shares the one cache instead of splitting it. The transform lambda
    # runs at load time, well after this class body finishes executing, so its
    # by-name reference to the class resolves fine.
    _shared_info_cache: HoconCatalogCache = HoconCatalogCache(
        env_var="AGENT_NETWORK_DESIGNER_MIDDLEWARE_INFO_FILE",
        default_file=DEFAULT_MIDDLEWARE_INFO_FILE,
        bundled_file=BUNDLED_MIDDLEWARE_INFO_FILE,
        file_purpose="get_middleware_info",
        empty_effect="no middleware will be offered to the LLM",
        transform=lambda info: (info, MiddlewareInfoMiddleware._format_middleware_info_prompt(info)),
    )

    def __init__(self) -> None:
        self.logger = AndLogger(logging.getLogger(self.__class__.__name__))

    @classmethod
    def clear_shared_info_for_testing(cls):
        """
        Reset the process-wide catalog cache. For test isolation only.

        Production code must never call this: the cache is deliberately
        load-once-per-process with fingerprint-based refresh. Tests call it (via
        tests/conftest.py's ProcessGlobals reset) so a catalog loaded under one
        test's AGENT_NETWORK_DESIGNER_MIDDLEWARE_INFO_FILE state cannot leak into later tests.
        """
        MiddlewareInfoMiddleware._shared_info_cache.clear_for_testing()

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """
        Inject the middleware catalog into the system prompt before each model call.

        :param request: Model request containing messages and state
        :param handler: Handler to execute the model call
        :return: Model response from handler
        """
        try:
            middleware_info, info_prompt = await MiddlewareInfoMiddleware._shared_info_cache.aget()
        except CatalogLoadError as error:
            # This catalog only enriches the prompt, so degrade gracefully instead
            # of failing the model call; the load is retried on the next call. The
            # detailed message stays server-side — this warning never reaches the
            # client.
            self.logger.warning("Middleware info catalog could not be loaded (%s). Skipping injection.", error)
            return await handler(request)

        if middleware_info:
            self.logger.debug(">>>>>>>>>>>>>>>>>>>Injecting Middleware Info into System Prompt>>>>>>>>>>>>>>>>>>>")
            system_message: BaseMessage | None = request.system_message
            if system_message is not None:
                original_content: str = system_message.content if isinstance(system_message.content, str) else ""
                system_message = SystemMessage(content=f"{original_content}\n\n{info_prompt}")
            else:
                system_message = SystemMessage(content=info_prompt)

            return await handler(request.override(system_message=system_message))

        return await handler(request)
