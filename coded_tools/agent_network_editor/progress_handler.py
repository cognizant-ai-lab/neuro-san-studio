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

from os import environ
from typing import Any

from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter

# Reaching into neuro_san internals because we expect to know the gory details here because
# we are building agent networks.  This is not normally a recommended practice.
from neuro_san.internals.chat.connectivity_reporter import ConnectivityReporter
from neuro_san.internals.run_context.interfaces.agent_network_inspector import AgentNetworkInspector

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.designer_network_inspector import DesignerNetworkInspector


# pylint: disable=too-few-public-methods
class ProgressHandler:
    """
    Common handler for progress progress during the building of agent networks
    """

    @staticmethod
    async def report_progress(args: dict[str, Any], network_definition: dict[str, Any], name: str = None):
        """
        Common handler for progress progress during the building of agent networks

        :param args: The arguments dictionary for the calling CodedTool
        :param network_definition: The network definition dictionary
        :param name: The name of the agent network. If None, will not be reported in progress.
        """
        progress_reporter: AgentProgressReporter = args.get("progress_reporter")

        use_key: str = AGENT_NETWORK_DEFINITION
        use_network_definition: dict[str, Any] = network_definition

        agent_progress_style: str = environ.get("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", "internal")
        if agent_progress_style == "connectivity":
            # The idea here is that a multi-user MAUI server can turn on this env variable
            # so that agent network progress progress is converted to connectivity-style data format
            # that it already knows how to render.  Using the different key name allows the AGENT_PROGRESS
            # dictionary to look just like a ConnectivityResponse from the service.
            use_key: str = "connectivity_info"
            use_network_definition = ProgressHandler._convert_to_connectivity_style(network_definition)

        elif agent_progress_style == "internal":
            # Report the internal structure used by Agent Network Designer and pals.
            # This is what was used in the first iterations with nsflow.
            use_key: str = AGENT_NETWORK_DEFINITION
            use_network_definition: dict[str, Any] = network_definition

        progress: dict[str, Any] = {
            # Agent network definition with an added agent
            use_key: use_network_definition
        }

        # Optionally add agent network name
        if name:
            progress[AGENT_NETWORK_NAME] = name

        await progress_reporter.async_report_progress(progress)

    @staticmethod
    def _convert_to_connectivity_style(network_definition: dict[str, Any]) -> list[dict[str, Any]]:

        connectivity: list[dict[str, Any]] = []

        inspector: AgentNetworkInspector = DesignerNetworkInspector(network_definition)

        reporter: ConnectivityReporter = ConnectivityReporter(inspector)
        connectivity = reporter.report_network_connectivity()

        return connectivity
