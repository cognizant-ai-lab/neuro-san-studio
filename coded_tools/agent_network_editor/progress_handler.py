# Copyright © 2025 Cognizant Technology Solutions Corp, www.cognizant.com.
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

from typing import Any

from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME


class ProgressHandler:
    """
    Common handler for progress reporting during the building of agent networks
    """

    @staticmethod
    async def report_progress(args: dict[str, Any], network_definition: dict[str, Any], name: str = None) -> None:
        """
        Common handler for progress reporting during the building of agent networks

        :param args: The arguments dictionary for the calling CodedTool
        :param network_definition: The network definition dictionary
        :param name: The name of the agent network. If None, will not be reported in progress.
        """
        progress_reporter: AgentProgressReporter = args.get("progress_reporter")
        progress: dict[str, Any] = {
            # Agent network definition with an added agent
            AGENT_NETWORK_DEFINITION: network_definition
        }

        # Optionally add agent network name
        if name:
            progress[AGENT_NETWORK_NAME] = name

        await progress_reporter.async_report_progress(progress)
