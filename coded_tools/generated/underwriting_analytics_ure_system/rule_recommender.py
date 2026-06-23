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
Rule Recommender + URE Feedback Loop stage (Experiment 1).

Ranks rule gaps by Straight-Through-Acceptance (STA) uplift potential and emits
"opportunity cards". The driving signal is directionality:

  - "rule_too_strict": rule would REFER but the human accepted (STANDARD).
    Relaxing such a rule converts referrals into straight-through accepts ->
    direct STA uplift.

All figures are derived from the divergence records. STA-uplift values are
explicitly INDICATIVE estimates, not guarantees, and are flagged as such.
"""

import logging
from collections import defaultdict
from typing import Any
from typing import Dict
from typing import List

from . import data_access

logger = logging.getLogger(__name__)


def _direction(predicted: str, actual: str) -> str:
    if predicted == "REFER" and actual == "STANDARD":
        return "rule_too_strict"
    if predicted == "STANDARD" and actual == "REFER":
        return "rule_too_lenient"
    return "aligned"


def _is_rule_line(label: str) -> bool:
    if not label:
        return False
    upper = label.upper()
    if upper.startswith("STANDARD") or upper.startswith("REFER"):
        return False
    if label in {"PRODUCT", "DO_NOTHING", "OCCUPATION", "MLC"}:
        return False
    return True


def recommend_rules(
    records: List[Dict[str, Any]],
    wording_index: Dict[str, str],
    min_cases: int = 1,
) -> Dict[str, Any]:
    """
    Build ranked opportunity cards from divergence records.

    Returns {"opportunity_cards": [...], "summary": {...}}.
    """
    decided = [r for r in records if r.get("decided")]
    total_decided = len(decided)
    total_referrals_actual = sum(1 for r in decided if r.get("actual") == "REFER")

    # Per rule line accumulators.
    line_decided: Dict[str, int] = defaultdict(int)
    line_diverged: Dict[str, int] = defaultdict(int)
    line_strict: Dict[str, int] = defaultdict(int)
    line_lenient: Dict[str, int] = defaultdict(int)
    line_flows: Dict[str, set] = defaultdict(set)
    line_cases: Dict[str, List[str]] = defaultdict(list)

    for rec in decided:
        direction = _direction(rec.get("predicted"), rec.get("actual")) if rec.get("diverged") else "aligned"
        seen = set()
        for label in rec.get("rule_nodes_on_path", []):
            if not _is_rule_line(label) or label in seen:
                continue
            seen.add(label)
            line_decided[label] += 1
            line_flows[label].add(rec.get("flow"))
            if rec.get("diverged"):
                line_diverged[label] += 1
                line_cases[label].append(rec.get("enquiry_id"))
                if direction == "rule_too_strict":
                    line_strict[label] += 1
                elif direction == "rule_too_lenient":
                    line_lenient[label] += 1

    cards: List[Dict[str, Any]] = []
    for label in line_diverged:
        strict = line_strict[label]
        lenient = line_lenient[label]
        diverged = line_diverged[label]
        dec_on_path = line_decided[label]
        cases_affected = diverged  # all divergent cases on this rule line
        if cases_affected < min_cases:
            continue

        divergence_rate = round(100.0 * diverged / dec_on_path, 2) if dec_on_path else 0.0
        # STA uplift only comes from the rule-too-strict direction.
        est_uplift_pp = round(100.0 * strict / total_decided, 2) if total_decided else 0.0

        # Feasibility heuristic: a clean, one-directional signal is easier to
        # action than a mixed one.
        dominant = max(strict, lenient)
        if diverged and dominant / diverged >= 0.8:
            feasibility = "high"
        elif diverged and dominant / diverged >= 0.5:
            feasibility = "medium"
        else:
            feasibility = "low"

        if strict >= lenient and strict > 0:
            gap_type = "sta_uplift"  # rule too strict -> relax to gain STA
            hypothesis = (
                f"Rule line '{label}' refers cases that underwriters then accept as "
                f"STANDARD in {strict} decided case(s); the threshold/condition may be "
                f"stricter than human practice."
            )
            recommended_change = (
                f"Relax or re-tune the '{label}' branch so qualifying cases route to "
                f"STANDARD instead of REFER; validate against the {strict} divergent "
                f"case(s) before rollout."
            )
        else:
            gap_type = "risk_leakage"  # rule too lenient -> tighten to match humans
            hypothesis = (
                f"Rule line '{label}' auto-accepts (STANDARD) cases that underwriters "
                f"then REFER in {lenient} decided case(s); the rule may be more lenient "
                f"than human practice and could let risk through."
            )
            recommended_change = (
                f"Tighten the '{label}' branch (add/adjust referral condition) so these "
                f"cases route to REFER as underwriters did; validate against the "
                f"{lenient} divergent case(s). This reduces downstream rework rather "
                f"than adding STA."
            )

        cards.append(
            {
                "rule_line": label,
                "gap_type": gap_type,
                "readable_question": data_access.readable_question(label, wording_index),
                "divergence_rate_pct": divergence_rate,
                "cases_affected": cases_affected,
                "diverged_cases_on_path": diverged,
                "strict_cases": strict,
                "lenient_cases": lenient,
                "hypothesis": hypothesis,
                "recommended_change": recommended_change,
                "est_STA_uplift_pp": est_uplift_pp,
                "est_STA_uplift_pp_note": "INDICATIVE: share of decided cases that would convert to STA if this rule were relaxed (0 for risk_leakage gaps).",
                "feasibility": feasibility,
                "flows": sorted(f for f in line_flows[label] if f),
                "example_enquiry_ids": [c for c in line_cases[label] if c][:5],
            }
        )

    # Rank: STA-uplift potential first, then divergence volume, then rate.
    cards.sort(
        key=lambda c: (-c["est_STA_uplift_pp"], -c["cases_affected"], -c["divergence_rate_pct"]),
    )
    for idx, card in enumerate(cards, start=1):
        card["rank"] = idx

    summary = {
        "total_decided_cases": total_decided,
        "total_actual_referrals": total_referrals_actual,
        "opportunity_cards": len(cards),
        "sta_uplift_cards": sum(1 for c in cards if c["gap_type"] == "sta_uplift"),
        "risk_leakage_cards": sum(1 for c in cards if c["gap_type"] == "risk_leakage"),
        "actionable_cards": sum(1 for c in cards if c["feasibility"] in ("high", "medium")),
        "note": (
            "Cards ranked by STA-uplift potential (rule-too-strict divergences) "
            "first, then by divergent volume. 'risk_leakage' cards capture the "
            "opposite gap (rule too lenient) and carry 0 STA uplift. All figures "
            "are INDICATIVE and grounded only in the 500 supplied cases."
        ),
    }
    return {"opportunity_cards": cards, "summary": summary}


# ---------------------------------------------------------------------------
# NeuroSan CodedTool wrapper
# ---------------------------------------------------------------------------
try:  # pragma: no cover
    from neuro_san.interfaces.coded_tool import CodedTool
except Exception:  # noqa: BLE001

    class CodedTool:  # type: ignore
        """Fallback base when neuro_san is unavailable."""


class RuleRecommenderTool(CodedTool):
    """CodedTool entrypoint for the Rule Recommender + Feedback Loop stage."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        records = sly_data.get("ure_divergence_records")
        if records is None:
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

        result = recommend_rules(records, wording_index)
        sly_data["ure_opportunity_cards"] = result["opportunity_cards"]
        sly_data["ure_recommender_summary"] = result["summary"]
        top = int(args.get("top", 10))
        return {
            "summary": result["summary"],
            "opportunity_cards": result["opportunity_cards"][:top],
        }

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.invoke(args, sly_data)
