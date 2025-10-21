from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.intranet_agents_with_tools.url_provider import URLProvider


class ScheduleLeaveTool(CodedTool):
    """
    CodedTool implementation which schedules a leave (time off, vacation) for an employee
    """

    def __init__(self):
        """
        Constructs a Leave Scheduler for company's intranet.
        """
        url_provider = URLProvider()
        self.tool_url = url_provider.company_urls.get("Absence Management")

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent. This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "start_date" the start date of the leave;
                    "end_date" the end date of the leave;

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "login" The user id describing who is making the request.

        :return:
            In case of successful execution:
                A string confirmation ID for the scheduled leave."
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        start_date: str = args.get("start_date", "need-start-date")
        end_date: str = args.get("end_date", "need-end-date")
        confirmation_id = "Oli-42XB35-leave-scheduled-conf-id"
        print(">>>>>>>>>>>>>>>>>>>SCHEDULING !!!>>>>>>>>>>>>>>>>>>")
        print(f"Start date: {start_date}")
        print(f"End date: {end_date}")
        print(f"Confirmation ID: {confirmation_id}")
        print(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        confirmation = {
            "Start date": start_date,
            "End date": end_date,
            "Confirmation ID": confirmation_id,
            "Tool": self.tool_url,
        }
        return confirmation

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)
