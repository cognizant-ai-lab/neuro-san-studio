from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agentforce.agentforce_adapter import AgentforceAdapter


class AgentforceAPI(CodedTool):
    """
    CodedTool implementation of Agentforce API.
    """

    def __init__(self):
        """
        Constructs an Agentforce API for Cognizant's Neuro AI Multi-Agent Accelerator.
        """
        # Construct an AgentforceAdapter object using environment variables
        self.agentforce = AgentforceAdapter(None, None)

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent. This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "inquiry" the date on which to check the balances (format: 'YYYY-MM-DD')

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
                A respose from the Agentforce API.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        inquiry: str = args.get("inquiry")
        print(f"========== Calling self.__class__.__name__ ==========")
        print(f"Start date: {inquiry}")
        if self.agentforce.is_configured:
            print("AgentforceAdapter is configured. Fetching response...")
            res = self.agentforce.get_response(inquiry)
        else:
            print("WARNING: AgentforceAdapter is not configured. Using mock response")
            res = "mocking bla"
        res["app_name"] = "Agentforce Adapter"
        res["app_url"] = self.agentforce.APP_URL
        print("-----------------------")
        print("Agentforce response:", res)
        print("========== Done with self.__class__.__name__ ==========")
        return res


# Example usage:
if __name__ == "__main__":
    agentforce_tool = AgentforceAPI()

    af_inquiry = "find a random product"
    # Get response
    af_res = agentforce_tool.invoke(args={"inquiry": af_inquiry}, sly_data={})
