import logging
import os
from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Union

from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor
from neuro_san.interfaces.agent_session import AgentSession
from neuro_san.interfaces.coded_tool import CodedTool

SOLVER_AGENT_NAME = "voting_solver"
SINGLE_AGENT_NAME = "thinking_module_bench"

CONNECTION_TYPE = "direct"
HOST = "localhost"  # string
PORT = 30012
LOCAL_EXTERNALS_DIRECT = False
AGENT_THINKING_PATH = "/tmp/agent_thinking.txt"  # Or wherever you want
VOTE_WIN_COUNT = 2  # require this many identical answers to win early
MAX_VOTING = 3  # max attempts
MAX_DEPTH = 3
SOLUTION_START = ">>>>"

# If True, start a fresh agent session per attempt (prevents very long carry-over chains)
ISOLATE_ATTEMPTS = True


class CallAgent(CodedTool):
    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        problem: str = args.get("problem", "")
        if not problem:
            return "Error: No problem provided."

        # Increment depth ONCE per invoke
        base_depth: str = args.get("depth", "1")
        try:
            depth_int = int(base_depth) + 1
        except ValueError:
            depth_int = 1

        # Choose agent ONCE for this invoke
        agent_name = SINGLE_AGENT_NAME if depth_int > MAX_DEPTH else SOLVER_AGENT_NAME

        print(f"inquiry: {problem}, depth: {depth_int}, agent_name: {agent_name}")

        # Optional args
        connection_type: str = args.get("connection_type", CONNECTION_TYPE)
        host: str = args.get("host", HOST)
        port: int = int(args.get("port", PORT))
        local_externals_direct: bool = args.get("local_external_direct", LOCAL_EXTERNALS_DIRECT)
        agent_thinking_path: str = args.get("agent_thinking_path", AGENT_THINKING_PATH)

        logger = logging.getLogger(self.__class__.__name__)
        vote_logger = logging.getLogger("CallAgentVoting")
        logger.info(">>>>>>>>>>>>>>>>>>>CallAgent>>>>>>>>>>>>>>>>>>")
        logger.info("problem: %s", problem)
        logger.info("depth: %s", depth_int)
        logger.info("agent_name: %s", agent_name)

        # Get or create session/state ONCE (keeps the same conversation across votes at this depth)
        agent_session = sly_data.get("agent_session")
        agent_state_info = sly_data.get("agent_state_info")
        if not agent_session or not agent_state_info:
            agent_session, agent_state_info = set_up_agent(
                agent_name, connection_type, host, port, local_externals_direct
            )

        # -------- Voting at a single depth --------
        answers: Dict[str, int] = {}
        most_popular_answer: Optional[str] = None
        most_popular_votes: int = 0
        most_popular_state_info: Optional[Dict[str, Any]] = None
        winner: Optional[str] = None
        winner_votes: int = 0
        attempts = 0

        # Keep the SAME depth across attempts; terminate early on threshold
        while attempts < MAX_VOTING:
            attempts += 1
            print(f"problem:{problem}, attempt:{attempts}")
            parsed_answer, agent_state_info = call_agent(
                agent_session, agent_state_info, problem, depth_int, agent_thinking_path
            )
            print(f"problem:{problem}, attempt:{attempts}, parsed_answer:{parsed_answer}")

            if not parsed_answer:
                vote_logger.debug("Attempt %d: Empty/None parsed answer; skipping.", attempts)
                print("Empty/None parsed answer!")
                continue

            count = answers.get(parsed_answer, 0) + 1
            answers[parsed_answer] = count

            if count > most_popular_votes:
                most_popular_votes = count
                most_popular_answer = parsed_answer
                most_popular_state_info = dict(agent_state_info)

            vote_logger.debug("Attempt %d: answer=%r votes=%d", attempts, parsed_answer, count)

            if count >= VOTE_WIN_COUNT:
                winner = parsed_answer
                winner_votes = count
                vote_logger.info(
                    "Voting reached threshold: answer=%r votes=%d attempts=%d", winner, winner_votes, attempts
                )
                print(f"answer={winner} votes={winner_votes} attempts={attempts}")
                break  # IMPORTANT: stop once we hit the threshold

        # Finalize selection
        if winner is not None:
            final_answer = winner
            final_votes = winner_votes
        else:
            final_answer = most_popular_answer or ""
            final_votes = most_popular_votes
            vote_logger.info(
                "Voting ended without threshold. Selected most popular: answer=%r votes=%d attempts=%d",
                final_answer,
                final_votes,
                attempts,
            )
            print(f"Threshold not hit: answer={final_answer} votes={final_votes} attempts={attempts}")

        # Persist session/state for next call
        if most_popular_state_info is not None:
            agent_state_info = most_popular_state_info
        sly_data["agent_session"] = agent_session
        sly_data["agent_state_info"] = agent_state_info

        logger.info("Winner (or most popular): %r with %d votes in %d attempts", final_answer, final_votes, attempts)
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")

        return final_answer


def set_up_agent(
    agent_name: str, connection_type: str, host: str, port: int, local_externals_direct: bool
) -> Tuple[AgentSession, Dict[str, Any]]:
    metadata = {"user_id": os.environ.get("USER")}
    factory = AgentSessionFactory()
    agent_session = factory.create_session(connection_type, agent_name, host, port, local_externals_direct, metadata)
    agent_state_info = {
        "last_chat_response": None,
        "prompt": "Please enter your response ('quit' to terminate):\n",
        "timeout": 5000.0,  # honored by some processors; keep small to encourage turn completion
        "num_input": 0,
        "user_input": None,
        "sly_data": None,
        "chat_filter": {"chat_filter_type": "MAXIMAL"},
    }
    return agent_session, agent_state_info


def _extract_solution_text(raw: Optional[str], marker: str) -> Optional[str]:
    if not raw:
        return None
    if marker in raw:
        return raw.split(marker, 1)[1].strip()
    return raw.strip()


def call_agent(
    agent_session: AgentSession,
    agent_state_info: Dict[str, Any],
    problem: str,
    depth: int,
    agent_thinking_path: str,
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Single turn:
      - Write user_input with the given depth
      - Run processor once
      - Return the substring after SOLUTION_START (or full trimmed text if marker absent)
    """
    input_processor = StreamingInputProcessor("DEFAULT", agent_thinking_path, agent_session, None)
    agent_state_info["user_input"] = f"problem: {problem}, depth: {depth}"
    agent_state_info = input_processor.process_once(agent_state_info)
    raw_response = agent_state_info.get("last_chat_response")
    parsed = _extract_solution_text(raw_response, SOLUTION_START)
    return parsed, agent_state_info
