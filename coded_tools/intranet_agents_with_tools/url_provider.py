import os
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool


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
        print(f"Company URLs: {self.company_urls}")

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
        print(">>>>>>>>>>>>>>>>>>>URL Provider>>>>>>>>>>>>>>>>>>")
        print(f"App name: {app_name}")
        app_url = self.company_urls.get(app_name)
        print(f"URL: {app_url}")
        print(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return app_url

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)
