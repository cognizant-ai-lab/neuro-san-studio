import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

from neuro_san.client.agent_session_factory import AgentSession
from neuro_san.client.agent_session_factory import AgentSessionFactory
from neuro_san.client.streaming_input_processor import StreamingInputProcessor

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=LOG_LEVEL, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger()

LOG_DIR = os.getenv("LOG_DIR")
if LOG_DIR:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    log_file = Path(LOG_DIR) / f"mr_{os.getpid()}_{threading.get_ident()}_{int(time.time())}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)
    logging.info(f"Logging to {log_file}")

_DECOMP_FIELD_RE = re.compile(r"(P1|P2|C)\s*=\s*\[(.*?)]", re.DOTALL)

os.environ["AGENT_MANIFEST_FILE"] = "apps/benchmarking/manifest_solver.hocon"
os.environ["AGENT_TOOL_PATH"] = "coded_tools"

FINAL_TOKEN = os.getenv("FINAL_TOKEN", "vote:")  # agents end their final answer on the last line after this token

# Tuning knobs with environment variable overrides
MAX_DEPTH = int(os.getenv("MAX_DEPTH", "5"))
WINNING_VOTE_COUNT = int(os.getenv("WINNING_VOTE_COUNT", "2"))
CANDIDATE_COUNT = (2 * WINNING_VOTE_COUNT) - 1
NUMBER_OF_VOTES = (2 * WINNING_VOTE_COUNT) - 1
SOLUTION_CANDIDATE_COUNT = (2 * WINNING_VOTE_COUNT) - 1

LOG_FAILURES_JSONL = os.getenv("LOG_FAILURES_JSONL")

AGENTS_PORT = 30011

_trace_data = threading.local()

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
                "direct", agent_name, "localhost", AGENTS_PORT, False, {"user_id": os.environ.get("USER")}
            )
            _sessions[agent_name] = sess
        return sess


def decomposer_session() -> AgentSession:
    return _get_session("decomposer")


def solution_discriminator_session() -> AgentSession:
    return _get_session("solution_discriminator")


def composition_discriminator_session() -> AgentSession:
    return _get_session("composition_discriminator")


def problem_solver_session() -> AgentSession:
    return _get_session("problem_solver")


# Unique temp file per *call*
def _tmpfile(stem: str) -> str:
    return f"/tmp/{stem}_{os.getpid()}_{threading.get_ident()}.txt"


def call_agent(agent_session: AgentSession, text: str, timeout_ms: float = 100000.0) -> str:
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
    inp = StreamingInputProcessor("DEFAULT", _tmpfile("program_mode_thinking"), agent_session, None)
    thread = inp.process_once(thread)
    logging.debug(f"call_agent({agent_session}): sending {len(text)} chars")
    resp = thread.get("last_chat_response") or ""
    logging.debug(f"call_agent({agent_session}): received {len(resp)} chars")
    return resp


def _parse_number(text: str) -> int | None:
    """Extract and parse a number from text, stripping commas/spaces/underscores."""
    if not text:
        return None
    cleaned = text.strip().replace(",", "").replace("_", "").replace(" ", "")
    try:
        return int(cleaned)
    except ValueError:
        numbers = re.findall(r"\d+", cleaned)
        if numbers:
            try:
                return int(max(numbers, key=len))
            except ValueError:
                pass
    return None


def _extract_final(text: str, token: str = FINAL_TOKEN) -> str:
    """Return the text after the last occurrence of token (case-insensitive),
    or the last non-empty line if not found. Preserves original casing."""
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    tkn = (token or "").strip()
    if not tkn:
        return lines[-1]

    tkn_lower = tkn.lower()
    for ln in reversed(lines):
        # Find LAST occurrence of token in this line (case-insensitive)
        idx = ln.lower().rfind(tkn_lower)
        if idx != -1:
            return ln[idx + len(tkn) :].strip()
    return lines[-1]


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
        c = fields.get("C", "None")
        return f"P1=[{p1}], P2=[{p2}], C=[{c}]"

    # Fallback: if the last line already contains the canonical string
    tail = _extract_final(resp)
    if "P1=" in tail and "C=" in tail:
        return tail
    return None


def _extract_multiplication_problem(problem: str) -> tuple[int | None, int | None]:
    """Extract A and B from 'What is A × B?' or similar formats."""
    patterns = [
        r"What is (\d+)\s*[×x*]\s*(\d+)",
        r"(\d+)\s*[×x*]\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, problem, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1)), int(match.group(2))
            except ValueError:
                pass
    return None, None


def _classify_failure(trace: dict, expected: int, actual: int | None) -> list[str]:
    """Classify failure patterns based on trace data."""
    patterns = []

    if actual is None:
        patterns.append("malformed_final")
        return patterns

    decomp_info = trace.get("decomposition")
    if decomp_info:
        p2_text = decomp_info.get("p2", "")
        c_text = decomp_info.get("c", "")

        if p2_text and (
            "result of P1" in p2_text
            or "result of p1" in p2_text.lower()
            or "use P1" in p2_text
            or "use p1" in p2_text.lower()
        ):
            patterns.append("non_independent_subproblems")

        if c_text:
            has_add = any(word in c_text.lower() for word in ["add", "sum", "plus"])
            has_subtract = any(word in c_text.lower() for word in ["subtract", "minus", "difference"])
            if has_add and has_subtract:
                patterns.append("ambiguous_composition_op")

    solve_info = trace.get("solve")
    if solve_info:
        s1_final = solve_info.get("s1_final")
        s2_final = solve_info.get("s2_final")

        if s1_final is not None or s2_final is not None:
            patterns.append("composed_miscalc")
        else:
            patterns.append("atomic_miscalc")
    else:
        patterns.append("atomic_miscalc")

    if not patterns:
        patterns.append("unknown_failure")

    return patterns


def _parse_decomposition(decomp_line: str) -> tuple[str | None, str | None, str | None]:
    """
    Parses: P1=[p1], P2=[p2], C=[c]
    Returns (p1, p2, c) with 'None' coerced to None.
    """
    parts = {
        seg.split("=", 1)[0].strip(): seg.split("=", 1)[1].strip() for seg in decomp_line.split(",") if "=" in seg
    }

    def unbracket(s: str | None) -> str | None:
        if not s:
            return None
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
    return f"Solve C(P1, P2) such that C={c}, P1={s1}, P2={s2}"


def _solve_atomic(problem: str) -> str:
    """Single call to problem_solver; returns the full agent response."""
    return call_agent(problem_solver_session(), problem)


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

    comp_prompt = _compose_prompt(c, s1, s2)
    logging.info(f"[solve] depth={depth} composing with C={c!r}")

    solutions: list[str] = []
    finals: list[str] = []
    for k in range(SOLUTION_CANDIDATE_COUNT):
        r = call_agent(problem_solver_session(), comp_prompt)
        solutions.append(r)
        finals.append(_extract_final(r))
        logging.info(f"[solve] depth={depth} composed candidate {k + 1}: {finals[-1]}")

    numbered = "\n".join(f"{i + 1}. {ans}" for i, ans in enumerate(finals))
    numbered = f"problem: {comp_prompt}, {numbered}"
    logging.info(f"[solve] depth={depth} composition_discriminator query: {numbered}")
    votes = [0] * len(finals)
    winner_idx = None
    for _ in range(NUMBER_OF_VOTES):
        vresp = call_agent(composition_discriminator_session(), f"{numbered}\n\n")
        vote_txt = _extract_final(vresp)
        logging.info(f"[solve] depth={depth} solution vote: {vote_txt}")
        try:
            idx = int(vote_txt) - 1
            if idx >= len(finals):
                logging.error(f"Invalid solution index: {idx}")
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

    if depth == 0 and not hasattr(_trace_data, "solve"):
        _trace_data.solve = {
            "s1_final": s1,
            "s2_final": s2,
            "c": c,
            "composed_candidates": finals,
            "composition_votes": votes,
            "composition_winner_idx": winner_idx,
        }

    return resp


def decompose(problem: str) -> tuple[str | None, str | None, str | None]:
    """
    Collect CANDIDATE_COUNT decompositions from the 'decomposer' agent,
    then run a voting round via 'solution_discriminator'. Returns (p1, p2, c).
    """
    candidates: list[str] = []
    for _ in range(CANDIDATE_COUNT):
        resp = call_agent(decomposer_session(), problem)
        cand = _extract_decomposition_text(resp)
        if cand:
            candidates.append(cand)

    for i, c in enumerate(candidates, 1):
        logging.info(f"[decompose] candidate {i}: {c}")

    if not candidates:
        return None, None, None

    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(candidates))
    numbered = f"problem: {problem}, {numbered}"
    logging.info(f"[decompose] solution_discriminator query: {numbered}")

    votes = [0] * len(candidates)
    winner_idx = None
    for _ in range(NUMBER_OF_VOTES):
        disc_prompt = f"{numbered}\n\n"
        vresp = call_agent(solution_discriminator_session(), disc_prompt)
        vote_txt = _extract_final(vresp)
        logging.info(f"[decompose] discriminator raw vote: {vote_txt}")
        try:
            idx = int(vote_txt) - 1
            if idx >= len(candidates):
                logging.error(f"Invalid vote index: {idx}")
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
        winner_idx = max(range(len(votes)), key=lambda v: votes[v])

    logging.info(f"[decompose] final winner: {winner_idx + 1} -> {candidates[winner_idx]}")

    p1, p2, c = _parse_decomposition(candidates[winner_idx])

    if not hasattr(_trace_data, "decomposition"):
        _trace_data.decomposition = {}
    _trace_data.decomposition = {
        "candidates": candidates,
        "winner_idx": winner_idx,
        "votes": votes,
        "p1": p1,
        "p2": p2,
        "c": c,
    }

    return p1, p2, c


def main():
    problem = sys.stdin.read().strip()
    if not problem:
        print("[ERROR] No input provided.", file=sys.stderr)
        sys.exit(1)

    final_resp = solve(problem, depth=0, max_depth=MAX_DEPTH)

    extracted_final = _extract_final(final_resp)
    logging.info(f"[main] final answer: {extracted_final!r}")

    a, b = _extract_multiplication_problem(problem)
    if a is not None and b is not None and LOG_FAILURES_JSONL:
        expected = a * b
        actual = _parse_number(extracted_final)

        if actual != expected:
            trace = {
                "decomposition": getattr(_trace_data, "decomposition", None),
                "solve": getattr(_trace_data, "solve", None),
            }

            failure_patterns = _classify_failure(trace, expected, actual)

            failure_record = {
                "problem": problem,
                "expected": expected,
                "actual": actual,
                "extracted_final": extracted_final,
                "final_resp": final_resp,
                "failure_patterns": failure_patterns,
                "trace": trace,
                "config": {
                    "WINNING_VOTE_COUNT": WINNING_VOTE_COUNT,
                    "MAX_DEPTH": MAX_DEPTH,
                    "CANDIDATE_COUNT": CANDIDATE_COUNT,
                    "NUMBER_OF_VOTES": NUMBER_OF_VOTES,
                    "SOLUTION_CANDIDATE_COUNT": SOLUTION_CANDIDATE_COUNT,
                },
            }

            if LOG_DIR:
                failure_record["log_file"] = str(log_file) if "log_file" in locals() else None

            try:
                with open(LOG_FAILURES_JSONL, "a") as f:
                    f.write(json.dumps(failure_record) + "\n")
                logging.info(f"[main] Failure logged to {LOG_FAILURES_JSONL}")
            except Exception as e:
                logging.error(f"[main] Failed to write failure log: {e}")

    print(final_resp)


if __name__ == "__main__":
    main()
