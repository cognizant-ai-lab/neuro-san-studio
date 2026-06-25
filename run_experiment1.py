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
Runnable entrypoint for Experiment 1 — URE Uplift Agents.

Runs the full pipeline end to end against the THREE real source files only:
  Ingestion -> Divergence Miner -> Pattern Analyser -> Rule Recommender
            -> URE Feedback Loop -> KPI metrics

It reads:
  coded_tools/generated/underwriting_analytics_ure_system/all_flowcharts.json
  coded_tools/generated/underwriting_analytics_ure_system/desicion_question.json
  coded_tools/generated/underwriting_analytics_ure_system/question_wording.json

and prints a summary mirroring Experiment 1's deliverables. No dataset files are
created or regenerated; nothing is fabricated.

Usage:
    python run_experiment1.py
"""

import os
import sys

# Ensure the repo root is importable when run directly.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from coded_tools.generated.underwriting_analytics_ure_system import data_access  # noqa: E402
from coded_tools.generated.underwriting_analytics_ure_system import divergence_miner  # noqa: E402
from coded_tools.generated.underwriting_analytics_ure_system import kpi_metrics  # noqa: E402
from coded_tools.generated.underwriting_analytics_ure_system import pattern_analyser  # noqa: E402
from coded_tools.generated.underwriting_analytics_ure_system import rule_recommender  # noqa: E402


def _hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main() -> int:
    data_dir = data_access.DATA_DIR

    # ---- Ingestion -------------------------------------------------------
    flowcharts = data_access.load_flowcharts(data_dir)
    cases = data_access.load_cases(data_dir)
    wording = data_access.load_question_wording(data_dir)
    wording_index = data_access.build_wording_index(wording)
    matcher = data_access.FlowMatcher(flowcharts)
    coverage = data_access.coverage_report(cases, matcher)

    _hr("EXPERIMENT 1 — URE UPLIFT AGENTS")
    print("Inputs (the only data sources):")
    print(f"  all_flowcharts.json     : {len(flowcharts)} flowcharts")
    print(f"  desicion_question.json  : {len(cases)} cases")
    print(f"  question_wording.json   : {len(wording)} rule-version tags")

    _hr("INGESTION — flowchart-match coverage / data quality")
    print(f"  Cases matched to a flowchart : {coverage['matched_cases']}/{coverage['total_cases']} "
          f"({coverage['match_rate_pct']}%)")
    print(f"  Cases with no flowchart match: {coverage['unmatched_cases']}")
    print("  Cases per flow:")
    for flow, count in coverage["cases_per_flow"].items():
        print(f"    - {flow}: {count}")

    # ---- Divergence Miner ------------------------------------------------
    mined = divergence_miner.mine_divergence(cases, flowcharts)
    records = mined["records"]
    dsum = mined["summary"]

    _hr("DIVERGENCE MINER — human-vs-URE divergence findings")
    print(f"  Decided cases (both sides categorical): {dsum['decided_cases']}")
    print(f"  Diverged cases                        : {dsum['diverged_cases']} "
          f"({dsum['divergence_rate_pct']}% of decided)")
    print(f"  Indeterminate rule predictions        : {dsum['indeterminate_predictions']}")
    print(f"  Unknown human outcomes (numeric only) : {dsum['unknown_actual_outcomes']}")
    print(f"  Unmapped cases                        : {dsum['unmapped_cases']}")
    print("  Example divergences:")
    shown = 0
    for rec in records:
        if rec["diverged"]:
            print(f"    - {rec['enquiry_id']} [{rec['flow']}]: "
                  f"rule={rec['predicted']} vs human={rec['actual']}")
            shown += 1
            if shown >= 5:
                break
    if shown == 0:
        print("    (no categorical divergences found in the supplied cases)")

    # ---- Pattern Analyser ------------------------------------------------
    patterns = pattern_analyser.analyse_patterns(records, wording_index)

    _hr("PATTERN ANALYSER — divergence by flow and rule line")
    print("  By occupation flow:")
    for row in patterns["by_flow"][:10]:
        print(f"    - {row['flow']}: {row['diverged_cases']}/{row['decided_cases']} "
              f"diverged ({row['divergence_rate_pct']}%)")
    print("  By directionality:")
    for direction, count in patterns["by_direction"].items():
        print(f"    - {direction}: {count}")
    print("  Top implicated rule lines:")
    for row in patterns["by_rule_line"][:8]:
        print(f"    - {row['rule_line']}: {row['diverged_cases_on_path']}/"
              f"{row['decided_cases_on_path']} ({row['divergence_rate_pct']}%) "
              f"| {row['readable_question'][:60]}")

    # ---- Rule Recommender + Feedback Loop --------------------------------
    recs = rule_recommender.recommend_rules(records, wording_index)
    cards = recs["opportunity_cards"]

    _hr("RULE RECOMMENDER — ranked rule-gap hypotheses & opportunity cards")
    if not cards:
        print("  No rule-uplift opportunity cards could be derived from the supplied cases.")
    for card in cards[:8]:
        print(f"  #{card['rank']} {card['rule_line']}  "
              f"[feasibility={card['feasibility']}]")
        print(f"      readable_question : {card['readable_question'][:70]}")
        print(f"      divergence_rate   : {card['divergence_rate_pct']}%  "
              f"cases_affected={card['cases_affected']}")
        print(f"      hypothesis        : {card['hypothesis']}")
        print(f"      recommended_change: {card['recommended_change']}")
        print(f"      est_STA_uplift_pp : {card['est_STA_uplift_pp']} (INDICATIVE)")

    # ---- KPI metrics -----------------------------------------------------
    kpis = kpi_metrics.compute_kpis(records, cards)

    _hr("SUCCESS METRICS (Experiment 1)")
    m = kpis["metrics"]
    print(f"  1) Indicative % STA uplift        : {m['indicative_sta_uplift_pct']['value']}%  "
          f"({m['indicative_sta_uplift_pct']['basis']})")
    print(f"     -> {m['indicative_sta_uplift_pct']['qualifier']}")
    print(f"  2) Actionable recommendations     : {m['actionable_recommendations']['value']}  "
          f"({m['actionable_recommendations']['basis']})")
    print(f"  3) Manual-review-effort reduction : {m['manual_review_effort_reduction_pct']['value']}%  "
          f"({m['manual_review_effort_reduction_pct']['basis']})")
    print(f"     -> {m['manual_review_effort_reduction_pct']['qualifier']}")
    print(f"  4) URE tuning cycle-time reduction: {m['ure_tuning_cycle_time_reduction']['value']}")
    print(f"     -> {m['ure_tuning_cycle_time_reduction']['note']}")

    if kpis["limitations"]:
        _hr("LIMITATIONS (stated, not invented)")
        for lim in kpis["limitations"]:
            print(f"  - {lim}")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
