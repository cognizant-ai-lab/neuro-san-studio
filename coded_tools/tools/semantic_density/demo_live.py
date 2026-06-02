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
FedEx Day 5-minute demo: live agent network simulation with TTS narration.

Simulates the qa_manager -> answerer + confidence_checker agent flow,
showing how agents change behavior based on semantic density confidence.

Usage:
    CUDA_VISIBLE_DEVICES=7 python demo_live.py [--audio-url URL]
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[96m"
WHITE = "\033[97m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"

# Confidence thresholds for agent behavior
THRESHOLD_HIGH = 0.9
THRESHOLD_MODERATE = 0.75

DEMO_QUESTIONS = [
    {
        "question": "What is the capital of France?",
        "category": "Factual — single correct answer",
    },
    {
        "question": "What is the best programming language?",
        "category": "Subjective — no single right answer",
    },
    {
        "question": "What will the stock market do tomorrow?",
        "category": "Unpredictable — genuinely uncertain",
    },
]


def speak(audio_url, text, voice="nova"):
    """Send TTS narration if audio URL is configured."""
    if not audio_url:
        return
    try:
        encoded = urllib.parse.urlencode({"text": text, "voice": voice})
        url = f"{audio_url}/speak?{encoded}"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except Exception:
        pass


def wait_for_speech(seconds):
    """Pause to let TTS finish playing."""
    time.sleep(seconds)


def color_for_score(score):
    if score >= THRESHOLD_HIGH:
        return GREEN
    if score >= THRESHOLD_MODERATE:
        return YELLOW
    return RED


def print_agent(name, color, message):
    """Print a message as if from an agent."""
    print(f"  {color}{BOLD}[{name}]{RESET} {message}")


def run_demo(audio_url=None, precomputed_path=None):
    """Run the full 5-minute FedEx Day demo."""

    # ── INTRO (30s) ──────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  ╔══════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}  ║   Semantic Density — Confidence for Agent Networks      ║{RESET}")
    print(f"{BOLD}{CYAN}  ║   FedEx Day 2026                                        ║{RESET}")
    print(f"{BOLD}{CYAN}  ╚══════════════════════════════════════════════════════════╝{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")

    speak(audio_url,
          "Welcome to our FedEx Day project: Semantic Density for Agent Networks. "
          "We took Xin's research demo, a standalone web app that measures LLM confidence, "
          "and productionized it into a reusable Coded Tool for neuro-san. "
          "Now any agent network can know when to trust its own answers.")
    wait_for_speech(14)

    speak(audio_url,
          "The algorithm works in four steps. First, diverse beam search generates "
          "five different answers. Then we extract token probabilities. "
          "Next, an NLI model scores how semantically different each pair of answers is. "
          "Finally, we combine these into a single zero-to-one confidence score.")
    wait_for_speech(14)

    # ── AGENT NETWORK DEMO (3.5 min) ────────────────────────────────
    print(f"{BOLD}{WHITE}  Agent Network: qa_manager → answerer + confidence_checker{RESET}")
    print(f"{DIM}  The QA Manager asks for an answer, checks confidence,{RESET}")
    print(f"{DIM}  then adapts its response based on the score.{RESET}\n")
    print(f"{DIM}{'─' * 70}{RESET}\n")

    speak(audio_url,
          "Let's see it in action. We have a simple agent network: "
          "a QA Manager that delegates to an Answerer agent and a Confidence Checker. "
          "Watch how the manager changes its behavior based on the confidence score.")
    wait_for_speech(10)

    # Load engine or precomputed results
    if precomputed_path:
        with open(precomputed_path, encoding="utf-8") as f:
            cached = json.load(f)
        engine = None
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from semantic_density_engine import SemanticDensityEngine
        engine = SemanticDensityEngine(
            generation_model="Qwen/Qwen2.5-7B-Instruct",
            nli_model="microsoft/deberta-large-mnli",
            device="cuda:0",
        )
        cached = None

    for i, q_info in enumerate(DEMO_QUESTIONS, 1):
        question = q_info["question"]
        category = q_info["category"]

        print(f"{BOLD}{WHITE}  ┌─ Question {i}: {question}{RESET}")
        print(f"{DIM}  │  Category: {category}{RESET}")
        print(f"{DIM}  │{RESET}")

        speak(audio_url, f"Question {i}: {question}. This is a {category.split(' — ')[0].lower()} question.")
        wait_for_speech(5)

        # Step 1: QA Manager receives the question
        print_agent("qa_manager", MAGENTA, f"Received question: \"{question}\"")
        print_agent("qa_manager", MAGENTA, "Delegating to answerer and confidence_checker...")
        print(f"{DIM}  │{RESET}")

        # Step 2: Get the answer (simulated answerer agent)
        if cached and question in cached:
            result = cached[question]
            best_answer = result["best_answer"]
            score = result["confidence_score"]
            interp = result["interpretation"]
            elapsed = result.get("elapsed", 0)
        else:
            start = time.time()
            result = engine.evaluate(question)
            elapsed = time.time() - start
            best_answer = result["best_answer"]
            score = result["confidence_score"]
            interp = result["interpretation"]

        print_agent("answerer", BLUE, f"\"{best_answer}\"")
        print(f"{DIM}  │{RESET}")

        # Step 3: Confidence check
        color = color_for_score(score)
        bar_length = 30
        filled = int(score * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        print_agent("confidence_checker", CYAN,
                    f"Score: {color}{BOLD}{score:.4f}{RESET} [{color}{bar}{RESET}]")

        # Show individual beam answers
        if "answers_with_scores" in result:
            print(f"{DIM}  │  Beam search answers:{RESET}")
            for j, entry in enumerate(result["answers_with_scores"]):
                d = entry["density"]
                dc = color_for_score(d)
                snippet = entry["answer"][:75]
                print(f"{DIM}  │    {j+1}. [{dc}d={d:.3f}{RESET}{DIM}] {snippet}{RESET}")
        print(f"{DIM}  │{RESET}")

        # Step 4: QA Manager adapts behavior based on confidence
        if score >= THRESHOLD_HIGH:
            print_agent("qa_manager", MAGENTA,
                        f"{GREEN}{BOLD}✓ HIGH CONFIDENCE{RESET} — presenting answer directly:")
            print(f"  {BOLD}  → {best_answer}{RESET}")
            speak(audio_url,
                  f"Confidence is {score:.2f}, which is high. "
                  f"The manager presents the answer directly: {best_answer}")
        elif score >= THRESHOLD_MODERATE:
            print_agent("qa_manager", MAGENTA,
                        f"{YELLOW}{BOLD}⚠ MODERATE CONFIDENCE{RESET} — adding caveat:")
            print(f"  {BOLD}  → {best_answer}{RESET}")
            print(f"  {YELLOW}  ⚠ Note: Confidence is moderate ({score:.2f}). Consider verifying.{RESET}")
            speak(audio_url,
                  f"Confidence is {score:.2f}, which is moderate. "
                  f"The manager adds a caveat: the answer is {best_answer}, "
                  "but you may want to verify this from another source.")
        else:
            print_agent("qa_manager", MAGENTA,
                        f"{RED}{BOLD}✗ LOW CONFIDENCE{RESET} — flagging as unreliable:")
            print(f"  {RED}  → ⚠ This answer may be unreliable: {best_answer}{RESET}")
            print(f"  {RED}  → Please verify from authoritative sources.{RESET}")
            speak(audio_url,
                  f"Confidence is only {score:.2f}, which is low. "
                  "The manager flags the answer as potentially unreliable "
                  "and advises the user to check authoritative sources.")

        if elapsed:
            print(f"{DIM}  │  Time: {elapsed:.1f}s{RESET}")
        print(f"{DIM}  └{'─' * 69}{RESET}\n")

        wait_for_speech(8)

    # ── WRAP-UP (30s) ────────────────────────────────────────────────
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  Summary{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")

    print(f"  {BOLD}What we built:{RESET}")
    print(f"    • SemanticDensityEngine — core algorithm as a Python class")
    print(f"    • SemanticDensityTool — async CodedTool wrapper for neuro-san")
    print(f"    • HOCON agent network — qa_manager + answerer + confidence_checker")
    print(f"    • 9 unit tests, all passing")
    print(f"    • Demo scripts with TTS narration and t-SNE visualization\n")

    print(f"  {BOLD}Key insight:{RESET}")
    print(f"    Agents can now {GREEN}self-assess{RESET} their confidence and")
    print(f"    {GREEN}adapt their behavior{RESET} — no external calibration needed.\n")

    speak(audio_url,
          "To summarize: we turned a research prototype into a production "
          "Coded Tool. Any neuro-san agent network can now self-assess confidence "
          "and adapt its behavior. High confidence? Give the answer. "
          "Low confidence? Flag it. No external calibration needed. "
          "Thanks for watching!")
    wait_for_speech(12)

    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FedEx Day 5-minute demo")
    parser.add_argument("--audio-url", default=None, help="Audio server URL for TTS")
    parser.add_argument("--precomputed", default=None, help="Path to pre-computed results JSON")
    args = parser.parse_args()
    run_demo(audio_url=args.audio_url, precomputed_path=args.precomputed)
