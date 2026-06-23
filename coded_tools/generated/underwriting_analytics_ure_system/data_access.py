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
Data access layer for Experiment 1 (URE Uplift Agents).

Loads the THREE real source files that live in this same folder and provides
line-name canonicalization / fuzzy matching against the flowchart flow names.

The three (and only three) data inputs are:
  - all_flowcharts.json      URE rule logic as directed graphs.
  - desicion_question.json   500 underwriting cases (note the intentional
                             misspelling of the filename in the source data).
  - question_wording.json    human-readable question wording dictionary.

Nothing in this module fabricates data. Every value returned is derived from
those files. Where a file or field is missing, the loaders surface that fact
instead of inventing a value.
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
from typing import Tuple

logger = logging.getLogger(__name__)

# Directory that holds the three real source files (this same folder).
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

FLOWCHARTS_FILE = "all_flowcharts.json"
# The source filename is intentionally misspelled ("desicion"). We honour the
# real filename and also accept the correctly-spelled variant if it ever exists.
DECISION_QUESTION_FILE = "desicion_question.json"
DECISION_QUESTION_FILE_ALT = "decision_question.json"
QUESTION_WORDING_FILE = "question_wording.json"


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


def load_question_wording(data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """Load question_wording.json -> {tag: {question_line_name: {definition: [...]}}}."""
    return _read_json(os.path.join(data_dir, QUESTION_WORDING_FILE))


def canonicalize_line_name(name: Optional[str]) -> str:
    """
    Normalize a line / flow name so the inconsistent, truncated variants seen
    across the three files collapse to a comparable token.

    Steps:
      1) strip the "Jun 2026 - " prefix and a trailing ".pdf"
      2) lowercase
      3) remove every non-alphanumeric character

    Examples:
      "Jun 2026 - Occupation_Contractor.pdf" -> "occupationcontractor"
      "Occupation_SelfEmplo"                 -> "occupationselfemplo"
      "Occupation_Self_Emplo"                -> "occupationselfemplo"
    """
    if not name:
        return ""
    text = str(name)
    text = re.sub(r"^\s*Jun\s*2026\s*-\s*", "", text)
    text = re.sub(r"\.pdf\s*$", "", text, flags=re.IGNORECASE)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


class FlowMatcher:
    """
    Maps inconsistent case line-names to flowchart flow names using
    canonicalization plus difflib fuzzy matching (cutoff ~0.8).
    """

    def __init__(self, flowcharts: Dict[str, Any], cutoff: float = 0.8):
        self.flowcharts = flowcharts
        self.cutoff = cutoff
        # canonical token -> original flow name
        self.canon_to_flow: Dict[str, str] = {}
        for flow_name in flowcharts:
            self.canon_to_flow[canonicalize_line_name(flow_name)] = flow_name
        self._canon_keys = list(self.canon_to_flow.keys())

    def match(self, line_name: Optional[str]) -> Optional[str]:
        """Return the best-matching flow name for a line-name, or None."""
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
        return None

    def match_case(self, case: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, int]]:
        """
        Pick the most likely flow for a case by matching each question's
        question_line_name and choosing the most frequently matched flow.

        Returns (chosen_flow_or_None, votes_by_flow).
        """
        votes: Dict[str, int] = {}
        for question in case.get("questions", []):
            flow = self.match(question.get("question_line_name"))
            if flow:
                votes[flow] = votes.get(flow, 0) + 1
        if not votes:
            return None, votes
        # deterministic: highest vote, tie-broken by flow name
        chosen = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return chosen, votes


def coverage_report(cases: List[Dict[str, Any]], matcher: FlowMatcher) -> Dict[str, Any]:
    """
    How many of the 500 cases could be mapped to a flowchart, and the
    per-flow distribution. Pure measurement, no fabrication.
    """
    matched = 0
    unmatched = 0
    per_flow: Dict[str, int] = {}
    for case in cases:
        flow, _votes = matcher.match_case(case)
        if flow:
            matched += 1
            per_flow[flow] = per_flow.get(flow, 0) + 1
        else:
            unmatched += 1
    total = len(cases)
    return {
        "total_cases": total,
        "matched_cases": matched,
        "unmatched_cases": unmatched,
        "match_rate_pct": round(100.0 * matched / total, 2) if total else 0.0,
        "cases_per_flow": dict(sorted(per_flow.items(), key=lambda kv: -kv[1])),
        "flows_available": list(matcher.flowcharts.keys()),
    }


def build_wording_index(wording: Dict[str, Any]) -> Dict[str, str]:
    """
    Collapse the tag -> question_line_name -> definition -> [{question_text,...}]
    structure into a flat {definition_label: first_question_text} lookup so a
    rule node label can be annotated with human-readable wording.
    """
    index: Dict[str, str] = {}
    for _tag, by_line in (wording or {}).items():
        if not isinstance(by_line, dict):
            continue
        for _line_name, by_def in by_line.items():
            if not isinstance(by_def, dict):
                continue
            for definition, entries in by_def.items():
                if definition in index:
                    continue
                if isinstance(entries, list) and entries:
                    text = entries[0].get("question_text")
                    if text:
                        index[definition] = text
    return index


def readable_question(label: str, wording_index: Dict[str, str]) -> str:
    """Return human-readable wording for a node label, or a clear fallback."""
    if label in wording_index:
        return wording_index[label]
    return f"(no wording found for rule line '{label}')"


# ---------------------------------------------------------------------------
# NeuroSan CodedTool wrapper
# ---------------------------------------------------------------------------
try:  # pragma: no cover - optional dependency for standalone runs
    from neuro_san.interfaces.coded_tool import CodedTool
except Exception:  # noqa: BLE001 - allow standalone, dependency-free execution

    class CodedTool:  # type: ignore
        """Minimal fallback so this module runs without neuro_san installed."""


class DataAccessTool(CodedTool):
    """
    CodedTool entrypoint. Loads the three real files and reports flowchart-match
    coverage so callers can judge data quality before deeper analysis.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        data_dir = args.get("data_dir", DATA_DIR)
        flowcharts = load_flowcharts(data_dir)
        cases = load_cases(data_dir)
        wording = load_question_wording(data_dir)
        matcher = FlowMatcher(flowcharts)
        coverage = coverage_report(cases, matcher)

        # Stash loaded artifacts for downstream tools in the same run.
        sly_data["ure_flowcharts"] = flowcharts
        sly_data["ure_cases"] = cases
        sly_data["ure_wording_index"] = build_wording_index(wording)

        return {
            "files_loaded": {
                "all_flowcharts.json": len(flowcharts),
                "desicion_question.json": len(cases),
                "question_wording.json": len(wording),
            },
            "coverage": coverage,
        }

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.invoke(args, sly_data)
