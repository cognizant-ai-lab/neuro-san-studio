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
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)


class AccountantSly(CodedTool):
    """
    A tool that updates a running cost each time it is called.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the passed running cost each time it's called.
        :param args: An empty dictionary (not used)

        :param sly_data: A dictionary containing parameters that should be kept out of the chat stream.
                         Keys expected for this implementation are:
                         - "running_cost": The current running cost.

        :return: A dictionary containing:
                 "running_cost": the updated running cost.
                 IMPORTANT: Also UPDATES the sly_data dictionary with the new running cost.
        """
        tool_name = self.__class__.__name__
        logger.debug("========== Calling %s ==========", tool_name)
        logger.debug("args: %s", args)
        # Parse the sly data
        # NOTE: sly_data may contain secrets - never log it
        # Get the current running cost. If not present, start at 0.0
        running_cost: float = float(sly_data.get("running_cost", 0.0))

        # Increment the running cost
        updated_running_cost: float = running_cost + 3.0

        # Update the sly_data
        sly_data["running_cost"] = updated_running_cost

        tool_response = {"running_cost": updated_running_cost}
        logger.debug("-----------------------")
        logger.debug("%s response: %s", tool_name, tool_response)
        logger.debug("========== Done with %s ==========", tool_name)
        return tool_response

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
