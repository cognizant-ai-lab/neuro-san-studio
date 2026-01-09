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
from pyhocon import ConfigFactory

AGENT_NETWORK_NAME = "cruse_agent"


def set_up_cruse_assistant(selected_agent):
    """Configure these as needed."""
    agent_name = AGENT_NETWORK_NAME
    connection = "direct"
    host = "localhost"
    port = 30011
    local_externals_direct = False
    metadata = {"user_id": os.environ.get("USER")}
    selected_agent = "registries/" + selected_agent

    # Create session factory and agent session
    factory = AgentSessionFactory()
    session = factory.create_session(connection, agent_name, host, port, local_externals_direct, metadata)
    sly_data = {"selected_agent": selected_agent, "agent_session": session}

    # Initialize any conversation state here
    cruse_state_info = {
        "last_chat_response": None,
        "prompt": "Please enter your response ('quit' to terminate):\n",
        "timeout": 5000.0,
        "num_input": 0,
        "user_input": None,
        "sly_data": sly_data,
        "chat_filter": {"chat_filter_type": "MAXIMAL"},
    }
    return session, cruse_state_info


def cruse(cruse_session, cruse_state_info, user_input):
    """
    Processes a single turn of user input within the cruse_agent agent's session.

    This function simulates a conversational turn by:
    1. Initializing a StreamingInputProcessor to handle the input.
    2. Updating the agent's internal state with the user's input (`thoughts`).
    3. Passing the updated state to the processor for handling.
    4. Extracting and returning the agent's response for this turn.

    Parameters:
        cruse_session: An active session object for the cruse_agent agent.
        cruse_state_info (dict): The agent's current conversation state.
        user_input (str): The user's input or query to be processed.

    Returns:
        tuple:
            - last_chat_response (str or None): The agent's response to the input.
            - cruse_state_info (dict): The updated state after processing.
    """
    # Use the processor (like in agent_cli.py)
    input_processor = StreamingInputProcessor(
        "DEFAULT",
        "/tmp/agent_thinking.txt",  # Or wherever you want
        cruse_session,
        None,  # Not using a thinking_dir for simplicity
    )
    # Update the conversation state with this turn's input
    cruse_state_info["user_input"] = user_input
    cruse_state_info = input_processor.process_once(cruse_state_info)
    # Get the agent response for this turn
    last_chat_response = cruse_state_info.get("last_chat_response")
    return last_chat_response, cruse_state_info


def tear_down_cruse_assistant(cruse_session):
    """Tear down the assistant.

    :param cruse_session: The pointer to the session.
    """
    print("tearing down cruse_agent assistant...")
    cruse_session.close()
    # client.assistants.delete(cruse_assistant_id)
    print("cruse_agent assistant torn down.")


def get_available_systems():
    """
    Parses the HOCON manifest file specified by the AGENT_MANIFEST_FILE environment variable
    and returns a list of enabled system keys.

    Systems explicitly listed in the `excluded` set will be omitted, even if enabled.

    Returns:
        List[str]: A list of enabled HOCON filenames (without surrounding quotes)
                   that are not in the excluded set.
    """
    excluded = {"cruse_agent.hocon"}  # Add more filenames as needed
    config = ConfigFactory.parse_file(os.environ["AGENT_MANIFEST_FILE"])
    return [
        key.strip('"').strip() for key, enabled in config.items() if enabled and key.strip('"').strip() not in excluded
    ]


def parse_response_blocks(response: str):
    """
    Parses a multiline response string into structured content blocks labeled as 'say' or 'gui'.

    The function detects lines that start with 'say:' or 'gui:' (case-insensitive), and
    aggregates the subsequent lines into corresponding content blocks. Each block continues
    until the next recognized prefix or the end of the response.

    Args:
        response (str): The raw response string to parse.

    Returns:
        List[Tuple[str, str]]: A list of (block_type, content) tuples, where block_type is
                               either 'say' or 'gui', and content is the corresponding block text.
    """
    blocks = []
    current_type = None
    current_lines = []

    for line in response.splitlines():
        line = line.rstrip()

        # Detect new block start
        if line.lower().startswith("say:"):
            if current_type:
                blocks.append((current_type, "\n".join(current_lines).strip()))
            current_type = "say"
            current_lines = [line[4:].lstrip()]  # content on same line
        elif line.lower().startswith("gui:"):
            if current_type:
                blocks.append((current_type, "\n".join(current_lines).strip()))
            current_type = "gui"
            current_lines = [line[4:].lstrip()]
        else:
            current_lines.append(line)

    # Append the last block
    if current_type and current_lines:
        blocks.append((current_type, "\n".join(current_lines).strip()))

    return blocks
