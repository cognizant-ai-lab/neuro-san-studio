
# Copyright © 2023-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
from typing import Dict
from typing import Union


from logging import getLogger
from logging import Logger

from neuro_san.interfaces.coded_tool import CodedTool


class Accountant(CodedTool):
    """
    A tool that updates a running cost each time it is called.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Updates the passed running cost each time it's called.
        :param args: A dictionary with optional key:
                    "running_cost": the running cost to update (optional if in sly_data).

        :param sly_data: A dictionary containing parameters that should be kept out of the chat stream.
                         Keys expected for this implementation are:
                         "running_cost": the running cost to update (optional if in args).

        :return: A dictionary containing:
                 "running_cost": the updated running cost.
                 Also updates sly_data with the new running cost if it was the source.
        """
        tool_name = self.__class__.__name__
        logger: Logger = getLogger(self.__class__.__name__)

        logger.debug("========== Calling %s ==========", tool_name)
        logger.debug("args: %s", str(args))

        # Try to get running_cost from args first, then sly_data, then default to 0.0
        if "running_cost" in args:
            running_cost: float = float(args.get("running_cost"))
        else:
            running_cost: float = float(sly_data.get("running_cost", 0.0))

        # Increment the running cost not using value other than 1
        # This would make it a little harder if the LLM wanted to guess
        updated_running_cost: float = running_cost + 3.0

        # Update sly_data if running_cost came from it
        if "running_cost" not in args:
            sly_data["running_cost"] = updated_running_cost

        tool_response = {
            "running_cost": updated_running_cost
        }
        logger.debug("-----------------------")
        logger.debug("%s response: %s", tool_name, tool_response)
        logger.debug("========== Done with %s ==========", tool_name)
        return tool_response
