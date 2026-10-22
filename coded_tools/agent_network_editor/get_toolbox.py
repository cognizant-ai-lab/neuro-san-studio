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
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.run_context.langchain.toolbox.toolbox_info_restorer import ToolboxInfoRestorer

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache

DEFAULT_TOOLBOX_INFO_FILE = os.path.join("neuro_san_studio", "toolbox", "agent_network_designer_toolbox_info.hocon")
logger = AndLogger(logging.getLogger(__name__))


class GetToolbox(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from toolbox info file
    """

    @staticmethod
    def _load_shared_toolbox_info() -> dict[str, str]:
        """
        Loader for the shared toolbox info (runs inside SharedProcessCache).

        Resolves the toolbox info file — the AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE
        env var or the default — reads and parses it, and reduces each entry to its
        description.

        :return: dict mapping tool names to descriptions; never empty.
        :raise FileNotFoundError: When the file does not exist, or when it
                yields no tools at all (after logging a warning with the
                resolved path). The cache publishes nothing on a raise, so a
                transient gap — a deploy replacing the file, a wrong-CWD
                launch, a read that comes back empty — cannot pin an empty
                toolbox for the life of the process: the next call retries
                and heals the moment the file reads correctly. A malformed
                file raises out of the parse, likewise unpublished.
        """
        # Check for toolbox info file in env var
        toolbox_info_file: str = os.getenv("AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE")
        if not toolbox_info_file:
            # Use a default if no value specified
            toolbox_info_file = DEFAULT_TOOLBOX_INFO_FILE

        # Go fish — once per process once it succeeds.
        logger.info(">>>>>>>>>>>>>>>>>>>Getting Tool Definition from Toolbox>>>>>>>>>>>>>>>>>>>")
        logger.info("Toolbox info file: %s", toolbox_info_file)

        try:
            raw_tools: dict[str, Any] = ToolboxInfoRestorer().restore(toolbox_info_file)
        except FileNotFoundError:
            # The warning lives here because only the loader knows the resolved
            # path; the callers' policy (return empty for this call) lives with
            # them. The recurring warning is the operator's signal.
            logger.warning("Error: Failed to load toolbox info from %s.", toolbox_info_file)
            raise

        logger.info("Successfully loaded the following toolbox: %s", str(raw_tools))

        # Keep only each tool's description.
        tools: dict[str, str] = {}
        for tool_name, tool_info in raw_tools.items():
            tools[tool_name] = tool_info.get("description", "")

        if not tools:
            # The designer's toolbox file always defines tools, so an empty
            # mapping only ever means the read went wrong — observed in the
            # wild as a one-off restore() returning {} that this cache (no
            # fingerprint) then pinned until a server restart. Raising
            # instead of returning keeps the empty result unpublished: this
            # call degrades to an empty toolbox, and the next call retries
            # and heals. FileNotFoundError so callers' existing
            # missing-file policy applies unchanged.
            logger.warning("Toolbox info from %s came back empty; treating as a failed load.", toolbox_info_file)
            raise FileNotFoundError(f"Toolbox info file {toolbox_info_file} yielded no tools")
        return tools

    # Process-wide cache of the {tool_name: description} mapping parsed from
    # the toolbox info file. With no fingerprint the mapping is
    # deliberately never refreshed once loaded, so picking up an edited
    # toolbox info file requires a process restart — the same trade-off as
    # ConnectivityDictionaryConverter's shared ToolboxFactory. Previously the
    # cache lived in sly_data, so a server handling N concurrent conversations
    # re-parsed the same HOCON N times, on the event loop. Locking, publish
    # ordering, and the async once-gate live in SharedProcessCache; access
    # goes through the class by name (not cls) so a hypothetical subclass
    # shares the one cache instead of splitting it.
    _shared_toolbox_info_cache: SharedProcessCache[dict[str, str]] = SharedProcessCache(
        loader=_load_shared_toolbox_info
    )

    @classmethod
    def clear_shared_toolbox_info_for_testing(cls):
        """
        Reset the process-wide toolbox info cache. For test isolation only.

        Production code must never call this: the cache is deliberately
        load-once-per-process (see the class comment above). Tests call it
        (via tests/conftest.py) so toolbox info loaded under one test's
        AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE state cannot leak into later
        tests. Living here rather than in conftest keeps all the singleton
        policy in this one class.
        """
        GetToolbox._shared_toolbox_info_cache.clear_for_testing()

    @staticmethod
    async def get_toolbox_info() -> dict[str, str]:
        """
        Read toolbox info from the process-wide cache, loading it from a file
        on the first call in the process. The cold load runs off the event
        loop and is shared by concurrent cold callers.

        :return: dict mapping tool names to descriptions; empty if the toolbox
                info file does not exist (retried on the next call, never
                cached). A malformed file raises. The returned dict is a copy,
                so callers may mutate it without corrupting the shared cache.
        """
        try:
            tools: dict[str, str] = await GetToolbox._shared_toolbox_info_cache.aget()
        except FileNotFoundError:
            # Already logged by the loader with the resolved path.
            return {}
        return dict(tools)

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    None

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
                the tool definition from toolbox as a dictionary.
            otherwise:
                an empty dictionary if the toolbox info file does not exist;
                a malformed file raises.
        """
        return await self.get_toolbox_info()
