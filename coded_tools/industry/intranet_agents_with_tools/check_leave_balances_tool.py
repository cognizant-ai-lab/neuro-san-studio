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

from coded_tools.industry.intranet_agents_with_tools.absence_manager import AbsenceManager

logger = logging.getLogger(__name__)

MOCK_RESPONSE = {
    "Absencemodel": [
        {"AbsenceName": "Jury Duty", "AbsPin": "10081", "Balance": "10.00"},
        {"AbsenceName": "Time to Vote", "AbsPin": "21582", "Balance": "0.00"},
        {"AbsenceName": "Sick Time", "AbsPin": "10097", "Balance": "0.00"},
        {"AbsenceName": "Vacation Time", "AbsPin": "10102", "Balance": "12.73"},
        {"AbsenceName": "Bereavement Leave", "AbsPin": "10114", "Balance": "5.00"},
        {"AbsenceName": "Floating Holiday", "AbsPin": "22716", "Balance": "0.00"},
    ],
    "Warning": "Applying backdated leave beyond 14 days is non-compliance as per our leave policy."
    " However, you can proceed with backdated leave application for up to a maximum of 2 times."
    " You shall not be eligible to record past dated leave beyond 14 days from third instance"
    " onwards. A trigger will be sent to your home manager to ensure that you are applying"
    " leave on time henceforth. Kindly apply / cancel leave on time to be compliant.",
}


class CheckLeaveBalancesTool(CodedTool):
    """
    CodedTool implementation which checks the Leave Balances for an employee.
    """

    def __init__(self):
        """
        Constructs a Leave Balances Checker for company's intranet.
        """
        # Construct an AbsenceManager object using environment variables
        self.absence_manager = AbsenceManager(None, None, None)

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent. This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "start_date" the date on which to check the balances (format: 'YYYY-MM-DD')

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
                An Absence Entitlement Balances dictionary with string keys that represent the Entitlement Name
                and the string values that contain the Current Balances in Days.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        start_date: str = args.get("start_date", "need-start-date")
        logger.debug(">>>>>>>>>>>>>>>>>>> Checking Leave Balances >>>>>>>>>>>>>>>>>>")
        logger.debug("Start date: %s", start_date)
        if self.absence_manager.is_configured:
            logger.debug("AbsenceManager is configured. Fetching absence types...")
            absence_types = self.absence_manager.get_absence_types(start_date)
        else:
            logger.warning("WARNING: AbsenceManager is not configured. Using mock response")
            absence_types = MOCK_RESPONSE
        absence_types["app_name"] = "Absence Management"
        absence_types["app_url"] = self.absence_manager.app_url
        logger.debug("-----------------------")
        logger.debug("Absence Types: %s", absence_types)
        logger.debug(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return absence_types

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)


# Example usage:
if __name__ == "__main__":
    check_leave_balances_tool = CheckLeaveBalancesTool()

    # Get absence types
    START_DATE = "2024-11-22"
    an_absence_types = check_leave_balances_tool.invoke(args={"start_date": START_DATE}, sly_data={})
    logger.debug(an_absence_types)
