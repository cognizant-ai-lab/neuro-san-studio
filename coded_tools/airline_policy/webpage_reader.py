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

import requests
from bs4 import BeautifulSoup
from neuro_san.interfaces.coded_tool import CodedTool


class WebPageReader(CodedTool):
    """
    A coded tool that reads and extracts all visible text from a given webpage URL.
    """

    def __init__(self):
        """
        Constructs a WebPageReader for airline's intranet.
        """
        self.default_url = ["https://www.united.com/en/us/fly/help-center.html"]
        self.airline_policy_urls = {
            "Carry On Baggage": ["https://www.united.com/en/us/fly/baggage/carry-on-bags.html"],
            "Checked Baggage": ["https://www.united.com/en/us/fly/baggage/checked-bags.html"],
            "Bag Issues": [
                "https://www.united.com/en/us/baggage/bag-help",
                "https://www.united.com/en/US/fly/help/lost-and-found.html",
            ],
            "Special Items": [
                "https://www.tsa.gov/travel/security-screening/whatcanibring/sporting-and-camping",
                "https://www.united.com/en/us/fly/baggage/fragile-and-valuable-items.html",
            ],
            "Military Personnel": [
                "https://www.united.com/en/us/fly/company/company-info/military-benefits-and-discounts.html"
            ],
            "Basic Economy Restrictions": ["https://www.united.com/en/us/fly/travel/inflight/basic-economy.html"],
            "Mileage Plus": ["https://www.united.com/en/us/fly/mileageplus.html"],
            "Bag Fee Calculator": ["https://www.united.com/en/us/checked-bag-fee-calculator/any-flights"],
            "International Checked_Baggage": [
                "https://www.united.com/en/us/fly/baggage/international-checked-bag-limits.html"
            ],
            "Embargoes": ["https://www.united.com/en/us/fly/baggage/international-checked-bag-limits.html"],
        }

    def invoke(self, args: Dict[str, Any]) -> Union[str, Dict[str, Any]]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent. This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "app_name" the name of the Airline Policy for which the webpage text is needed.

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
                The extracted text from the provided webpages.
            otherwise:
                A text string an error message in the format:
                "Error: <error message>"
        """
        app_name: str = args.get("app_name", None)
        if app_name is None:
            return "Error: No app name provided."
        print(">>>>>>>>>>>>>>>>>>> Extracting text >>>>>>>>>>>>>>>>>>")
        try:
            urls = self.airline_policy_urls.get(app_name, self.default_url)
            print(f"Fetching details from: {urls}")
            if not isinstance(urls, list) or not urls:
                return "Error: No URLs provided or invalid format. Expected a list of URLs."

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa E501
            }
            results = {}
            for url in urls:
                try:
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, "html.parser")
                    texts = soup.stripped_strings
                    full_text = " ".join(texts)
                    results[url] = full_text
                except Exception as e:
                    results[url] = f"Error: Unable to process the URL. {str(e)}"
            print(">>>>>>>>>>>>>>>>>>> Done! >>>>>>>>>>>>>>>>>>")
            return results
        except Exception as e:
            return f"Error: Unable to process the request. {str(e)}"
