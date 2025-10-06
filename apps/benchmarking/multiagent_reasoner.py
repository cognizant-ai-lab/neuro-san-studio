import os
import sys
import re
import logging
from neuro_san.client.agent_session_factory import AgentSessionFactory, AgentSession
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=LOG_LEVEL, format="[%(levelname)s] %(message)s", stream=sys.stderr)

_DECOMP_FIELD_RE = re.compile(r"(P1|P2|C)\s*=\s*\[(.*?)]", re.DOTALL)

os.environ["AGENT_MANIFEST_FILE"] = "registries/manifest.hocon"
os.environ["AGENT_TOOL_PATH"] = "coded_tools"

FINAL_TOKEN = ">>>>"  # agents end their final answer on the last line after this token

# Tuning knobs
CANDIDATE_COUNT = 3
NUMBER_OF_VOTES = 5
WINNING_VOTE_COUNT = 3
SOLUTION_CANDIDATE_COUNT = 3
MAX_DEPTH = 3


AGENTS_PORT = 30011

agent_session_factory = AgentSessionFactory()
decomposer_agent_session = agent_session_factory.create_session(
    "direct", "decomposer", "localhost", AGENTS_PORT, False,
    {"user_id": os.environ.get("USER")}
)
solution_discriminator_agent_session = agent_session_factory.create_session(
    "direct", "solution_discriminator", "localhost", AGENTS_PORT, False,
    {"user_id": os.environ.get("USER")}
)
composition_discriminator_agent_session = agent_session_factory.create_session(
    "direct", "composition_discriminator", "localhost", AGENTS_PORT, False,
    {"user_id": os.environ.get("USER")}
)
thinking_module_bench_agent_session = agent_session_factory.create_session(
    "direct", "thinking_module_bench", "localhost", AGENTS_PORT, False,
    {"user_id": os.environ.get("USER")}
)


def call_agent(agent_session: AgentSession, text: str, timeout_ms: float = 10000.0) -> str:
    """Call a single agent with given text, return its response."""
    thread = {
        "last_chat_response": None,
        "prompt": "",
        "timeout": timeout_ms,
        "num_input": 0,
        "user_input": text,
        "sly_data": None,
        "chat_filter": {"chat_filter_type": "MAXIMAL"},
    }
    inp = StreamingInputProcessor("DEFAULT", "/tmp/program_mode_thinking.txt",
                                  agent_session, None)
    thread = inp.process_once(thread)
    logging.debug(f"call_agent({agent_session}): sending {len(text)} chars")
    resp = thread.get("last_chat_response") or ""
    logging.debug(f"call_agent({agent_session}): received {len(resp)} chars")
    return resp

def _extract_final(text: str, token: str = FINAL_TOKEN) -> str:
    """Return the text after the last occurrence of FINAL_TOKEN, or entire string if not found."""
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # prefer last line that contains token; fallback to last line
    for ln in reversed(lines):
        if token in ln:
            return ln.split(token, 1)[1].strip()
    return lines[-1] if lines else ""

def _extract_decomposition_text(resp: str) -> str | None:
    """
    Scan the FULL agent response (multi-line) for P1=[...], P2=[...], C=[...].
    Returns a canonical single-line 'P1=[...], P2=[...], C=[...]' or None.
    """
    fields = {}
    for label, val in _DECOMP_FIELD_RE.findall(resp or ""):
        fields[label] = val.strip()

    if fields:
        p1 = fields.get("P1", "None")
        p2 = fields.get("P2", "None")
        c  = fields.get("C",  "None")
        return f"P1=[{p1}], P2=[{p2}], C=[{c}]"

    # Fallback: if the last line already contains the canonical string
    tail = _extract_final(resp)
    if "P1=" in tail and "C=" in tail:
        return tail
    return None

def _parse_decomposition(decomp_line: str) -> tuple[str | None, str | None, str | None]:
    """
    Parses: P1=[p1], P2=[p2], C=[c]
    Returns (p1, p2, c) with 'None' coerced to None.
    """
    # very lightweight parse without regex backtracking headaches
    parts = {seg.split("=", 1)[0].strip(): seg.split("=", 1)[1].strip()
             for seg in decomp_line.split(",") if "=" in seg}

    def unbracket(s: str | None) -> str | None:
        if not s: return None
        s = s.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1].strip()
        return None if s == "None" else s

    p1 = unbracket(parts.get("P1"))
    p2 = unbracket(parts.get("P2"))
    c = unbracket(parts.get("C"))
    return p1, p2, c

def _compose_prompt(c: str, s1: str, s2: str) -> str:
    """
    Build a prompt for the final composition solve: C(s1, s2).
    We pass the original problem, the composition description, and the sub-solutions.
    """
    return (
        f"Solve C(S1, S2) such that C={c}, S1={s1}, S2={s2}"
    )

def _solve_atomic(problem: str) -> str:
    """Single call to thinking_module_bench; returns the full agent response."""
    return call_agent(thinking_module_bench_agent_session, problem)

def solve(problem: str, depth: int = 0, max_depth: int = MAX_DEPTH) -> str:
    """
    Recursive solver:
      - Try decompose & recurse (up to max_depth)
      - If decomposition is absent/disabled/unhelpful, fall back to atomic solve
    Returns the final agent response (which includes the {FINAL_TOKEN} line).
    """
    logging.info(f"[solve] depth={depth} problem: {problem[:120]}{'...' if len(problem) > 120 else ''}")

    if depth >= max_depth:
        logging.info(f"[solve] depth={depth} -> atomic (no decomp or max depth)")
        return _solve_atomic(problem)

    p1, p2, c = decompose(problem)

    # No decomposition (or explicitly None)
    if not p1 or not p2 or not c:
        logging.info(f"[solve] depth={depth} -> atomic (no decomp or max depth)")
        return _solve_atomic(problem)

    logging.info(f"[solve] depth={depth} using decomposition")

    # Recurse on sub-problems
    s1_resp = solve(p1, depth + 1, max_depth)
    s2_resp = solve(p2, depth + 1, max_depth)

    # Extract final lines to feed into composition step
    s1 = _extract_final(s1_resp)
    s2 = _extract_final(s2_resp)

    logging.info(f"[solve] depth={depth} sub-answers -> s1_final={s1!r}, s2_final={s2!r}")

    # Compose using thinking_module_bench
    comp_prompt = _compose_prompt(c, s1, s2)
    logging.info(f"[solve] depth={depth} composing with C={c!r}")

    # Generate multiple composed solutions
    solutions: list[str] = []
    finals: list[str] = []
    for k in range(SOLUTION_CANDIDATE_COUNT):
        r = call_agent(thinking_module_bench_agent_session, comp_prompt)
        solutions.append(r)
        finals.append(_extract_final(r))
        logging.info(f"[solve] depth={depth} composed candidate {k + 1}: {finals[-1]!r}")

    # Vote among composed solutions using composition_discriminator
    numbered = "\n".join(f"{i + 1}. {ans}" for i, ans in enumerate(finals))
    votes = [0] * len(finals)
    winner_idx = None
    for _ in range(NUMBER_OF_VOTES):  # reuse existing vote knobs
        vresp = call_agent(composition_discriminator_agent_session, f"{numbered}\n\n")
        vote_txt = _extract_final(vresp)
        logging.info(f"[solve] depth={depth} solution vote: {vote_txt}")
        try:
            idx = int(vote_txt) - 1
            if 0 <= idx < len(finals):
                votes[idx] += 1
                logging.info(f"[solve] depth={depth} tally: {votes}")
                if votes[idx] >= WINNING_VOTE_COUNT:
                    winner_idx = idx
                    logging.info(f"[solve] depth={depth} early solution winner: {winner_idx + 1}")
                    break
        except ValueError:
            logging.warning(f"[solve] depth={depth} malformed vote ignored: {vote_txt!r}")

    if winner_idx is None:
        winner_idx = max(range(len(votes)), key=lambda i: votes[i])

    resp = solutions[winner_idx]
    logging.info(f"[solve] depth={depth} composed final (chosen): {finals[winner_idx]!r}")
    return resp


def decompose(problem: str) -> tuple[str | None, str | None, str | None]:
    """
    Collect CANDIDATE_COUNT decompositions from the 'decomposer' agent,
    then run a voting round via 'solution_discriminator'. Returns (p1, p2, c).
    """
    # 1) Gather candidates
    candidates: list[str] = []
    for _ in range(CANDIDATE_COUNT):
        resp = call_agent(decomposer_agent_session, problem)
        cand = _extract_decomposition_text(resp)  # expect "P1=[...], P2=[...], C=[...]"
        if cand:
            candidates.append(cand)

    for i, c in enumerate(candidates, 1):
        logging.info(f"[decompose] candidate {i}: {c}")

    if not candidates:
        return None, None, None

    # Numbered list for the discriminator
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(candidates))

    # 2) Voting
    votes = [0] * len(candidates)
    winner_idx = None
    for _ in range(NUMBER_OF_VOTES):
        disc_prompt = (
            f"{numbered}\n\n"
        )
        vresp = call_agent(solution_discriminator_agent_session, disc_prompt)
        vote_txt = _extract_final(vresp)
        logging.info(f"[decompose] discriminator raw vote: {vote_txt}")
        try:
            idx = int(vote_txt) - 1
            if 0 <= idx < len(candidates):
                votes[idx] += 1
                logging.info(f"[decompose] tally: {votes}")
                if votes[idx] >= WINNING_VOTE_COUNT:
                    winner_idx = idx
                    logging.info(f"[decompose] early winner: {winner_idx + 1}")
                    break
        except ValueError:
            logging.warning(f"[decompose] malformed vote ignored: {vote_txt!r}")

    if winner_idx is None:
        # choose argmax (first tie-winner)
        winner_idx = max(range(len(votes)), key=lambda v: votes[v])

    logging.info(f"[decompose] final winner: {winner_idx + 1} -> {candidates[winner_idx]}")

    p1, p2, c = _parse_decomposition(candidates[winner_idx])
    return p1, p2, c


def main():
    # Read the full prompt (problem) from stdin
    problem = sys.stdin.read().strip()
    if not problem:
        print("[ERROR] No input provided.", file=sys.stderr)
        sys.exit(1)

    final_resp = solve(problem, depth=0, max_depth=MAX_DEPTH)

    # Print EXACTLY what the benchmark runner should capture; include the agent’s full response
    # (which is expected to end with the final line containing the FINAL_TOKEN).
    logging.info(f"[main] final answer: {_extract_final(final_resp)!r}")
    print(final_resp)

if __name__ == "__main__":
    main()
