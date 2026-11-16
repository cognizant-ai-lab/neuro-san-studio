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

from neuro_san_studio.agent_network_designer.common.and_logger import AndLogger
from neuro_san_studio.agent_network_designer.common.shared_process_cache import SharedProcessCache

DEFAULT_TOOLBOX_INFO_FILE = os.path.join("neuro_san_studio", "toolbox", "agent_network_designer_toolbox_info.hocon")
logger = AndLogger(logging.getLogger(__name__))


class GetToolbox(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from toolbox info file.

    The file is AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE, or the local default. A multi-user server
    points that variable at agent_network_designer_toolbox_info_multiuser.hocon. A file that defines
    no tools gives an empty toolbox.
    """

    @staticmethod
    def _resolve_toolbox_info_file() -> str:
        """
        Resolve the designer's toolbox info file.

        :return: The AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE env var, or the default when it is
                unset or empty.
        """
        return os.getenv("AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE") or DEFAULT_TOOLBOX_INFO_FILE

    @staticmethod
    def _toolbox_info_fingerprint() -> tuple[str, tuple[int, int] | None]:
        """
        Freshness probe for the shared toolbox info cache (see SharedProcessCache).

        The cached mapping is served only while the resolved path and the file's
        modification_time and size stay the same, so a changed env var or an edited
        file is read again on the next call. The size also catches a rewrite that
        finishes in the same timestamp tick as a read of the half-written file. A
        missing file (None) is read the moment it appears.

        :return: (path, (modification_time_ns, size) or None) tuple.
        """
        toolbox_info_file: str = GetToolbox._resolve_toolbox_info_file()
        return (toolbox_info_file, SharedProcessCache.stat_modification_time_ns_and_size(toolbox_info_file))

    @staticmethod
    def _load_shared_toolbox_info() -> dict[str, str]:
        """
        Loader for the shared toolbox info (runs inside SharedProcessCache).

        Reads and parses the toolbox info file and reduces each entry to its
        description. A file that defines no tools is a valid result, published
        like any other.

        :return: dict mapping tool names to descriptions; empty when the file
                defines no tools.
        :raises FileNotFoundError: When the file does not exist (after logging a
                warning with the resolved path). The cache publishes nothing on a
                raise, so the next call retries and heals the moment the file
                appears.
        :raises ValueError: When the file is malformed. Nothing is published
                then either, so the next call retries.
        """
        toolbox_info_file: str = GetToolbox._resolve_toolbox_info_file()

        # Go fish — once per version of the file.
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
            # A read that caught the file mid-rewrite can also come back empty.
            # The finished rewrite changes the file's size or modification_time,
            # so the next call reads it again.
            logger.info("Toolbox info file %s defines no tools.", toolbox_info_file)
        return tools

    # Process-wide cache of the {tool_name: description} mapping parsed from
    # the toolbox info file. The fingerprint (path, modification_time and size,
    # see _toolbox_info_fingerprint) serves the mapping only while the file is
    # unchanged, so an edit is read on the next call without a restart.
    # Locking, publish ordering, and the async once-gate live in
    # SharedProcessCache; access goes through the class by name (not cls) so
    # a hypothetical subclass shares the one cache instead of splitting it.
    _shared_toolbox_info_cache: SharedProcessCache[dict[str, str]] = SharedProcessCache(
        loader=_load_shared_toolbox_info, fingerprint=_toolbox_info_fingerprint
    )

    @classmethod
    def clear_shared_toolbox_info_for_testing(cls) -> None:
        """
        Reset the process-wide toolbox info cache. For test isolation only.

        Production code must never call this: the fingerprint already reloads
        the file when it changes. Tests call it (via tests/conftest.py) so
        toolbox info loaded under one test's
        AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE state cannot leak into later
        tests. Living here rather than in conftest keeps all the singleton
        policy in this one class.
        """
        GetToolbox._shared_toolbox_info_cache.clear_for_testing()

    @staticmethod
    async def get_toolbox_info() -> dict[str, str]:
        """
        Read toolbox info from the process-wide cache, loading it from the file
        on the first call and again whenever the file changes. A load runs off
        the event loop and is shared by concurrent callers.

        :return: dict mapping tool names to descriptions; empty if the toolbox
                info file defines no tools, or if it does not exist (retried on
                the next call, never cached). The returned dict is a copy, so
                callers may mutate it without corrupting the shared cache.
        :raises ValueError: When the toolbox info file is malformed.
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
                an empty dictionary if the toolbox info file defines no tools
                or does not exist.
        :raises ValueError: When the toolbox info file is malformed.
        """
        return await self.get_toolbox_info()
