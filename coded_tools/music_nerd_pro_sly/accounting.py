# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool


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
        print(f"========== Calling {tool_name} ==========")
        print(f"args: {args}")
        # Parse the sly data
        print(f"sly_data: {sly_data}")
        # Get the current running cost. If not present, start at 0.0
        running_cost: float = float(sly_data.get("running_cost", 0.0))

        # Increment the running cost
        updated_running_cost: float = running_cost + 3.0

        # Update the sly_data
        sly_data["running_cost"] = updated_running_cost

        tool_response = {"running_cost": updated_running_cost}
        print("-----------------------")
        print(f"{tool_name} response: ", tool_response)
        print(f"========== Done with {tool_name} ==========")
        return tool_response

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
