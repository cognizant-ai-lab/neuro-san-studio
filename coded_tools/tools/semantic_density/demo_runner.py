#!/usr/bin/env python3
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
Demo runner for the semantic density FedEx Day presentation.

Runs the engine directly on curated questions and produces colored
terminal output showing confidence scores (green/yellow/red).
"""

import json
import sys
import time

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[96m"
WHITE = "\033[97m"

DEMO_QUESTIONS = [
    {
        "question": "What is the capital of France?",
        "expected": "High confidence — factual, universally agreed upon",
    },
    {
        "question": "What is the best programming language?",
        "expected": "Lower confidence — subjective, diverse answers expected",
    },
    {
        "question": "What year did humans land on Mars?",
        "expected": "Low confidence — factually incorrect premise",
    },
]


def color_for_score(score: float) -> str:
    """Return ANSI color code based on confidence score."""
    if score >= 0.7:
        return GREEN
    if score >= 0.4:
        return YELLOW
    return RED


def label_for_score(score: float) -> str:
    """Return human label for confidence score."""
    if score >= 0.7:
        return "HIGH CONFIDENCE"
    if score >= 0.4:
        return "MODERATE CONFIDENCE"
    return "LOW CONFIDENCE"


def print_banner():
    """Print the demo banner."""
    print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  Semantic Density — Confidence Scoring for Agent Networks{RESET}")
    print(f"{BOLD}{CYAN}  FedEx Day Demo{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 70}{RESET}\n")


# pylint: disable=too-many-locals
def print_result(question_info: dict, result: dict, elapsed: float):
    """Print a single question's result with colored output."""
    question = question_info["question"]
    expected = question_info["expected"]
    score = result["confidence_score"]
    color = color_for_score(score)
    label = label_for_score(score)

    print(f"{BOLD}{WHITE}Question:{RESET} {question}")
    print(f"{DIM}Expected: {expected}{RESET}")
    print(f"{DIM}Time: {elapsed:.1f}s{RESET}")
    print()

    bar_length = 40
    filled = int(score * bar_length)
    progress = "█" * filled + "░" * (bar_length - filled)
    print(f"  Confidence: {color}{BOLD}{score:.4f}{RESET}  [{color}{progress}{RESET}]  {color}{BOLD}{label}{RESET}")
    print()

    print(f"  {BOLD}Best answer:{RESET} {result['best_answer']}")
    print()

    print(f"  {DIM}All beam search answers:{RESET}")
    for idx, entry in enumerate(result["answers_with_scores"]):
        prob = entry["probability"]
        density = entry["density"]
        answer_color = color_for_score(density)
        snippet = entry["answer"][:100]
        print(f"    {idx + 1}. [{answer_color}density={density:.4f}{RESET}, prob={prob:.4f}] {snippet}")

    print(f"\n{DIM}{'─' * 70}{RESET}\n")


def run_demo(precomputed_path: str | None = None):
    """Run the demo, either live or from pre-computed results."""
    print_banner()

    if precomputed_path:
        print(f"{DIM}Loading pre-computed results from {precomputed_path}...{RESET}\n")
        with open(precomputed_path, encoding="utf-8") as f:
            cached = json.load(f)

        for question_info in DEMO_QUESTIONS:
            key = question_info["question"]
            if key in cached:
                print_result(question_info, cached[key], cached[key].get("elapsed", 0))
            else:
                print(f"{RED}No pre-computed result for: {key}{RESET}\n")
        return

    # Live mode — import engine and run
    from coded_tools.tools.semantic_density.semantic_density_engine import get_engine

    print(f"{DIM}Loading models (this may take a minute)...{RESET}\n")
    engine = get_engine()

    all_results = {}
    for question_info in DEMO_QUESTIONS:
        question = question_info["question"]
        print(f"{CYAN}▶ Processing: {question}{RESET}\n")

        start = time.time()
        result = engine.evaluate(question)
        elapsed = time.time() - start
        result["elapsed"] = elapsed

        print_result(question_info, result, elapsed)
        all_results[question] = result

    # Save results for backup
    backup_path = "demo_results_backup.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"{DIM}Results saved to {backup_path}{RESET}")

    print(f"\n{BOLD}{CYAN}{'=' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  Demo complete.{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 70}{RESET}\n")


if __name__ == "__main__":
    precomputed = sys.argv[1] if len(sys.argv) > 1 else None
    run_demo(precomputed)
