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
"""
Rule engine for Experiment 1.

Parses each URE flowchart (from all_flowcharts.json) into a directed graph and
simulates a case's answers through it to predict a terminal outcome
(STANDARD vs REFER) and the path taken.

Honesty rule: when an answer is missing or a condition cannot be evaluated from
the available data, the walk is marked "indeterminate" rather than guessed.
"""

import logging
import re
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

logger = logging.getLogger(__name__)


# Answer-string -> condition-token synonyms. Edge labels use enum-like tokens
# (YES/NO/INC/SAME/DEC/IP/AIP/BE/TPD/LIFE/CI/...), while case answers are
# human strings. We only assert a match we are reasonably confident about;
# anything else stays unknown (-> indeterminate), never guessed.
_ANSWER_SYNONYMS: Dict[str, List[str]] = {
    "yes": ["YES"],
    "no": ["NO"],
    "increase": ["INC", "UP", "UPHOURS", "UP_COMMS", "UP_CONTRACT"],
    "decrease": ["DEC"],
    "staythesame": ["SAME"],
    "stay the same": ["SAME"],
    "same": ["SAME"],
    "bonus": ["BONUS"],
    "leave": ["LEAVE"],
    "contractor": ["CONTRACT", "CHANGE_OCC"],
    "employee": ["EE"],
    "selfemployed": ["SE"],
}

# Tokens that mark a terminal decision node.
_TERMINAL_KEYWORDS = ("STANDARD", "REFER")


def _norm_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


class FlowGraph:
    """In-memory directed graph for a single flowchart."""

    def __init__(self, flow_name: str, spec: Dict[str, Any]):
        self.flow_name = flow_name
        self.nodes: Dict[str, Dict[str, Any]] = {n["id"]: n for n in spec.get("nodes", [])}
        self.edges: List[Dict[str, Any]] = list(spec.get("edges", []))
        self.adjacency: Dict[str, List[Dict[str, Any]]] = {}
        for edge in self.edges:
            self.adjacency.setdefault(edge.get("from"), []).append(edge)
        self.start_node = self._find_start()

    def _find_start(self) -> Optional[str]:
        if "n1" in self.nodes:
            return "n1"
        targets = {e.get("to") for e in self.edges}
        for node_id in self.nodes:
            if node_id not in targets:
                return node_id
        return next(iter(self.nodes), None)

    def label(self, node_id: str) -> str:
        return self.nodes.get(node_id, {}).get("label", "")

    def is_terminal(self, node_id: str) -> Optional[str]:
        """Return 'STANDARD'/'REFER' if node is a terminal, else None."""
        node = self.nodes.get(node_id, {})
        label = node.get("label", "")
        upper = label.upper()
        if "STANDARD" in upper:
            return "STANDARD"
        if "REFER" in upper:
            return "REFER"
        # A node typed 'terminal' but without STANDARD/REFER wording.
        if node.get("type") == "terminal":
            return "STANDARD" if "STANDARD" in upper else "REFER" if "REFER" in upper else None
        return None


def build_graphs(flowcharts: Dict[str, Any]) -> Dict[str, FlowGraph]:
    """Parse every flowchart into a FlowGraph."""
    return {name: FlowGraph(name, spec) for name, spec in flowcharts.items()}


def _answer_matches_token(answer: Optional[str], token: str) -> Optional[bool]:
    """
    Return True/False if we can decide whether an answer matches a condition
    token, or None if we cannot evaluate it from the data.
    """
    if answer is None:
        return None
    ans_raw = str(answer).strip()
    if ans_raw == "" or ans_raw.lower() in ("none", "none of these"):
        return None
    ans_norm = _norm_token(ans_raw)
    tok_norm = _norm_token(token)
    if not tok_norm:
        return None
    # direct normalized equality / containment
    if ans_norm == tok_norm:
        return True
    # synonym table (keyed by simplified answer text)
    syn_key = re.sub(r"[^a-z ]", "", ans_raw.lower()).strip()
    for key, tokens in _ANSWER_SYNONYMS.items():
        if key in syn_key or syn_key in key:
            if token.upper() in tokens:
                return True
    # We cannot positively confirm a match -> unknown rather than False,
    # so the walk can record this branch as indeterminate.
    return None


def _evaluate_condition(label: str, answers: Dict[str, str], node_label: str) -> Optional[bool]:
    """
    Evaluate an edge condition label against the case answers.

    Returns:
      True  -> condition satisfied
      False -> condition definitively not satisfied
      None  -> cannot be evaluated from available data (indeterminate)
    """
    cond = label.strip()
    answer = answers.get(node_label)

    # Fallbacks are handled by the caller, but be defensive.
    if cond in ("always", "else"):
        return True

    # is in [A, B, C] / is not in [A, B, C]
    m = re.match(r"is\s+(not\s+)?in\s*\[(.*)\]", cond, flags=re.IGNORECASE)
    if m:
        negate = bool(m.group(1))
        tokens = [t.strip() for t in m.group(2).split(",") if t.strip()]
        results = [_answer_matches_token(answer, tok) for tok in tokens]
        if any(r is True for r in results):
            # Answer is a member of the set.
            return not negate
        # If every token evaluated to None (unknown), we cannot decide.
        if all(r is None for r in results):
            return None
        # All tokens known and none matched -> answer is not a member.
        return True if negate else False

    # is = X  /  is BE
    m = re.match(r"is\s*=\s*(.+)", cond, flags=re.IGNORECASE)
    if m:
        return _answer_matches_token(answer, m.group(1).strip())
    m = re.match(r"is\s+([A-Za-z_]+)\s*$", cond)
    if m:
        return _answer_matches_token(answer, m.group(1).strip())

    # it <= 10 / it > 10  (numeric on the node's own answer)
    m = re.match(r"it\s*(<=|>=|<|>|==)\s*(-?\d+(?:\.\d+)?)", cond)
    if m:
        num = _to_number(answer)
        if num is None:
            return None
        return _num_compare(num, m.group(1), float(m.group(2)))

    # EARNINGS < (PREVIOUS_EARNINGS_SE * 85 / 100)  etc.
    m = re.match(r"EARNINGS\s*(<=|>=|<|>)\s*\((.+)\)", cond)
    if m:
        earnings = _to_number(answers.get("EARNINGS"))
        rhs = _evaluate_earnings_rhs(m.group(2), answers)
        if earnings is None or rhs is None:
            return None
        return _num_compare(earnings, m.group(1), rhs)

    # is.industry and any other unrecognised expression -> cannot evaluate.
    return None


def _to_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _num_compare(left: float, op: str, right: float) -> bool:
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    if op == "==":
        return left == right
    return False


def _evaluate_earnings_rhs(expr: str, answers: Dict[str, str]) -> Optional[float]:
    """Evaluate something like 'PREVIOUS_EARNINGS_SE * 85 / 100'."""
    var = re.search(r"PREVIOUS_EARNINGS_[A-Z]+", expr)
    if not var:
        return None
    base = _to_number(answers.get(var.group(0)))
    if base is None:
        return None
    nums = re.findall(r"\*\s*([\d.]+)|/\s*([\d.]+)", expr)
    value = base
    for mul, div in nums:
        if mul:
            value *= float(mul)
        if div:
            value /= float(div)
    return value


def simulate(graph: FlowGraph, answers: Dict[str, str], max_steps: int = 64) -> Dict[str, Any]:
    """
    Walk the flowchart from its start node using a case's answers.

    `answers` maps a node label (== case question `definition`) to its answer.

    Returns:
      {
        outcome: "STANDARD" | "REFER" | "indeterminate",
        path: [node_id, ...],
        path_labels: [label, ...],
        terminal_node: node_id or None,
        reason: str,
      }
    """
    path: List[str] = []
    path_labels: List[str] = []
    current = graph.start_node
    if current is None:
        return {
            "outcome": "indeterminate",
            "path": [],
            "path_labels": [],
            "terminal_node": None,
            "reason": "flowchart has no nodes",
        }

    visited = set()
    for _ in range(max_steps):
        path.append(current)
        path_labels.append(graph.label(current))

        terminal = graph.is_terminal(current)
        if terminal:
            return {
                "outcome": terminal,
                "path": path,
                "path_labels": path_labels,
                "terminal_node": current,
                "reason": f"reached terminal node {current} ({graph.label(current)})",
            }

        if current in visited:
            return {
                "outcome": "indeterminate",
                "path": path,
                "path_labels": path_labels,
                "terminal_node": None,
                "reason": f"cycle detected at node {current}",
            }
        visited.add(current)

        node_label = graph.label(current)
        out_edges = graph.adjacency.get(current, [])
        if not out_edges:
            return {
                "outcome": "indeterminate",
                "path": path,
                "path_labels": path_labels,
                "terminal_node": None,
                "reason": f"node {current} has no outgoing edges and is not terminal",
            }

        conditional = [e for e in out_edges if e.get("label", "").strip() not in ("always", "else")]
        fallback = [e for e in out_edges if e.get("label", "").strip() in ("always", "else")]

        chosen = None
        any_unknown = False
        for edge in conditional:
            result = _evaluate_condition(edge.get("label", ""), answers, node_label)
            if result is True:
                chosen = edge
                break
            if result is None:
                any_unknown = True

        if chosen is None:
            if any_unknown and not fallback:
                # We could not evaluate the branch and there is no safe default.
                return {
                    "outcome": "indeterminate",
                    "path": path,
                    "path_labels": path_labels,
                    "terminal_node": None,
                    "reason": (
                        f"cannot evaluate condition at node {current} "
                        f"('{node_label}'); answer missing or unmappable"
                    ),
                }
            if fallback:
                chosen = fallback[0]
            elif conditional and not any_unknown:
                # All conditions known-false and no fallback -> dead end.
                return {
                    "outcome": "indeterminate",
                    "path": path,
                    "path_labels": path_labels,
                    "terminal_node": None,
                    "reason": f"no satisfied branch at node {current} ('{node_label}')",
                }
            else:
                return {
                    "outcome": "indeterminate",
                    "path": path,
                    "path_labels": path_labels,
                    "terminal_node": None,
                    "reason": f"no traversable edge at node {current}",
                }

        current = chosen.get("to")
        if current is None or current not in graph.nodes:
            return {
                "outcome": "indeterminate",
                "path": path,
                "path_labels": path_labels,
                "terminal_node": None,
                "reason": f"edge points to unknown node '{current}'",
            }

    return {
        "outcome": "indeterminate",
        "path": path,
        "path_labels": path_labels,
        "terminal_node": None,
        "reason": "exceeded max traversal steps",
    }


def answers_from_case(case: Dict[str, Any]) -> Dict[str, str]:
    """
    Build the node-label -> answer map a case provides. The case question
    `definition` field aligns with flowchart node labels.
    """
    answers: Dict[str, str] = {}
    for question in case.get("questions", []):
        definition = question.get("definition")
        answer = question.get("answer")
        if definition is not None and answer is not None and definition not in answers:
            answers[definition] = answer
    return answers


# ---------------------------------------------------------------------------
# NeuroSan CodedTool wrapper
# ---------------------------------------------------------------------------
try:  # pragma: no cover
    from neuro_san.interfaces.coded_tool import CodedTool
except Exception:  # noqa: BLE001

    class CodedTool:  # type: ignore
        """Fallback base when neuro_san is unavailable."""


class RuleEngineTool(CodedTool):
    """
    CodedTool entrypoint that simulates a single case (by enquiry_id or by
    explicit flow + answers) through the URE flowchart graph.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        from . import data_access  # local import to avoid hard dependency at import time

        flowcharts = sly_data.get("ure_flowcharts") or data_access.load_flowcharts()
        graphs = build_graphs(flowcharts)
        matcher = data_access.FlowMatcher(flowcharts)

        flow_name = args.get("flow")
        answers = args.get("answers")

        if flow_name is None or answers is None:
            cases = sly_data.get("ure_cases") or data_access.load_cases()
            enquiry_id = args.get("enquiry_id")
            case = next((c for c in cases if c.get("enquiry_id") == enquiry_id), None)
            if case is None and cases:
                case = cases[0]
            if case is None:
                return {"error": "no case available to simulate"}
            flow_name = flow_name or matcher.match_case(case)[0]
            answers = answers if answers is not None else answers_from_case(case)

        if flow_name not in graphs:
            return {"error": f"flow '{flow_name}' not found in flowcharts"}

        result = simulate(graphs[flow_name], answers)
        result["flow"] = flow_name
        return result

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.invoke(args, sly_data)
