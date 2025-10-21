import logging
import os
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor
from neuro_san.interfaces.coded_tool import CodedTool

CONNECTION_TYPE = "direct"
HOST = "localhost"
PORT = 30011


class CallAgent(CodedTool):
    """
    CodedTool implementation which provides a way to utilize different websites' search feature
    """

    def __init__(self):
        self.top_n = 5
        self.agent_name = None
        self.agent_state_info = None

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "app_name" the name of the One Cognizant app for which the URL is needed.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation, and the coded_tool implementation
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
        inquiry: str = args.get("inquiry", "")
        if inquiry == "":
            return "Error: No inquiry provided."
        mode: str = args.get("mode", "")
        if mode == "":
            return "Error: No mode provided."
        self.agent_name: str = sly_data.get("selected_agent", "")
        if self.agent_name == "":
            return "Error: No select_agent in sly_data."

        print(f"inquiry: {inquiry}")
        print(f"mode: {mode}")
        print(f"agent_name: {self.agent_name}")

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>CallAgent>>>>>>>>>>>>>>>>>>")
        logger.info("inquiry: %s", str(inquiry))
        logger.info("mode: %s", str(mode))
        logger.info("agent_name: %s", str(self.agent_name))

        agent_session = sly_data.get("agent_session", None)
        self.agent_state_info = sly_data.get("agent_state_info", None)
        if not self.agent_state_info or not agent_session:
            agent_session, self.agent_state_info = self.set_up_agent()
        response, self.agent_state_info = self.call_agent(agent_session, inquiry + mode)
        sly_data["agent_session"] = agent_session
        sly_data["agent_state_info"] = self.agent_state_info

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return response

    def set_up_agent(self):
        """Configure these as needed."""
        connection = CONNECTION_TYPE
        host = HOST
        port = PORT
        local_externals_direct = False
        metadata = {"user_id": os.environ.get("USER")}

        # Create session factory and agent session
        factory = AgentSessionFactory()
        agent_session = factory.create_session(
            connection, self.agent_name, host, port, local_externals_direct, metadata
        )
        # Initialize any conversation state here
        agent_state_info = {
            "last_chat_response": None,
            "prompt": "Please enter your response ('quit' to terminate):\n",
            "timeout": 5000.0,
            "num_input": 0,
            "user_input": None,
            "sly_data": None,
            "chat_filter": {"chat_filter_type": "MAXIMAL"},
        }
        return agent_session, agent_state_info

    def call_agent(self, agent_session, user_input):
        """
        Processes a single turn of user input within the selected agent's session.

        This function simulates a conversational turn by:
        1. Initializing a StreamingInputProcessor to handle the input.
        2. Updating the agent's internal state with the user's input (`thoughts`).
        3. Passing the updated to the processor for handling.
        4. Extracting and returning the agent's response for this turn.

        Parameters:
            agent_session: An active session object for the selected agent.
            user_input (str): The user's input or query to be processed.

        Returns:
            tuple:
                - last_chat_response (str or None): The agent's response to the input.
                - agent_state_info (dict): The updated state after processing.
        """
        # Use the processor (like in agent_cli.py)
        input_processor = StreamingInputProcessor(
            "DEFAULT",
            "/tmp/agent_thinking.txt",  # Or wherever you want
            agent_session,
            None,  # Not using a thinking_dir for simplicity
        )
        # Update the conversation state with this turn's input
        self.agent_state_info["user_input"] = user_input
        agent_state_info = input_processor.process_once(self.agent_state_info)
        # Get the agent response for this turn
        last_chat_response = agent_state_info.get("last_chat_response")
        return last_chat_response, agent_state_info
