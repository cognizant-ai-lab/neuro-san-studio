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
KPI metrics for Experiment 1 (URE Uplift Agents).

Computes the four success metrics from the divergence records and opportunity
cards:
  1) Indicative % STA uplift
  2) # actionable rule recommendations
  3) Manual-review-effort reduction % (proxy)
  4) URE tuning cycle-time reduction (qualitative)

Every metric traces back to the three real JSON files. STA uplift is INDICATIVE
and is labelled as such. Where a value cannot be computed, the limitation is
stated instead of inventing a number.
"""

import logging
from typing import Any
from typing import Dict
from typing import List

logger = logging.getLogger(__name__)


def _unique_strict_cases(records: List[Dict[str, Any]]) -> List[str]:
    """Enquiry ids where the rule would REFER but the human accepted (STANDARD)."""
    ids = []
    for rec in records:
        if (
            rec.get("decided")
            and rec.get("diverged")
            and rec.get("predicted") == "REFER"
            and rec.get("actual") == "STANDARD"
        ):
            ids.append(rec.get("enquiry_id"))
    return [i for i in ids if i]


def compute_kpis(
    records: List[Dict[str, Any]],
    opportunity_cards: List[Dict[str, Any]],
    top_n: int = 5,
) -> Dict[str, Any]:
    """Compute the Experiment 1 success metrics."""
    decided = [r for r in records if r.get("decided")]
    total_decided = len(decided)
    total_referrals = sum(1 for r in decided if r.get("actual") == "REFER")

    strict_ids = set(_unique_strict_cases(records))
    n_strict = len(strict_ids)

    # 1) Indicative % STA uplift: unique rule-too-strict cases / decided cases.
    if total_decided:
        sta_uplift_pp = round(100.0 * n_strict / total_decided, 2)
    else:
        sta_uplift_pp = None

    # 2) # actionable rule recommendations (feasibility high/medium).
    actionable = [c for c in opportunity_cards if c.get("feasibility") in ("high", "medium")]
    n_actionable = len(actionable)

    # 3) Manual-review-effort reduction %: share of actual referrals attributable
    #    to the top-N recommended rules (unique cases they would convert to STA).
    top_lines = {c.get("rule_line") for c in opportunity_cards[:top_n]}
    attributable = set()
    for rec in records:
        if (
            rec.get("decided")
            and rec.get("diverged")
            and rec.get("predicted") == "REFER"
            and rec.get("actual") == "STANDARD"
            and top_lines.intersection(set(rec.get("rule_nodes_on_path", [])))
        ):
            attributable.add(rec.get("enquiry_id"))
    if total_referrals:
        review_reduction_pp = round(100.0 * len(attributable) / total_referrals, 2)
    else:
        review_reduction_pp = None

    # 4) URE tuning cycle-time reduction: qualitative.
    cycle_time_note = (
        "Qualitative: the Divergence Miner -> Pattern Analyser -> Rule Recommender "
        "chain converts manual log review into ranked, evidence-backed opportunity "
        "cards, compressing the URE tuning loop from ad-hoc analysis to a repeatable "
        "automated pass over the 500 cases. A numeric cycle-time reduction is NOT "
        "computed because the source files contain no timing/effort data."
    )

    metrics = {
        "indicative_sta_uplift_pct": {
            "value": sta_uplift_pp,
            "basis": f"{n_strict} rule-too-strict case(s) of {total_decided} decided case(s)",
            "qualifier": "INDICATIVE estimate, not a guaranteed production uplift.",
        },
        "actionable_recommendations": {
            "value": n_actionable,
            "basis": f"{n_actionable} of {len(opportunity_cards)} opportunity cards rated high/medium feasibility",
        },
        "manual_review_effort_reduction_pct": {
            "value": review_reduction_pp,
            "basis": (
                f"{len(attributable)} referral case(s) attributable to top-{top_n} "
                f"recommended rules of {total_referrals} actual referral(s)"
            ),
            "qualifier": "Proxy metric: referrals convertible to STA via the top recommendations.",
        },
        "ure_tuning_cycle_time_reduction": {
            "value": "not_quantified",
            "note": cycle_time_note,
        },
    }

    limitations = []
    if total_decided == 0:
        limitations.append(
            "No case had BOTH a categorical rule prediction and a categorical human "
            "outcome, so STA-uplift and review-reduction percentages could not be "
            "computed from the supplied data."
        )
    if total_referrals == 0:
        limitations.append(
            "No actual referral outcomes were present, so manual-review-effort "
            "reduction could not be computed."
        )

    return {
        "metrics": metrics,
        "denominators": {
            "decided_cases": total_decided,
            "actual_referrals": total_referrals,
            "rule_too_strict_cases": n_strict,
        },
        "limitations": limitations,
    }


# ---------------------------------------------------------------------------
# NeuroSan CodedTool wrapper
# ---------------------------------------------------------------------------
try:  # pragma: no cover
    from neuro_san.interfaces.coded_tool import CodedTool
except Exception:  # noqa: BLE001

    class CodedTool:  # type: ignore
        """Fallback base when neuro_san is unavailable."""


class KpiMetricsTool(CodedTool):
    """CodedTool entrypoint that computes the Experiment 1 success metrics."""

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        from . import data_access
        from . import divergence_miner
        from . import rule_recommender

        records = sly_data.get("ure_divergence_records")
        if records is None:
            flowcharts = sly_data.get("ure_flowcharts") or data_access.load_flowcharts()
            cases = sly_data.get("ure_cases") or data_access.load_cases()
            mined = divergence_miner.mine_divergence(cases, flowcharts)
            records = mined["records"]
            sly_data["ure_divergence_records"] = records
            sly_data["ure_divergence_summary"] = mined["summary"]

        cards = sly_data.get("ure_opportunity_cards")
        if cards is None:
            wording_index = sly_data.get("ure_wording_index") or data_access.build_wording_index(
                data_access.load_question_wording()
            )
            rec = rule_recommender.recommend_rules(records, wording_index)
            cards = rec["opportunity_cards"]
            sly_data["ure_opportunity_cards"] = cards

        result = compute_kpis(records, cards, top_n=int(args.get("top_n", 5)))
        sly_data["ure_kpis"] = result
        return result

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.invoke(args, sly_data)
