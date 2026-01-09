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

import os

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

AGENT_NETWORK_NAME = "conscious_agent"


def set_up_conscious_assistant():
    """Configure these as needed."""
    agent_name = AGENT_NETWORK_NAME
    connection = "direct"
    host = "localhost"
    port = 30011
    local_externals_direct = False
    metadata = {"user_id": os.environ.get("USER")}

    # Create session factory and agent session
    factory = AgentSessionFactory()
    session = factory.create_session(connection, agent_name, host, port, local_externals_direct, metadata)
    # Initialize any conversation state here
    conscious_thread = {
        "last_chat_response": None,
        "prompt": "Please enter your response ('quit' to terminate):\n",
        "timeout": 5000.0,
        "num_input": 0,
        "user_input": None,
        "sly_data": None,
        "chat_filter": {"chat_filter_type": "MAXIMAL"},
    }
    return session, conscious_thread


def conscious_thinker(conscious_session, conscious_thread, thoughts):
    """
    Processes a single turn of user input within the conscious agent's session.

    This function simulates a conversational turn by:
    1. Initializing a StreamingInputProcessor to handle the input.
    2. Updating the agent's internal thread state with the user's input (`thoughts`).
    3. Passing the updated thread to the processor for handling.
    4. Extracting and returning the agent's response for this turn.

    Parameters:
        conscious_session: An active session object for the conscious agent.
        conscious_thread (dict): The agent's current conversation thread state.
        thoughts (str): The user's input or query to be processed.

    Returns:
        tuple:
            - last_chat_response (str or None): The agent's response to the input.
            - conscious_thread (dict): The updated thread state after processing.
    """
    # Use the processor (like in agent_cli.py)
    input_processor = StreamingInputProcessor(
        "DEFAULT",
        "/tmp/agent_thinking.txt",  # Or wherever you want
        conscious_session,
        None,  # Not using a thinking_dir for simplicity
    )
    # Update the conversation state with this turn's input
    conscious_thread["user_input"] = thoughts
    conscious_thread = input_processor.process_once(conscious_thread)
    # Get the agent response for this turn
    last_chat_response = conscious_thread.get("last_chat_response")
    return last_chat_response, conscious_thread


def tear_down_conscious_assistant(conscious_session):
    """Tear down the assistant.

    :param conscious_session: The pointer to the session.
    """
    print("tearing down conscious assistant...")
    conscious_session.close()
    # client.assistants.delete(conscious_assistant_id)
    print("conscious assistant torn down.")
