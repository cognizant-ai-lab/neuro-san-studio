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
Pattern Analyser stage (Experiment 1).

Aggregates the per-case divergence records by occupation flow, by rule line
(graph node label), and by directionality. Attaches human-readable question
wording (from question_wording.json) to each implicated rule line.

Every count traces back to the divergence records, which trace back to the
three real JSON files. Nothing is fabricated.
"""

import logging
from collections import defaultdict
from typing import Any
from typing import Dict
from typing import List

from . import data_access

logger = logging.getLogger(__name__)

# Labels that are terminals or generic structural nodes, not "rule lines"
# worth recommending changes on.
_NON_RULE_PREFIXES = ("STANDARD", "REFER")
_GENERIC_LABELS = {"PRODUCT", "DO_NOTHING", "OCCUPATION", "MLC"}


def _is_rule_line(label: str) -> bool:
    if not label:
        return False
    upper = label.upper()
    if any(upper.startswith(p) for p in _NON_RULE_PREFIXES):
        return False
    if label in _GENERIC_LABELS:
        return False
    return True


def _direction(predicted: str, actual: str) -> str:
    """Classify divergence directionality."""
    if predicted == "REFER" and actual == "STANDARD":
        return "rule_too_strict"  # human accepted what the rule would refer -> STA uplift
    if predicted == "STANDARD" and actual == "REFER":
        return "rule_too_lenient"  # human referred what the rule would auto-accept
    return "aligned"


def analyse_patterns(
    records: List[Dict[str, Any]],
    wording_index: Dict[str, str],
) -> Dict[str, Any]:
    """
    Aggregate divergence by flow, rule line, and direction.

    Returns dict with: by_flow, by_rule_line (annotated), by_direction, totals.
    """
    decided = [r for r in records if r.get("decided")]

    # ---- by flow ----
    flow_decided: Dict[str, int] = defaultdict(int)
    flow_diverged: Dict[str, int] = defaultdict(int)
    for rec in decided:
        flow = rec.get("flow")
        flow_decided[flow] += 1
        if rec.get("diverged"):
            flow_diverged[flow] += 1
    by_flow = []
    for flow in sorted(flow_decided, key=lambda f: -flow_diverged[f]):
        dec = flow_decided[flow]
        div = flow_diverged[flow]
        by_flow.append(
            {
                "flow": flow,
                "decided_cases": dec,
                "diverged_cases": div,
                "divergence_rate_pct": round(100.0 * div / dec, 2) if dec else 0.0,
            }
        )

    # ---- by rule line (node label) ----
    line_decided: Dict[str, int] = defaultdict(int)
    line_diverged: Dict[str, int] = defaultdict(int)
    line_flows: Dict[str, set] = defaultdict(set)
    for rec in decided:
        seen = set()
        for label in rec.get("rule_nodes_on_path", []):
            if not _is_rule_line(label) or label in seen:
                continue
            seen.add(label)
            line_decided[label] += 1
            line_flows[label].add(rec.get("flow"))
            if rec.get("diverged"):
                line_diverged[label] += 1

    by_rule_line = []
    for label in sorted(line_diverged, key=lambda lbl: (-line_diverged[lbl], lbl)):
        dec = line_decided[label]
        div = line_diverged[label]
        by_rule_line.append(
            {
                "rule_line": label,
                "readable_question": data_access.readable_question(label, wording_index),
                "decided_cases_on_path": dec,
                "diverged_cases_on_path": div,
                "divergence_rate_pct": round(100.0 * div / dec, 2) if dec else 0.0,
                "flows": sorted(f for f in line_flows[label] if f),
            }
        )

    # ---- by direction ----
    direction_counts: Dict[str, int] = defaultdict(int)
    for rec in decided:
        if rec.get("diverged"):
            direction_counts[_direction(rec.get("predicted"), rec.get("actual"))] += 1

    totals = {
        "decided_cases": len(decided),
        "diverged_cases": sum(1 for r in decided if r.get("diverged")),
        "rule_lines_implicated": len(by_rule_line),
    }

    return {
        "by_flow": by_flow,
        "by_rule_line": by_rule_line,
        "by_direction": dict(direction_counts),
        "totals": totals,
    }


# ---------------------------------------------------------------------------
# NeuroSan CodedTool wrapper
# ---------------------------------------------------------------------------
try:  # pragma: no cover
    from neuro_san.interfaces.coded_tool import CodedTool
except Exception:  # noqa: BLE001

    class CodedTool:  # type: ignore
        """Fallback base when neuro_san is unavailable."""


class PatternAnalyserTool(CodedTool):
    """CodedTool entrypoint for the Pattern Analyser stage."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        records = sly_data.get("ure_divergence_records")
        if records is None:
            # Run the upstream stage if it has not populated sly_data yet.
            from . import divergence_miner

            flowcharts = sly_data.get("ure_flowcharts") or data_access.load_flowcharts()
            cases = sly_data.get("ure_cases") or data_access.load_cases()
            mined = divergence_miner.mine_divergence(cases, flowcharts)
            records = mined["records"]
            sly_data["ure_divergence_records"] = records
            sly_data["ure_divergence_summary"] = mined["summary"]

        wording_index = sly_data.get("ure_wording_index")
        if wording_index is None:
            wording_index = data_access.build_wording_index(data_access.load_question_wording())
            sly_data["ure_wording_index"] = wording_index

        patterns = analyse_patterns(records, wording_index)
        sly_data["ure_patterns"] = patterns

        top_rule_lines = args.get("top_rule_lines")
        if top_rule_lines:
            try:
                limit = int(top_rule_lines)
            except (TypeError, ValueError):
                limit = None
            if limit and limit > 0:
                trimmed = dict(patterns)
                trimmed["by_rule_line"] = patterns["by_rule_line"][:limit]
                return trimmed
        return patterns

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.invoke(args, sly_data)
