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

"""
Old import path for the designer's editor tools and their helpers. A network or module that still names a class here
gets the class from its new module, with a deprecation warning logged the first time each name is used.
"""

from typing import Any
from typing import Callable
from typing import Type

from leaf_common.resolution.deprecation_redirect import DeprecationRedirect

# Each old and new class name stays whole on one line, so that it can be searched for.
_DEPRECATION_REDIRECT = DeprecationRedirect(
    __name__,
    {
        "coded_tools.agent_network_editor.add_agent.AddAgent": "neuro_san_studio.agent_network_designer.tools.add_agent.AddAgent",  # noqa: E501
        "coded_tools.agent_network_editor.agent_name_guard.AgentNameGuard": "neuro_san_studio.agent_network_designer.common.agent_name_guard.AgentNameGuard",  # noqa: E501
        "coded_tools.agent_network_editor.and_logger.AndLogger": "neuro_san_studio.agent_network_designer.common.and_logger.AndLogger",  # noqa: E501
        "coded_tools.agent_network_editor.connectivity_dictionary_converter.ConnectivityDictionaryConverter": "neuro_san_studio.agent_network_designer.tools.connectivity_dictionary_converter.ConnectivityDictionaryConverter",  # noqa: E501
        "coded_tools.agent_network_editor.create_network.CreateNetwork": "neuro_san_studio.agent_network_designer.tools.create_network.CreateNetwork",  # noqa: E501
        "coded_tools.agent_network_editor.designer_network_inspector.DesignerNetworkInspector": "neuro_san_studio.agent_network_designer.tools.designer_network_inspector.DesignerNetworkInspector",  # noqa: E501
        "coded_tools.agent_network_editor.get_mcp_tool.GetMcpTool": "neuro_san_studio.agent_network_designer.tools.get_mcp_tool.GetMcpTool",  # noqa: E501
        "coded_tools.agent_network_editor.get_subnetwork.GetSubnetwork": "neuro_san_studio.agent_network_designer.tools.get_subnetwork.GetSubnetwork",  # noqa: E501
        "coded_tools.agent_network_editor.get_toolbox.GetToolbox": "neuro_san_studio.agent_network_designer.tools.get_toolbox.GetToolbox",  # noqa: E501
        "coded_tools.agent_network_editor.globals.ProcessGlobals": "neuro_san_studio.agent_network_designer.common.globals.ProcessGlobals",  # noqa: E501
        "coded_tools.agent_network_editor.mcp_header_hygiene.McpHeaderHygiene": "neuro_san_studio.agent_network_designer.tools.mcp_header_hygiene.McpHeaderHygiene",  # noqa: E501
        "coded_tools.agent_network_editor.mcp_servers_load.McpServersLoad": "neuro_san_studio.agent_network_designer.tools.mcp_servers_load.McpServersLoad",  # noqa: E501
        "coded_tools.agent_network_editor.progress_handler.ProgressHandler": "neuro_san_studio.agent_network_designer.common.progress_handler.ProgressHandler",  # noqa: E501
        "coded_tools.agent_network_editor.remove_agent.RemoveAgent": "neuro_san_studio.agent_network_designer.tools.remove_agent.RemoveAgent",  # noqa: E501
        "coded_tools.agent_network_editor.shared_process_cache.SharedProcessCache": "neuro_san_studio.agent_network_designer.common.shared_process_cache.SharedProcessCache",  # noqa: E501
        "coded_tools.agent_network_editor.sly_data_lock.SlyDataLock": "neuro_san_studio.utils.sly_data_lock.SlyDataLock",  # noqa: E501
        "coded_tools.agent_network_editor.update_agent.UpdateAgent": "neuro_san_studio.agent_network_designer.tools.update_agent.UpdateAgent",  # noqa: E501
    },
)

# Python calls a package's __getattr__ for a name the package does not define, which is how an old class name
# reaches the redirect.
__getattr__: Callable[[str], Type[Any]] = _DEPRECATION_REDIRECT.redirect_class
