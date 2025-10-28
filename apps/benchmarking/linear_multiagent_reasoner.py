import os
import sys
import re
import logging
import threading
from typing import List, Tuple, Optional

from neuro_san.client.agent_session_factory import AgentSessionFactory, AgentSession
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="[%(levelname)s] %(message)s", stream=sys.stderr)

# Expect the multi_step_decomposer to output a numbered list of steps, possibly on the last line after FINAL_TOKEN.
_STEP_LINE_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*\S)\s*$", re.MULTILINE)

os.environ["AGENT_MANIFEST_FILE"] = "apps/benchmarking/manifest_solver.hocon"
os.environ["AGENT_TOOL_PATH"] = "coded_tools"

FINAL_TOKEN = "vote:"  # agents end their final answer on the last line after this token

# Tuning knobs
WINNING_VOTE_COUNT = 8
CANDIDATE_COUNT = (2 * WINNING_VOTE_COUNT) - 1
NUMBER_OF_VOTES = (2 * WINNING_VOTE_COUNT) - 1

AGENTS_PORT = 30011

# Global, shared across threads
_factory_lock = threading.RLock()
_factory: AgentSessionFactory | None = None
_sessions: dict[str, AgentSession] = {}


def _get_session(agent_name: str) -> AgentSession:
    """Return a shared, thread-safe session for the named agent."""
    global _factory
    with _factory_lock:
        if _factory is None:
            _factory = AgentSessionFactory()
        sess = _sessions.get(agent_name)
        if sess is None:
            sess = _factory.create_session(
                "direct", agent_name, "localhost", AGENTS_PORT, False,
                {"user_id": os.environ.get("USER")}
            )
            _sessions[agent_name] = sess
        return sess

def _build_steps_block(all_steps: List[str]) -> str:
    return "\n".join(f"{i+1}) {s}" for i, s in enumerate(all_steps))

def multi_step_decomposer_session() -> AgentSession:
    return _get_session("multi_step_decomposer")


def composition_discriminator_session() -> AgentSession:
    return _get_session("composition_discriminator")


def problem_solver_session() -> AgentSession:
    return _get_session("problem_solver")


# Unique temp file per *call*
def _tmpfile(stem: str) -> str:
    return f"/tmp/{stem}_{os.getpid()}_{threading.get_ident()}.txt"


def call_agent(agent_session: AgentSession, text: str, timeout_ms: float = 100000.0) -> str:
    """Call a single agent with given text, return its full response."""
    thread = {
        "last_chat_response": None,
        "prompt": "",
        "timeout": timeout_ms,
        "num_input": 0,
        "user_input": text,
        "sly_data": None,
        "chat_filter": {"chat_filter_type": "MAXIMAL"},
    }
    inp = StreamingInputProcessor("DEFAULT", _tmpfile("program_mode_thinking"),
                                  agent_session, None)
    thread = inp.process_once(thread)
    logging.debug(f"call_agent({agent_session}): sending {len(text)} chars")
    resp = thread.get("last_chat_response") or ""
    logging.debug(f"call_agent({agent_session}): received {len(resp)} chars")
    return resp


def _extract_final(text: str, token: str = FINAL_TOKEN) -> str:
    """Return the text after the last occurrence of FINAL_TOKEN (case-insensitive),
    or last non-empty line if not found."""
    if not text:
        return ""
    token_low = token.lower()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines):
        ln_low = ln.lower()
        if token_low in ln_low:
            # find index of the match in a lowercase version, but slice original line
            idx = ln_low.find(token_low)
            return ln[idx + len(token):].strip()
    return lines[-1] if lines else ""


# Replace the single-line matcher with a block matcher:
_STEP_BLOCK_RE = re.compile(
    r"^\s*(\d+)[.)]\s+(.*?)"          # step number + first line of the step
    r"(?=^\s*\d+[.)]\s+|\Z)",         # up to (but not including) next step or end
    re.MULTILINE | re.DOTALL
)

def _extract_steps(resp: str) -> List[str]:
    """
    Parse multi-line steps from the multi_step_decomposer response.
    We prefer the content after FINAL_TOKEN if present; else the full response.
    Each step can span multiple lines until the next numbered header.
    """
    text = _extract_final(resp) or resp

    matches = list(_STEP_BLOCK_RE.finditer(text))
    if not matches:
        # Fallback: try scanning the full response if tail-only failed
        matches = list(_STEP_BLOCK_RE.finditer(resp))

    if not matches:
        logging.warning("[decompose] No multi-line steps found in decomposer response.")
        return []

    # (idx, block) -> sort by idx; dedup on idx in case of echoes
    seen = set()
    steps: List[str] = []
    for m in matches:
        idx = int(m.group(1))
        if idx in seen:
            continue
        block = m.group(2).rstrip()
        # Normalize indentation/trailing spaces, but keep line breaks
        block = "\n".join(line.rstrip() for line in block.splitlines()).strip()
        steps.append(block)
        seen.add(idx)

    logging.info(f"[decompose] extracted {len(steps)} multi-line steps.")
    return steps


def _build_history_block(original_problem: str, context_history: List[str]) -> str:
    """
    Build a labeled history block that includes the original problem and ALL prior step outputs.
    This allows later steps to reference any earlier result.
    """
    parts = [f"0) ORIGINAL PROBLEM:\n{original_problem}"]
    for i, ctx in enumerate(context_history, start=1):
        parts.append(f"{i}) OUTPUT OF STEP {i}:\n{ctx}")
    return "\n\n".join(parts)

def _compose_step_prompt(
    step_instruction: str,
    original_problem: str,
    context_history: List[str],
    all_steps: List[str],
    step_index: int
) -> str:
    """
    Give problem_solver:
      - the ORIGINAL problem,
      - ALL prior outputs (full history),
      - the FULL list of ALL steps,
      - and explicitly mark the CURRENT step to solve now.
    """
    history_block = _build_history_block(original_problem, context_history)
    steps_block = _build_steps_block(all_steps)
    return (
        "You are the 'problem_solver' in a multi-step pipeline.\n"
        "Use ALL prior outputs and ALL steps for context, but ONLY execute the CURRENT STEP now.\n"
        f"problem: ORIGINAL PROBLEM:\n{original_problem}\n\n"
        f"ALL STEPS:\n{steps_block}\n\n"
        f"CURRENT STEP ({step_index+1}/{len(all_steps)}):\n{step_instruction}\n\n"
        f"HISTORY (all prior outputs):\n{history_block}\n"
    )

def _discriminator_prompt(step_instruction: str, original_problem: str, context_history: List[str],
                          candidates: List[Tuple[str, str]]) -> str:
    """
    Build the prompt for composition_discriminator.
    We include the full history so it can judge candidates that depend on earlier steps.
    candidates: list of tuples (full_response, next_context_final_line)
    The discriminator should return the index (1..N) of the preferred candidate.
    """
    history_block = _build_history_block(original_problem, context_history)

    numbered = []
    for i, (_full_resp, next_ctx) in enumerate(candidates, 1):
        numbered.append(
            f"{i}:\n{next_ctx}"
        )
    body = "\n\n".join(numbered)

    return (
        f"history:\n{history_block}\n\n"
        f"problem:\n{step_instruction}\n\n"
        f"CANDIDATES:\n{body}\n\n"
    )

def _decomposition_discriminator_prompt(problem: str, decomp_candidates: List[List[str]]) -> str:
    """
    Ask composition_discriminator to choose the best decomposition (list of steps) for the problem.
    Respond ONLY with the candidate number.
    """
    parts = []
    for i, steps in enumerate(decomp_candidates, 1):
        parts.append(f"{i})\n{_build_steps_block(steps)}")
    body = "\n\n".join(parts)
    return (
        f"PROBLEM:\n{problem}\n\n"
        f"DECOMPOSITION CANDIDATES:\n{body}\n"
    )

def _vote_among_decompositions(problem: str, decomp_candidates: List[List[str]]) -> int:
    """
    Vote among decomposition candidates using composition_discriminator.
    Returns 0-based index of the winning decomposition.
    """
    prompt = _decomposition_discriminator_prompt(problem, decomp_candidates)
    votes = [0] * len(decomp_candidates)
    winner_idx: Optional[int] = None

    for _ in range(NUMBER_OF_VOTES):
        vresp = call_agent(composition_discriminator_session(), prompt)
        vote_txt = _extract_final(vresp)
        logging.info(f"[decomp-disc] vote raw: {vote_txt!r}")
        try:
            idx = int(vote_txt) - 1
            if 0 <= idx < len(decomp_candidates):
                votes[idx] += 1
                logging.info(f"[decomp-disc] tally: {votes}")
                if votes[idx] >= WINNING_VOTE_COUNT:
                    winner_idx = idx
                    logging.info(f"[decomp-disc] early winner: {winner_idx + 1}")
                    break
        except ValueError:
            logging.warning(f"[decomp-disc] malformed vote ignored: {vote_txt!r}")

    if winner_idx is None:
        winner_idx = max(range(len(votes)), key=lambda i: votes[i])
    return winner_idx

def _vote_among_candidates(step_instruction: str, original_problem: str, context_history: List[str],
                           candidates: List[Tuple[str, str]]) -> int:
    """
    Run NUMBER_OF_VOTES votes with composition_discriminator using the full history.
    Returns 0-based index of the winning candidate.
    """
    prompt = _discriminator_prompt(step_instruction, original_problem, context_history, candidates)
    votes = [0] * len(candidates)
    winner_idx: Optional[int] = None

    for _ in range(NUMBER_OF_VOTES):
        vresp = call_agent(composition_discriminator_session(), prompt)
        vote_txt = _extract_final(vresp)
        logging.info(f"[discriminator] vote raw: {vote_txt!r}")
        try:
            idx = int(vote_txt) - 1
            if 0 <= idx < len(candidates):
                votes[idx] += 1
                logging.info(f"[discriminator] tally: {votes}")
                if votes[idx] >= WINNING_VOTE_COUNT:
                    winner_idx = idx
                    logging.info(f"[discriminator] early winner: {winner_idx + 1}")
                    break
        except ValueError:
            logging.warning(f"[discriminator] malformed vote ignored: {vote_txt!r}")

    if winner_idx is None:
        winner_idx = max(range(len(votes)), key=lambda i: votes[i])
    return winner_idx


def multi_step_solve(problem: str) -> str:
    """
      1) Call multi_step_decomposer once to get a numbered list of steps.
      2) Maintain context_history = [] (all prior step outputs).
      3) For each step:
           a) Generate SOLUTION_CANDIDATE_COUNT candidate contexts via problem_solver
              using the FULL history.
           b) Ask composition_discriminator (with FULL history) to choose the best candidate.
           c) Append the winner's NEXT CONTEXT to context_history.
      4) Return the FULL response of the chosen candidate from the FINAL step.
    If no steps are found, falls back to a single atomic problem_solver call.
    """
    logging.info("[pipeline] starting multi-step solve")

    # Collect multiple decompositions
    decomp_candidates: List[List[str]] = []
    for _ in range(CANDIDATE_COUNT):
        decomp_resp = call_agent(multi_step_decomposer_session(), problem)
        logging.info(f"[pipeline] decomp resp: {decomp_resp}")
        steps_i = _extract_steps(decomp_resp)
        if steps_i:
            decomp_candidates.append(steps_i)

    if not decomp_candidates:
        logging.info("[pipeline] no steps parsed from any candidate -> atomic solve")
        return call_agent(problem_solver_session(), problem)

    # Vote among decompositions (or take the sole candidate)
    if len(decomp_candidates) == 1:
        steps = decomp_candidates[0]
    else:
        didx = _vote_among_decompositions(problem, decomp_candidates)
        steps = decomp_candidates[didx]

    logging.info(f"[pipeline] chosen steps: {steps}")

    context_history: List[str] = []  # store ALL prior outputs (step 1..k-1)
    last_full_response = ""          # full response of the chosen candidate of the last step

    for step_idx, step_instruction in enumerate(steps, 1):
        logging.info(f"[pipeline] step {step_idx}/{len(steps)}: {step_instruction}")

        # Generate candidates using FULL history
        candidates: List[Tuple[str, str]] = []
        for k in range(CANDIDATE_COUNT):
            prompt = _compose_step_prompt(
                step_instruction=step_instruction,
                original_problem=problem,
                context_history=context_history,
                all_steps=steps,
                step_index=step_idx - 1,
            )
            full = call_agent(problem_solver_session(), prompt)
            nxt = _extract_final(full)
            candidates.append((full, nxt))
            logging.info(f"[pipeline] step {step_idx} candidate {k + 1} next_ctx: {nxt!r}")

        # Discriminate with FULL history
        winner_idx = _vote_among_candidates(step_instruction, problem, context_history, candidates)
        last_full_response, chosen_next_context = candidates[winner_idx]
        logging.info(f"[pipeline] step {step_idx} winner: {winner_idx + 1}, appending ctx -> {chosen_next_context!r}")

        # Append the chosen output to the history (so ALL prior outputs are available to later steps)
        context_history.append(chosen_next_context)

    logging.info(f"[pipeline] final context (last): {context_history[-1] if context_history else ''!r}")
    return last_full_response


def main():
    # Read the full prompt (problem) from stdin
    problem = sys.stdin.read().strip()
    if not problem:
        print("[ERROR] No input provided.", file=sys.stderr)
        sys.exit(1)

    final_resp = multi_step_solve(problem)

    # Print EXACTLY what the benchmark runner should capture; include the agent’s full response
    # (which is expected to end with the final line containing the FINAL_TOKEN).
    logging.info(f"[main] final answer: {_extract_final(final_resp)!r}")
    print(final_resp)


if __name__ == "__main__":
    main()
