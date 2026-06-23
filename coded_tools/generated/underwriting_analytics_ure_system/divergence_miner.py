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
Divergence Miner stage (Experiment 1).

For each case:
  1) map it to a flowchart via canonicalized line names,
  2) simulate the URE rule logic on the case answers,
  3) derive the ACTUAL human outcome from the case decisions,
  4) compare rule-predicted vs actual and record any divergence.

Outputs are returned in memory (from invoke); no dataset file is written.
"""

import logging
import re
from typing import Any
from typing import Dict
from typing import List

from . import data_access
from . import rule_engine

logger = logging.getLogger(__name__)

# Categorical outcome tokens that represent an accept/refer decision.
_ACCEPT_TOKEN = "STANDARD"
_REFER_TOKEN = "REFER"


def _decision_tokens(decision: Dict[str, Any]) -> List[str]:
    """Collect categorical outcome tokens (STANDARD/REFER) from a decision."""
    tokens: List[str] = []
    candidates: List[str] = []
    value = decision.get("decision_value")
    if value is not None:
        candidates.append(str(value))
    for sub in decision.get("decision_values", []) or []:
        candidates.append(str(sub))
    for cand in candidates:
        for piece in re.split(r"[,\s]+", cand):
            upper = piece.strip().upper()
            if upper in (_ACCEPT_TOKEN, _REFER_TOKEN):
                tokens.append(upper)
    return tokens


def derive_actual_outcome(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive the human/actual outcome from a case's decisions.

    Classification (documented and deterministic):
      - Only categorical decisions (decision_value tokens of STANDARD/REFER)
        are considered; numeric benefit amounts are computed outputs, not
        accept/refer outcomes, so they are excluded.
      - any REFER token        -> "REFER"   (referral / override)
      - STANDARD and no REFER   -> "STANDARD" (straight-through accept)
      - no categorical tokens   -> "UNKNOWN" (cannot decide from data)
    """
    standard = 0
    refer = 0
    for decision in case.get("decisions", []):
        for token in _decision_tokens(decision):
            if token == _ACCEPT_TOKEN:
                standard += 1
            elif token == _REFER_TOKEN:
                refer += 1
    if refer > 0:
        outcome = _REFER_TOKEN
    elif standard > 0:
        outcome = _ACCEPT_TOKEN
    else:
        outcome = "UNKNOWN"
    return {
        "outcome": outcome,
        "standard_signals": standard,
        "refer_signals": refer,
    }


def mine_divergence(
    cases: List[Dict[str, Any]],
    flowcharts: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce per-case divergence records plus a data-quality summary.

    Each record:
      {
        enquiry_id, flow, predicted, actual, diverged(bool),
        reason, rule_nodes_on_path, decided(bool)
      }
    """
    matcher = data_access.FlowMatcher(flowcharts)
    graphs = rule_engine.build_graphs(flowcharts)

    records: List[Dict[str, Any]] = []
    unmapped = 0
    indeterminate_pred = 0
    unknown_actual = 0
    decided = 0
    diverged = 0

    for case in cases:
        enquiry_id = case.get("enquiry_id")
        flow, _votes = matcher.match_case(case)
        if not flow:
            unmapped += 1
            records.append(
                {
                    "enquiry_id": enquiry_id,
                    "flow": None,
                    "predicted": "unmapped",
                    "actual": None,
                    "diverged": False,
                    "reason": "no flowchart matched the case line names",
                    "rule_nodes_on_path": [],
                    "decided": False,
                }
            )
            continue

        answers = rule_engine.answers_from_case(case)
        sim = rule_engine.simulate(graphs[flow], answers)
        predicted = sim["outcome"]
        actual_info = derive_actual_outcome(case)
        actual = actual_info["outcome"]

        if predicted == "indeterminate":
            indeterminate_pred += 1
        if actual == "UNKNOWN":
            unknown_actual += 1

        is_decided = predicted in (_ACCEPT_TOKEN, _REFER_TOKEN) and actual in (
            _ACCEPT_TOKEN,
            _REFER_TOKEN,
        )
        has_diverged = bool(is_decided and predicted != actual)
        if is_decided:
            decided += 1
        if has_diverged:
            diverged += 1

        records.append(
            {
                "enquiry_id": enquiry_id,
                "flow": flow,
                "predicted": predicted,
                "actual": actual,
                "diverged": has_diverged,
                "reason": sim["reason"],
                "rule_nodes_on_path": sim["path_labels"],
                "terminal_node": sim.get("terminal_node"),
                "decided": is_decided,
                "actual_signals": {
                    "standard": actual_info["standard_signals"],
                    "refer": actual_info["refer_signals"],
                },
            }
        )

    summary = {
        "total_cases": len(cases),
        "unmapped_cases": unmapped,
        "indeterminate_predictions": indeterminate_pred,
        "unknown_actual_outcomes": unknown_actual,
        "decided_cases": decided,
        "diverged_cases": diverged,
        "divergence_rate_pct": round(100.0 * diverged / decided, 2) if decided else 0.0,
        "note": (
            "Divergence is only counted where BOTH the rule prediction and the "
            "human outcome are categorical (STANDARD/REFER). Unmapped, "
            "indeterminate, or numeric-only cases are excluded and reported "
            "separately so data quality is transparent."
        ),
    }
    return {"records": records, "summary": summary}


# ---------------------------------------------------------------------------
# NeuroSan CodedTool wrapper
# ---------------------------------------------------------------------------
try:  # pragma: no cover
    from neuro_san.interfaces.coded_tool import CodedTool
except Exception:  # noqa: BLE001

    class CodedTool:  # type: ignore
        """Fallback base when neuro_san is unavailable."""


class DivergenceMinerTool(CodedTool):
    """CodedTool entrypoint for the Divergence Miner stage."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        flowcharts = sly_data.get("ure_flowcharts") or data_access.load_flowcharts()
        cases = sly_data.get("ure_cases") or data_access.load_cases()
        result = mine_divergence(cases, flowcharts)
        # Stash for downstream Pattern Analyser / Rule Recommender stages.
        sly_data["ure_divergence_records"] = result["records"]
        sly_data["ure_divergence_summary"] = result["summary"]
        limit = int(args.get("max_records_returned", 25))
        return {
            "summary": result["summary"],
            "diverged_examples": [r for r in result["records"] if r["diverged"]][:limit],
        }

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.invoke(args, sly_data)
