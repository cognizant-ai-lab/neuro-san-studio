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

import json
import os
import re

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

AGENT_THINKING_LOGS_DIRECTORY = "/private/tmp/agent_thinking"

AGENT_NETWORK_NAME = "log_analysis_agents"
os.environ["AGENT_MANIFEST_FILE"] = "registries/manifest.hocon"
os.environ["AGENT_TOOL_PATH"] = "coded_tools"


def set_up_log_analyzer():
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
    analysis_thread = {
        "last_chat_response": None,
        "prompt": "Analyze the agent log\n",
        "timeout": 5000.0,
        "num_input": 0,
        "user_input": None,
        "sly_data": None,
        "chat_filter": {"chat_filter_type": "MAXIMAL"},
    }
    return session, analysis_thread


def log_analyzer_agent(analysis_session, analysis_thread, log_entry):
    """
    Processes a single turn of user input within the analysis agent's session.

    This function simulates a conversational turn by:
    1. Initializing a StreamingInputProcessor to handle the input.
    2. Updating the agent's internal thread state with the user's input (`log_entry`).
    3. Passing the updated thread to the processor for handling.
    4. Extracting and returning the agent's response for this turn.

    Parameters:
        analysis_session: An active session object for the analysis agent.
        analysis_thread (dict): The agent's current conversation thread state.
        log_entry (str): The user's input or query to be processed.

    Returns:
        tuple:
            - last_chat_response (str or None): The agent's response to the input.
            - analysis_thread (dict): The updated thread state after processing.
    """
    # Use the processor (like in agent_cli.py)
    input_processor = StreamingInputProcessor(
        "DEFAULT",
        "/tmp/agent_thinking.txt",  # Or wherever you want
        analysis_session,
        None,  # Not using a thinking_dir for simplicity
    )
    # Update the conversation state with this turn's input
    analysis_thread["user_input"] = log_entry
    analysis_thread = input_processor.process_once(analysis_thread)
    # Get the agent response for this turn
    last_chat_response = analysis_thread.get("last_chat_response")
    return last_chat_response, analysis_thread


def tear_down_analysis_assistant(analysis_session):
    """Tear down the assistant.

    :param analysis_session: The pointer to the session.
    """
    print("tearing down analysis assistant...")
    analysis_session.close()
    # client.assistants.delete(analysis_assistant_id)
    print("analysis assistant torn down.")


def parse_log_files(directory_path, log_analyzer, analysis_session, analysis_thread):
    """
    Parse all log files in a directory and extract system prompts and conversation entries.

    Args:
        directory_path (str): Path to directory containing log files
        log_analyzer: Function to call for analysis
        analysis_session: Session object for analysis
        analysis_thread: Thread object for analysis
    """

    # Get all log files in the directory
    log_files = list(os.listdir(directory_path))  # if f.endswith('.log') or f.endswith('.txt')]

    for log_file in log_files:
        file_path = os.path.join(directory_path, log_file)
        print(f"Processing file: {log_file}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract system prompt
            system_prompt = extract_system_prompt(content)

            # Extract conversation entries
            conversation_entries = extract_conversation_entries(content)

            # Process each conversation entry
            for log_entry in conversation_entries:
                if log_entry.strip():  # Skip empty entries
                    analysis, analysis_thread = log_analyzer(
                        analysis_session, analysis_thread, system_prompt + " " + log_entry
                    )
                    print(analysis)

        except (FileNotFoundError, UnicodeDecodeError, IOError) as e:
            print(f"Error processing file {file_path}: {str(e)}")

        except Exception as e:
            # Optional: log this or raise it after logging
            print(f"Unexpected error processing file {file_path}: {str(e)}")
            raise  # Or use logging framework to log full traceback


def extract_system_prompt(content):
    """
    Extract the [SYSTEM] section from the log content.

    Args:
        content (str): Full log file content

    Returns:
        str: System prompt text
    """
    system_match = re.search(r"\[SYSTEM]:\s*\n(.*?)(?=\[HUMAN]|\[AI]|\[AGENT]|$)", content, re.DOTALL)

    if system_match:
        return system_match.group(1).strip()
    return ""


def extract_conversation_entries(content):
    """
    Extract conversation entries from [HUMAN] to [AI] plus the following [AGENT] metadata.

    Args:
        content (str): Full log file content

    Returns:
        list: List of conversation entry strings
    """
    entries = []

    # Split content into sections
    sections = re.split(r"(\[(?:HUMAN|AI|AGENT|SYSTEM)])", content)

    # Remove empty sections and combine with their labels
    labeled_sections = []
    for i in range(0, len(sections), 2):
        if i + 1 < len(sections):
            label = sections[i + 1] if i + 1 < len(sections) else ""
            content_part = sections[i + 2] if i + 2 < len(sections) else ""
            if label and content_part.strip():
                labeled_sections.append((label, content_part.strip()))

    # Find conversation patterns: [HUMAN] -> ... -> [AI] -> [AGENT] (with metadata)
    i = 0
    while i < len(labeled_sections):
        if labeled_sections[i][0] == "[HUMAN]":
            entry_parts = []
            current_pos = i

            # Add the HUMAN section
            entry_parts.append(f"[HUMAN]:\n{labeled_sections[current_pos][1]}")
            current_pos += 1

            # Collect everything until we find [AI]
            while current_pos < len(labeled_sections) and labeled_sections[current_pos][0] != "[AI]":
                label, content_part = labeled_sections[current_pos]
                entry_parts.append(f"{label}:\n{content_part}")
                current_pos += 1

            # Add the AI section if found
            if current_pos < len(labeled_sections) and labeled_sections[current_pos][0] == "[AI]":
                entry_parts.append(f"[AI]:\n{labeled_sections[current_pos][1]}")
                current_pos += 1

                # Look for the following AGENT section with metadata (JSON)
                if (
                    current_pos < len(labeled_sections)
                    and labeled_sections[current_pos][0] == "[AGENT]"
                    and is_json_metadata(labeled_sections[current_pos][1])
                ):
                    entry_parts.append(f"[AGENT]:\n{labeled_sections[current_pos][1]}")
                    current_pos += 1

            # Combine all parts into a single log entry
            if len(entry_parts) >= 2:  # At least HUMAN and AI
                log_entry = "\n".join(entry_parts)
                entries.append(log_entry)

            i = current_pos
        else:
            i += 1

    return entries


def is_json_metadata(content):
    """
    Check if content appears to be JSON metadata (contains expected fields like completion_tokens).

    Args:
        content (str): Content to check

    Returns:
        bool: True if content appears to be metadata JSON
    """
    try:
        data = json.loads(content.strip())
        # Check if it has the expected metadata fields
        expected_fields = ["completion_tokens", "prompt_tokens", "total_tokens"]
        return any(field in data for field in expected_fields)
    except (json.JSONDecodeError, TypeError):
        return False


# Example usage:
def agentic_log_analyzer(analysis_session, analysis_thread, combined_input):
    """
    Example log analyzer function - replace with your actual implementation
    """
    # This is a placeholder - replace with your actual log_analyzer function
    analysis, analysis_thread = log_analyzer_agent(analysis_session, analysis_thread, combined_input)
    print(analysis)
    return analysis, analysis_thread


# Example usage:
if __name__ == "__main__":
    # Replace these with your actual objects/functions
    the_analysis_session, the_analysis_thread = set_up_log_analyzer()

    # Call the parser
    parse_log_files(AGENT_THINKING_LOGS_DIRECTORY, agentic_log_analyzer, the_analysis_session, the_analysis_thread)

    tear_down_analysis_assistant(the_analysis_session)
