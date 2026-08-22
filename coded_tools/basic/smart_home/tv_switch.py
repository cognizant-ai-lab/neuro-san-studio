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


class TVSwitch(CodedTool):
    """
    CodedTool implementation that calls an API to turn a TV on or off.
    """

    def __init__(self):
        """
        Constructs a switch for a TV.
        """
        self.tv_status = "OFF"
        logger.debug("... TV Switch initialized ...")

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "desired_status": whether the TV should be turned ON or OFF.

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
                The URL to the app as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        logger.debug(">>>>>>>>>>>>>>>>>>>TV Switch>>>>>>>>>>>>>>>>>>")
        # message = self.do_it(args)  # Would use this method if we could keep a state in the CodedTool
        logger.debug("--TV power button pressed--")
        message = "Power button pressed on the TV remote."
        logger.debug(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return message

    def do_it(self, args):
        """
        Calls the API to turn the TV on or off.
        :param args: A dictionary containing the `desired_status` key
        :return:a string explaining the result of the operation
        """
        desired_status: str = args.get("desired_status", None)
        # Check if the API was called correctly
        if desired_status is None:
            return "Error: No desired status provided."

        logger.debug("Desired status: %s", desired_status)
        logger.debug("Current status: %s", self.tv_status)
        # if desired status equals current status, nothing to do
        if desired_status == self.tv_status:
            message = f"TV is already {desired_status}"
        else:
            # else, update the status
            old_status = self.tv_status
            self.tv_status = desired_status
            message = f"TV was {old_status}. It is now {self.tv_status}"
        return message

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
