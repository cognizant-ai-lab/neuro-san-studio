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
from time import perf_counter
from typing import Any
from typing import Dict

from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter
from neuro_san.internals.interfaces.context_type_toolbox_factory import ContextTypeToolboxFactory
from neuro_san.internals.run_context.factory.master_toolbox_factory import MasterToolboxFactory

from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.constants import PROGRESS_HANDLER
from coded_tools.agent_network_editor.constants import TOOLBOX_FACTORY
from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock


class ProgressHandler:
    """
    Common handler for progress during the building of agent networks
    """

    PROGRESS_THROTTLE_SECONDS: float = 5.0

    def __init__(self):
        """
        Constructor
        """
        self.last_progress: float = 0.0

    def should_report(self) -> bool:
        """
        Should the progress be reported?
        """
        now: float = perf_counter()
        report_me: bool = now - self.last_progress > self.PROGRESS_THROTTLE_SECONDS
        if not report_me:
            return False

        self.last_progress = now
        return True

    @staticmethod
    async def report_progress(
        args: dict[str, Any], sly_data: Dict[str, Any], network_definition: dict[str, Any], name: str = None
    ):
        """
        Common handler for progress during the building of agent networks

        :param args: The arguments dictionary for the calling CodedTool
        :param network_definition: The network definition dictionary
        :param name: The name of the agent network. If None, will not be reported in progress.
        """
        if sly_data is not None:
            async with await SlyDataLock.get_lock(sly_data, "progress_handler_lock"):
                progress_handler: ProgressHandler = sly_data.get(PROGRESS_HANDLER)
                if progress_handler is None:
                    progress_handler = ProgressHandler()
                    sly_data[PROGRESS_HANDLER] = progress_handler

                if not progress_handler.should_report():
                    return

        progress_reporter: AgentProgressReporter = args.get("progress_reporter")

        use_key: str = AGENT_NETWORK_DEFINITION
        use_network_definition: dict[str, Any] | list[dict[str, Any]] = network_definition

        agent_progress_style: str = environ.get("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", "internal")
        if agent_progress_style == "connectivity":
            # The idea here is that a multi-user MAUI server can turn on this env variable
            # so that agent network progress is converted to connectivity-style data format
            # that it already knows how to render.  Using the different key name allows the AGENT_PROGRESS
            # dictionary to look just like a ConnectivityResponse from the service.

            # Get a cached toolbox factory so we don't have to read info from a file every time
            toolbox_factory: ContextTypeToolboxFactory = None
            if sly_data is not None:
                toolbox_factory: ContextTypeToolboxFactory = sly_data.get(TOOLBOX_FACTORY)
                if toolbox_factory is None:
                    async with await SlyDataLock.get_lock(sly_data, "toolbox_factory_lock"):
                        toolbox_factory: ContextTypeToolboxFactory = sly_data.get(TOOLBOX_FACTORY)
                        if toolbox_factory is None:
                            # DEF - not sure if this empty dict is good enough
                            empty: Dict[str, Any] = {}
                            toolbox_factory: ContextTypeToolboxFactory = MasterToolboxFactory.create_toolbox_factory(
                                empty
                            )
                            toolbox_factory.load()
                            sly_data[TOOLBOX_FACTORY] = toolbox_factory

            # Do the conversion
            use_key: str = "connectivity_info"
            converter = ConnectivityDictionaryConverter(toolbox_factory=toolbox_factory)
            use_network_definition = converter.from_dict(network_definition)

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
