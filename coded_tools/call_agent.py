import logging
import os
from typing import Any
from typing import Dict
from typing import Tuple
from typing import Union

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor
from neuro_san.interfaces.agent_session import AgentSession
from neuro_san.interfaces.coded_tool import CodedTool

CONNECTION_TYPE = "direct"
HOST = "localhost"
PORT = 30012
LOCAL_EXTERNALS_DIRECT = False
AGENT_THINKING_PATH = "/tmp/agent_thinking.txt"  # Or wherever you want


class CallAgent(CodedTool):
    """
    CodedTool implementation which provides a way to call an agent network.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "inquiry" the query for the agent.
                    "agent_name" the agent that answer the query.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation, and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "selected_agent" the agent that answer the query

        :return:
            In case of successful execution:
                The answer from the agent as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        inquiry: str = args.get("inquiry", "")
        if inquiry == "":
            return "Error: No inquiry provided."
        agent_name = args.get("agent_name") or sly_data.get("selected_agent")
        if not agent_name:
            return "Error: No 'agent_name' in args or 'selected_agent' in sly_data."

        print(f"inquiry: {inquiry}")
        print(f"agent_name: {agent_name}")

        # Optional args
        connection_type: str = args.get("connection_type", CONNECTION_TYPE)
        host: int = args.get("host", HOST)
        port: int = args.get("port", PORT)
        local_externals_direct: bool = args.get("local_external_direct", LOCAL_EXTERNALS_DIRECT)
        agent_thinking_path: str = args.get("agent_thinking_path", AGENT_THINKING_PATH)

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>CallAgent>>>>>>>>>>>>>>>>>>")
        logger.info("inquiry: %s", str(inquiry))
        logger.info("agent_name: %s", str(agent_name))

        agent_session = sly_data.get("agent_session", None)
        agent_state_info = sly_data.get("agent_state_info", None)
        if not agent_state_info or not agent_session:
            agent_session, agent_state_info = set_up_agent(
                agent_name, connection_type, host, port, local_externals_direct
            )
        response, agent_state_info = call_agent(agent_session, agent_state_info, inquiry, agent_thinking_path)
        sly_data["agent_session"] = agent_session
        sly_data["agent_state_info"] = agent_state_info

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return response


def set_up_agent(
    agent_name: str, connection_type: str, host: int, port: int, local_externals_direct: bool
) -> Tuple[AgentSession, Dict[str, Any]]:
    """Configure these as needed."""

    metadata = {"user_id": os.environ.get("USER")}

    # Create session factory and agent session
    factory = AgentSessionFactory()
    agent_session = factory.create_session(connection_type, agent_name, host, port, local_externals_direct, metadata)
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


def call_agent(
    agent_session: AgentSession, agent_state_info: Dict[str, Any], user_input: str, agent_thinking_path: str
) -> Tuple[Union[str], Dict[str, Any]]:
    """
    Processes a single turn of user input within the selected agent's session.

    This function simulates a conversational turn by:
    1. Initializing a StreamingInputProcessor to handle the input.
    2. Updating the agent's internal state with the user's input (`thoughts`).
    3. Passing the updated to the processor for handling.
    4. Extracting and returning the agent's response for this turn.

    Parameters:
        agent_session: An active session object for the selected agent.
        agent_state_info (dict): The agent's current conversation state.
        user_input (str): The user's input or query to be processed.

    Returns:
        tuple:
            - last_chat_response (str or None): The agent's response to the input.
            - agent_state_info (dict): The updated state after processing.
    """
    # Use the processor (like in agent_cli.py)
    input_processor = StreamingInputProcessor(
        "DEFAULT",
        agent_thinking_path,
        agent_session,
        None,  # Not using a thinking_dir for simplicity
    )
    # Update the conversation state with this turn's input
    agent_state_info["user_input"] = user_input
    agent_state_info = input_processor.process_once(agent_state_info)
    # Get the agent response for this turn
    last_chat_response = agent_state_info.get("last_chat_response")
    return last_chat_response, agent_state_info
