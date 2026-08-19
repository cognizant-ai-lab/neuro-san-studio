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
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer
from pyparsing.exceptions import ParseException

from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache

# Relative to the repository root, like every other default path in this project
# (the server is expected to be started from the top of the repo — see run.py).
DEFAULT_MIDDLEWARE_INFO_FILE: str = str(Path("middleware", "agent_network_designer", "middleware_info.hocon"))


class MiddlewareInfoMiddleware(AgentMiddleware):
    """
    Middleware that reads the available middleware catalog from a HOCON file and injects it
    into the system prompt before each model call, so the LLM can reason about which
    middleware are available without the information passing through the chat stream.

    The catalog is loaded once per process and shared via SharedProcessCache (see
    ProcessGlobals entry 8); an edited catalog file — or a changed MIDDLEWARE_INFO_FILE —
    is picked up on the next call through the path + modification-time fingerprint. The
    previous per-session sly_data cache never actually survived between /middleware_manager
    invocations (each call starts with fresh downstream sly_data), so it cold-parsed the
    file every time.

    Unlike ExternalAgentsMiddleware — a security gate that fails closed — this middleware
    only enriches the prompt, so a catalog that cannot be loaded degrades to a warning and
    an uninjected prompt rather than failing the model call.
    """

    @staticmethod
    def _load_middleware_info() -> dict[str, Any]:
        """
        SharedProcessCache loader: read and parse the middleware catalog.

        Runs in a worker thread (reached through aget()), so the blocking file read
        and HOCON parse stay off the event loop.

        :return: The parsed catalog dictionary ({} for an empty file — loaders must
                never return None, the cache's miss sentinel).
        :raises OSError, ValueError: when the catalog cannot be read or parsed
                (current neuro-san re-wraps parse failures into ValueError). Nothing
                is published on a raise, so the next call retries; awrap_model_call()
                catches these and skips injection.
        """
        middleware_info_file: str = os.getenv("MIDDLEWARE_INFO_FILE", DEFAULT_MIDDLEWARE_INFO_FILE)
        if not middleware_info_file:
            # An empty env var (MIDDLEWARE_INFO_FILE="") makes restore() return None
            # before its must_exist check; surface it as a load failure so the
            # caller's warn-and-skip path reports it instead of silently injecting
            # nothing forever.
            raise ValueError("MIDDLEWARE_INFO_FILE is set to an empty string")
        restorer = AbstractAsyncConfigRestorer(file_purpose="get_middleware_info", must_exist=True)
        middleware_info: dict[str, Any] = restorer.restore(file_reference=middleware_info_file)
        return middleware_info or {}

    @staticmethod
    def _info_fingerprint() -> tuple[str, int | None]:
        """
        SharedProcessCache fingerprint: the resolved catalog path plus its
        modification time, so both an edited file and a changed MIDDLEWARE_INFO_FILE
        register as a miss and trigger a reload. Cheap and never raises, per the
        fingerprint contract.
        """
        middleware_info_file: str = os.getenv("MIDDLEWARE_INFO_FILE", DEFAULT_MIDDLEWARE_INFO_FILE)
        return middleware_info_file, SharedProcessCache.stat_modification_time_ns(middleware_info_file)

    # Process-wide cache of the parsed catalog (see ProcessGlobals entry 8). Access
    # goes through the class by name (not cls) so a hypothetical subclass shares the
    # one cache instead of splitting it.
    _shared_info_cache: SharedProcessCache[dict[str, Any]] = SharedProcessCache(
        loader=_load_middleware_info,
        fingerprint=_info_fingerprint,
    )

    def __init__(self, sly_data: dict[str, Any]) -> None:
        """
        Initialize middleware info middleware.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.
                No longer used by this middleware (the catalog moved to a
                process-wide cache); the parameter stays because MiddlewareFactory
                wires it in per the "sly_data": true arg in
                registries/middleware_manager.hocon.
        """
        self.sly_data = sly_data
        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def clear_shared_info_for_testing(cls):
        """
        Reset the process-wide catalog cache. For test isolation only.

        Production code must never call this: the cache is deliberately
        load-once-per-process with fingerprint-based refresh. Tests call it (via
        tests/conftest.py's ProcessGlobals reset) so a catalog loaded under one
        test's MIDDLEWARE_INFO_FILE state cannot leak into later tests.
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
            middleware_info: dict[str, Any] = await MiddlewareInfoMiddleware._shared_info_cache.aget()
        except (OSError, ValueError, ParseException) as error:
            # OSError covers FileNotFoundError / PermissionError / IsADirectoryError;
            # ValueError is raised for unsupported file extensions and is what current
            # neuro-san re-wraps HOCON/JSON parse failures into; ParseException stays
            # in the tuple defensively for neuro-san versions that surface pyhocon's
            # exception directly. This catalog only enriches the prompt, so degrade
            # gracefully instead of failing the model call; the load is retried on
            # the next call.
            self.logger.warning("Middleware info catalog could not be loaded (%s). Skipping injection.", error)
            return await handler(request)

        if middleware_info:
            self.logger.debug(">>>>>>>>>>>>>>>>>>>Injecting Middleware Info into System Prompt>>>>>>>>>>>>>>>>>>>")
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
