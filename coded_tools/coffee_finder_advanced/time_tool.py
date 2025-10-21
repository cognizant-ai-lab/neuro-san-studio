# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import datetime
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool


class TimeTool(CodedTool):
    """
    Returns either the time from sly_data or the current time.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: an empty dictionary (not used).

        :param sly_data: a dictionary with the following keys:
            - time: optional - the time to return to calling agents.

        :return: the current time
        """
        print(">>>>>>>>>>>>>>>>>>> TimeTool >>>>>>>>>>>>>>>>>>")
        sly_time = sly_data.get("time")
        if sly_time:
            response = sly_time
        else:
            # No time was provided in sly_data. Return the current time.
            response = datetime.datetime.now().strftime("%I:%M %p").lstrip("0")
        print(f"Response: {response}")
        print(">>>>>>>>>>>>>>>>>>> DONE !!! >>>>>>>>>>>>>>>>>>")
        return response

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
