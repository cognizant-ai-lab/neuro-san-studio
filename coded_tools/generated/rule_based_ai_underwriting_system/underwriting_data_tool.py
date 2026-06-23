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
Grounded data layer for Experiment 2 (AI Underwriter pipeline).

Loads the THREE real source files that live in this same folder and exposes
read-only, deterministic operations the agent network grounds on. Nothing in
this module fabricates data and nothing is ever written to disk.

The three (and only three) data inputs are:
  - all_flowcharts.json      Decision-tree rule base (nodes + edges per flow).
  - desicion_question.json   500 underwriting cases (note the intentional
                             misspelling of the filename in the source data),
                             each with questions[] and historical decisions[].
  - question_wording.json    Human-readable wording for explainability.

Join keys (relied upon, never invented):
  - A case question's `question_line_name` matches a flowchart name stem in
    all_flowcharts.json (with normalization + fuzzy matching).
  - A question's `tag` links to question_wording.json: tag -> question_line_name
    -> definition -> [{question_text, question_help_text}].
  - Historical decisions use codes DECISION_TPD, DECISION_IP_3, DECISION_IP_4,
    DECISION_IP_13 with a decision_value (e.g. STANDARD / REFER / a number).
"""

import difflib
import json
import logging
import os
import re
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

logger = logging.getLogger(__name__)

# Directory that holds the three real source files (this same folder).
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

FLOWCHARTS_FILE = "all_flowcharts.json"
# The source filename is intentionally misspelled ("desicion"). We honour the
# real filename and also accept the correctly-spelled variant if it ever exists.
DECISION_QUESTION_FILE = "desicion_question.json"
DECISION_QUESTION_FILE_ALT = "decision_question.json"
QUESTION_WORDING_FILE = "question_wording.json"

# Words that mark a flowchart terminal/decision outcome.
_OUTCOME_KEYWORDS = ("STANDARD", "REFER", "DECLINE")
_DECISION_CODE_RE = re.compile(r"DECISION_[A-Z0-9_]+")


# ---------------------------------------------------------------------------
# Low-level loaders (read-only)
# ---------------------------------------------------------------------------
def _read_json(path: str) -> Any:
    """Read a JSON file, raising a clear error if it is missing."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required data file not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_flowcharts(data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """Load all_flowcharts.json -> {flow_name: {nodes:[...], edges:[...]}}."""
    return _read_json(os.path.join(data_dir, FLOWCHARTS_FILE))


def load_cases(data_dir: str = DATA_DIR) -> List[Dict[str, Any]]:
    """Load the (misspelled) desicion_question.json and return the case list."""
    path = os.path.join(data_dir, DECISION_QUESTION_FILE)
    if not os.path.exists(path):
        alt = os.path.join(data_dir, DECISION_QUESTION_FILE_ALT)
        if os.path.exists(alt):
            path = alt
    payload = _read_json(path)
    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    return cases


def load_wording(data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """Load question_wording.json -> {tag: {question_line_name: {definition: [...]}}}."""
    return _read_json(os.path.join(data_dir, QUESTION_WORDING_FILE))


# ---------------------------------------------------------------------------
# Name normalization / fuzzy stem matching
# ---------------------------------------------------------------------------
def flowchart_stem(name: Optional[str]) -> str:
    """
    Strip the "Jun 2026 - " prefix and the ".pdf" suffix, returning the readable
    stem used for rule_ids and citations (e.g. "Occupation_Contractor").
    """
    if not name:
        return ""
    text = re.sub(r"^\s*Jun\s*2026\s*-\s*", "", str(name))
    text = re.sub(r"\.pdf\s*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def canonicalize_line_name(name: Optional[str]) -> str:
    """
    Normalize a line / flow name so inconsistent, truncated variants collapse to
    a comparable token: drop the prefix/suffix, lowercase, strip non-alphanumerics.

    Examples:
      "Jun 2026 - Occupation_Contractor.pdf" -> "occupationcontractor"
      "Occupation_WorkingContinuous"         -> "occupationworkingcontinuous"
    """
    stem = flowchart_stem(name)
    return re.sub(r"[^a-z0-9]", "", stem.lower())


class FlowMatcher:
    """
    Maps inconsistent case `question_line_name` values to flowchart names using
    canonicalization plus difflib fuzzy matching (cutoff ~0.8). Unmatched names
    are logged, never guessed.
    """

    def __init__(self, flowcharts: Dict[str, Any], cutoff: float = 0.8):
        self.flowcharts = flowcharts
        self.cutoff = cutoff
        # canonical token -> original flow name (deterministic order)
        self.canon_to_flow: Dict[str, str] = {}
        for flow_name in sorted(flowcharts):
            self.canon_to_flow[canonicalize_line_name(flow_name)] = flow_name
        self._canon_keys = sorted(self.canon_to_flow.keys())

    def match(self, line_name: Optional[str]) -> Optional[str]:
        """Return the best-matching flowchart name for a line-name, or None."""
        canon = canonicalize_line_name(line_name)
        if not canon:
            return None
        # 1) exact canonical match
        if canon in self.canon_to_flow:
            return self.canon_to_flow[canon]
        # 2) fuzzy match against the flow canonical keys
        close = difflib.get_close_matches(canon, self._canon_keys, n=1, cutoff=self.cutoff)
        if close:
            return self.canon_to_flow[close[0]]
        logger.warning("No flowchart matched question_line_name '%s' (canonical '%s')", line_name, canon)
        return None


# ---------------------------------------------------------------------------
# Rule-base extraction from flowcharts
# ---------------------------------------------------------------------------
def _decision_outcome(label: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
    """
    If a node label encodes a terminal outcome (e.g. "STANDARD to DECISION_BE +"),
    return {outcome, decision_code}. Otherwise return None.
    """
    if not label:
        return None
    upper = label.upper()
    outcome = next((kw for kw in _OUTCOME_KEYWORDS if kw in upper), None)
    if not outcome:
        return None
    code_match = _DECISION_CODE_RE.search(upper)
    return {"outcome": outcome, "decision_code": code_match.group(0) if code_match else None}


def extract_rules(flow_name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a single flowchart into a normalized rule object set.

    Each node becomes a rule carrying its question/condition (label + description),
    the labelled edges leaving it (branch logic), and any terminal decision outcome.
    rule_id is deterministic: "<stem>-<node_id>". flow_name is the manual citation.
    """
    stem = flowchart_stem(flow_name)
    nodes = list(spec.get("nodes", []))
    edges = list(spec.get("edges", []))

    outgoing: Dict[str, List[Dict[str, Any]]] = {}
    for edge in edges:
        outgoing.setdefault(edge.get("from"), []).append(edge)

    node_label = {n.get("id"): n.get("label") for n in nodes}
    targets = {e.get("to") for e in edges}
    start_node = "n1" if any(n.get("id") == "n1" for n in nodes) else None
    if start_node is None:
        for node in nodes:
            if node.get("id") not in targets:
                start_node = node.get("id")
                break

    rules: List[Dict[str, Any]] = []
    for node in sorted(nodes, key=lambda n: str(n.get("id"))):
        node_id = node.get("id")
        branches = [
            {
                "to": e.get("to"),
                "to_label": node_label.get(e.get("to")),
                "condition": e.get("label"),
            }
            for e in sorted(outgoing.get(node_id, []), key=lambda e: (str(e.get("label")), str(e.get("to"))))
        ]
        outcome = _decision_outcome(node.get("label"))
        rules.append(
            {
                "rule_id": f"{stem}-{node_id}",
                "node_id": node_id,
                "label": node.get("label"),
                "type": node.get("type"),
                "description": node.get("description"),
                "is_terminal": not branches,
                "decision_outcome": outcome,
                "branches": branches,
            }
        )

    return {
        "flowchart_name": flow_name,
        "stem": stem,
        "start_node": start_node,
        "rule_count": len(rules),
        "rules": rules,
    }


def load_rules(data_dir: str = DATA_DIR, flowchart_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse all_flowcharts.json into a normalized rule set. If `flowchart_name` is
    given, return only the matching flow (resolved via the fuzzy matcher).
    """
    flowcharts = load_flowcharts(data_dir)
    matcher = FlowMatcher(flowcharts)

    if flowchart_name:
        resolved = flowchart_name if flowchart_name in flowcharts else matcher.match(flowchart_name)
        if not resolved or resolved not in flowcharts:
            return {
                "requested": flowchart_name,
                "resolved": None,
                "error": "FLOWCHART_NOT_FOUND",
                "available_flowcharts": sorted(flowcharts.keys()),
            }
        selected = {resolved: flowcharts[resolved]}
    else:
        selected = flowcharts

    flow_rules = [extract_rules(name, selected[name]) for name in sorted(selected)]
    return {
        "flowchart_count": len(flow_rules),
        "total_rules": sum(fr["rule_count"] for fr in flow_rules),
        "flowcharts": flow_rules,
    }


# ---------------------------------------------------------------------------
# Case access
# ---------------------------------------------------------------------------
def _index_cases(cases: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """enquiry_id -> case (first occurrence wins, deterministic)."""
    index: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        enquiry_id = case.get("enquiry_id")
        if enquiry_id and enquiry_id not in index:
            index[enquiry_id] = case
    return index


def list_cases(data_dir: str = DATA_DIR, limit: Optional[int] = None) -> Dict[str, Any]:
    """Return the case count and a sorted list of enquiry_ids."""
    cases = load_cases(data_dir)
    enquiry_ids = sorted({c.get("enquiry_id") for c in cases if c.get("enquiry_id")})
    shown = enquiry_ids[:limit] if limit and limit > 0 else enquiry_ids
    return {"case_count": len(cases), "enquiry_ids": shown}


def get_case(enquiry_id: str, data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """
    Return one case's questions and historical decisions (ground truth), plus a
    map from each question's question_line_name to its matched flowchart.
    """
    cases = load_cases(data_dir)
    case = _index_cases(cases).get(enquiry_id)
    if case is None:
        return {"enquiry_id": enquiry_id, "found": False, "error": "CASE_NOT_FOUND"}

    matcher = FlowMatcher(load_flowcharts(data_dir))
    line_to_flow: Dict[str, Optional[str]] = {}
    unmatched: List[str] = []
    for question in case.get("questions", []):
        line_name = question.get("question_line_name")
        if line_name is None or line_name in line_to_flow:
            continue
        flow = matcher.match(line_name)
        line_to_flow[line_name] = flow
        if flow is None:
            unmatched.append(line_name)

    return {
        "enquiry_id": enquiry_id,
        "found": True,
        "questions": case.get("questions", []),
        "decisions": case.get("decisions", []),
        "question_line_flow_map": dict(sorted(line_to_flow.items())),
        "unmatched_question_line_names": sorted(set(unmatched)),
    }


# ---------------------------------------------------------------------------
# Explainability wording
# ---------------------------------------------------------------------------
def get_wording(tag: str, question_line_name: str, data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """
    Return the wording entries for a (tag, question_line_name) pair:
    {definition: [{question_text, question_help_text}, ...]}.
    """
    wording = load_wording(data_dir)
    by_line = wording.get(tag) if isinstance(wording, dict) else None
    if not isinstance(by_line, dict) or question_line_name not in by_line:
        return {
            "tag": tag,
            "question_line_name": question_line_name,
            "found": False,
            "available_tags": sorted(wording.keys()) if isinstance(wording, dict) else [],
        }
    return {
        "tag": tag,
        "question_line_name": question_line_name,
        "found": True,
        "wording": by_line[question_line_name],
    }


def unmatched_line_names(data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """
    Audit helper: list distinct case question_line_names that do NOT map to any
    flowchart, plus the ones that do. Used for grounding diagnostics.
    """
    cases = load_cases(data_dir)
    matcher = FlowMatcher(load_flowcharts(data_dir))
    matched: Dict[str, str] = {}
    unmatched: List[str] = []
    distinct = sorted({q.get("question_line_name") for c in cases for q in c.get("questions", []) if q.get("question_line_name")})
    for line_name in distinct:
        flow = matcher.match(line_name)
        if flow:
            matched[line_name] = flow
        else:
            unmatched.append(line_name)
    return {
        "distinct_question_line_names": distinct,
        "matched": dict(sorted(matched.items())),
        "unmatched": sorted(unmatched),
    }


# ---------------------------------------------------------------------------
# NeuroSan CodedTool wrapper
# ---------------------------------------------------------------------------
try:  # pragma: no cover - optional dependency for standalone runs
    from neuro_san.interfaces.coded_tool import CodedTool
except Exception:  # noqa: BLE001 - allow standalone, dependency-free execution

    class CodedTool:  # type: ignore
        """Minimal fallback so this module runs without neuro_san installed."""


class UnderwritingDataTool(CodedTool):
    """
    CodedTool entrypoint for the grounded underwriting pipeline.

    Routes on the `operation` argument and returns only values derived from the
    three real source files:
      - load_rules     (optional flowchart_name)
      - list_cases     (optional limit)
      - get_case       (enquiry_id)
      - get_wording    (tag, question_line_name)
      - unmatched_line_names
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        data_dir = args.get("data_dir") or DATA_DIR
        operation = (args.get("operation") or "load_rules").strip()

        if operation == "load_rules":
            result = load_rules(data_dir, args.get("flowchart_name"))
        elif operation == "list_cases":
            limit = args.get("limit")
            try:
                limit = int(limit) if limit is not None else None
            except (TypeError, ValueError):
                limit = None
            result = list_cases(data_dir, limit)
        elif operation == "get_case":
            enquiry_id = args.get("enquiry_id")
            if not enquiry_id:
                return {"error": "MISSING_ENQUIRY_ID", "operation": operation}
            result = get_case(str(enquiry_id), data_dir)
        elif operation == "get_wording":
            tag = args.get("tag")
            line_name = args.get("question_line_name")
            if not tag or not line_name:
                return {"error": "MISSING_TAG_OR_LINE_NAME", "operation": operation}
            result = get_wording(str(tag), str(line_name), data_dir)
        elif operation == "unmatched_line_names":
            result = unmatched_line_names(data_dir)
        else:
            return {
                "error": "UNKNOWN_OPERATION",
                "operation": operation,
                "supported": ["load_rules", "list_cases", "get_case", "get_wording", "unmatched_line_names"],
            }

        # Stash grounding artifacts for downstream agents in the same run.
        sly_data["uw_data_dir"] = data_dir
        sly_data["uw_last_operation"] = operation
        return result

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.invoke(args, sly_data)


# ---------------------------------------------------------------------------
# Standalone sanity check (PRINTS only — never writes)
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    rules = load_rules(DATA_DIR)
    cases = list_cases(DATA_DIR)
    audit = unmatched_line_names(DATA_DIR)

    print("=== underwriting_data_tool sanity check ===")
    print(f"Flowcharts loaded : {rules['flowchart_count']} (expected 9)")
    print(f"Total rules       : {rules['total_rules']}")
    for fr in rules["flowcharts"]:
        print(f"  - {fr['stem']:<28} rules={fr['rule_count']:<3} start={fr['start_node']}")
    print(f"Cases loaded      : {cases['case_count']} (expected 500)")
    print(f"Distinct line names: {len(audit['distinct_question_line_names'])}")
    print(f"Matched line names : {sorted(audit['matched'].keys())}")
    print(f"UNMATCHED line names (logged, not guessed): {audit['unmatched']}")

    sample_id = cases["enquiry_ids"][0]
    case = get_case(sample_id, DATA_DIR)
    print(f"Sample case        : {sample_id}")
    print(f"  questions={len(case['questions'])} decisions={len(case['decisions'])}")
    print(f"  line->flow map: {json.dumps(case['question_line_flow_map'], indent=2)}")
