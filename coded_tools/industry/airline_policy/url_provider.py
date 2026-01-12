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


class URLProvider(CodedTool):
    """
    CodedTool implementation which provides URLs for airline's helpdesk and intranet resources.
    """

    def __init__(self):
        """
        Constructs a URL Provider for airline's intranet.
        """
        self.airline_policy_urls = {
            "Baggage Tracking": "https://www.united.com/en/us/bagdelivery/start",
            "Damaged Bags Claim": "https://rynnsluggage.com/",
            "Missing Items": "https://www.united.com/en/US/fly/help/lost-and-found.html",
            "Claims Status": "https://www.united.com/en/us/claimform/checkstatus",
            "Carry On Baggage": "https://www.united.com/en/us/fly/baggage/carry-on-bags.html",
            "Checked Baggage": "https://www.united.com/en/us/fly/baggage/checked-bags.html",
            "Bag Issues": "https://www.united.com/en/us/baggage/bag-help",
            "Special Items": "https://www.tsa.gov/travel/security-screening/whatcanibring/sporting-and-camping",
            "Military_Personnel": "https://www.united.com/en/us/fly/company/company-info/military-benefits-and-discounts.html",  # noqa E501
            "Mileage Plus": "https://www.united.com/en/us/fly/mileageplus.html",
            "International Checked Baggage": "https://www.united.com/en/us/fly/baggage/international-checked-bag-limits.html",  # noqa E501
            "International Travel Requirements": "https://www.united.com/en/us/travel/trip-planning/travel-requirements",  # noqa E501
            "Embargoes": "https://www.united.com/en/us/fly/baggage/international-checked-bag-limits.html",
            "Basic Economy_Restrictions": "https://www.united.com/en/us/fly/travel/inflight/basic-economy.html",
            "Bag Fee Calculator": "https://www.united.com/en/us/checked-bag-fee-calculator/any-flights",
        }

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "app_name" the name of the Airline Policy for which the URL is needed.

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
                The URL to the policy as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        app_name: str = args.get("app_name", None)
        if app_name is None:
            return "Error: No app name provided."
        logger.debug(">>>>>>>>>>>>>>>>>>>URL Provider>>>>>>>>>>>>>>>>>>")
        logger.debug("App name: %s", app_name)
        app_url = self.airline_policy_urls.get(app_name)
        logger.debug("URL: %s", app_url)
        logger.debug(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return app_url
