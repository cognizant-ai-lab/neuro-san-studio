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
        print(">>>>>>>>>>>>>>>>>>>URL Provider>>>>>>>>>>>>>>>>>>")
        print(f"App name: {app_name}")
        app_url = self.airline_policy_urls.get(app_name)
        print(f"URL: {app_url}")
        print(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return app_url
