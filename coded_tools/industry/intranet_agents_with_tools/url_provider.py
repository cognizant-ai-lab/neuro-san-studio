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
import os
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)


class URLProvider(CodedTool):
    """
    CodedTool implementation which provides URLs for company's intranet apps.
    """

    def __init__(self):
        """
        Constructs a URL Provider for company's intranet.
        """
        intranet_url = os.environ.get("MI_INTRANET", None)
        hcm_url = os.environ.get("MI_HCM", None)
        absence_management_url = os.environ.get("MI_ABSENCE_MANAGEMENT", None)
        travel_and_expense_url = os.environ.get("MI_TRAVEL_AND_EXPENSE", None)
        gsd_url = os.environ.get("MI_GSD", None)

        self.company_urls = {
            "My Intranet": intranet_url,
            "HCM": hcm_url,
            "Absence Management": absence_management_url,
            "Travel and Expense": travel_and_expense_url,
            "GSD": gsd_url,
        }
        logger.debug("Company URLs: %s", self.company_urls)

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "app_name" the name of the company's intranet app for which the URL is needed.

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
        app_name: str = args.get("app_name", None)
        if app_name is None:
            return "Error: No app name provided."
        logger.debug(">>>>>>>>>>>>>>>>>>>URL Provider>>>>>>>>>>>>>>>>>>")
        logger.debug("App name: %s", app_name)
        app_url = self.company_urls.get(app_name)
        logger.debug("URL: %s", app_url)
        logger.debug(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return app_url

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)
