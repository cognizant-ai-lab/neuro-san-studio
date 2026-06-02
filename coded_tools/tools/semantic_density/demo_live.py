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
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

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


class DemoRunner:
    """Orchestrates the FedEx Day semantic density demo.

    Simulates an agent network (qa_manager -> answerer + confidence_checker)
    with colored terminal output and optional TTS narration.
    """

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
            "question": "What is 19879 times 4390?",
            "category": "Arithmetic — exact answer but LLMs struggle",
        },
    ]

    def __init__(self, audio_url=None, precomputed_path=None):
        self._audio_url = audio_url
        self._precomputed_path = precomputed_path
        self._cached = None
        self._engine = None

    def _speak(self, text, voice="nova"):
        """Send TTS narration if audio URL is configured."""
        if not self._audio_url:
            return
        try:
            encoded = urllib.parse.urlencode({"text": text, "voice": voice})
            url = f"{self._audio_url}/speak?{encoded}"
            req = urllib.request.Request(url, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            logger.warning("TTS request failed: %s", exc)

    def _wait_for_speech(self, seconds):
        """Pause to let TTS finish playing."""
        time.sleep(seconds)

    def _color_for_score(self, score):
        """Return ANSI color code based on confidence threshold."""
        if score >= self.THRESHOLD_HIGH:
            return GREEN
        if score >= self.THRESHOLD_MODERATE:
            return YELLOW
        return RED

    def _print_agent(self, name, color, message):
        """Print a message as if from an agent."""
        print(f"  {color}{BOLD}[{name}]{RESET} {message}")

    def _load_engine_or_cache(self):
        """Load precomputed results or initialize the live engine."""
        if self._precomputed_path:
            with open(self._precomputed_path, encoding="utf-8") as f:
                self._cached = json.load(f)
        else:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from semantic_density_engine import SemanticDensityEngine
            self._engine = SemanticDensityEngine(
                generation_model="Qwen/Qwen2.5-7B-Instruct",
                nli_model="microsoft/deberta-large-mnli",
                device="cuda:0",
            )

    def _run_intro(self):
        """Intro section (~45s): what semantic density does + productionization story."""
        print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
        print(f"{BOLD}{CYAN}  ╔══════════════════════════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{CYAN}  ║   Semantic Density — Confidence for Agent Networks      ║{RESET}")
        print(f"{BOLD}{CYAN}  ║   FedEx Day 2026                                        ║{RESET}")
        print(f"{BOLD}{CYAN}  ╚══════════════════════════════════════════════════════════╝{RESET}")
        print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")

        self._speak(
            "Welcome to our FedEx Day project: Semantic Density for Agent Networks. "
            "We started with Xin's research demo, a standalone web app that measures "
            "how confident an LLM really is in its own answers.")
        self._wait_for_speech(10)

        self._speak(
            "The challenge was: this was a great algorithm, trapped in a single-page demo. "
            "It couldn't be reused by any other system. "
            "Our goal was to productionize it into a Coded Tool "
            "that any neuro-san agent network can call, "
            "provided it has access to a GPU for the inference.")
        self._wait_for_speech(12)

        self._speak(
            "Here's what the refactor looked like. "
            "Step one: we extracted the algorithm into a SemanticDensityEngine class "
            "with four clean methods, one for each step of the pipeline. "
            "Diverse beam search, token probability extraction, NLI distance scoring, "
            "and the final density calculation.")
        self._wait_for_speech(14)

        self._speak(
            "Step two: we wrapped that engine in a SemanticDensityTool, "
            "a CodedTool subclass with an async invoke method. "
            "Since GPU inference blocks the thread, we use asyncio to-thread "
            "to keep the event loop responsive for the rest of the agent network. "
            "A classmethod singleton ensures we only load the models once.")
        self._wait_for_speech(14)

        self._speak(
            "Step three: we defined the agent network in HOCON. "
            "A Soothsayer agent orchestrates two sub-agents: "
            "an Answerer that generates responses, "
            "and a Confidence Checker that calls our new Coded Tool. "
            "The Soothsayer then adapts its response based on the confidence score.")
        self._wait_for_speech(12)

        self._speak(
            "Before calling this done, we ran the code through our Code Fink playbook. "
            "That's a Devin playbook we built that reviews code through Dan Fink's eyes, "
            "one of our most thorough reviewers. "
            "It flagged a few things: the singleton was a standalone function, not on the class. "
            "The demo had bare functions instead of a proper class. "
            "And the exception handler was a catch-all except Exception. "
            "We cleaned all of that up. "
            "The singleton is now a classmethod. "
            "The demo is wrapped in a DemoRunner class. "
            "Exception handling uses specific types. "
            "And the async to-thread pattern has a comment justifying why it's needed. "
            "That should keep Dan happy when he reviews the PR.")
        self._wait_for_speech(22)

    def _run_question(self, index, question_info):
        """Run a single question through the simulated agent network."""
        question = question_info.get("question", "")
        category = question_info.get("category", "")

        print(f"{BOLD}{WHITE}  ┌─ Question {index}: {question}{RESET}")
        print(f"{DIM}  │  Category: {category}{RESET}")
        print(f"{DIM}  │{RESET}")

        category_label = category.split(" — ")[0].lower() if " — " in category else "unknown"
        self._speak(f"Question {index}: {question}. This is a {category_label} question.")
        self._wait_for_speech(5)

        # Step 1: Soothsayer receives the question
        self._print_agent("soothsayer", MAGENTA, f"Received question: \"{question}\"")
        self._print_agent("soothsayer", MAGENTA, "Delegating to answerer and confidence_checker...")
        print(f"{DIM}  │{RESET}")

        # Step 2: Get the answer
        if self._cached and question in self._cached:
            result = self._cached[question]
            best_answer = result.get("best_answer", "")
            score = result.get("confidence_score", 0.0)
            elapsed = result.get("elapsed", 0)
        else:
            start = time.time()
            result = self._engine.evaluate(question)
            elapsed = time.time() - start
            best_answer = result.get("best_answer", "")
            score = result.get("confidence_score", 0.0)

        self._print_agent("answerer", BLUE, f"\"{best_answer}\"")
        print(f"{DIM}  │{RESET}")

        # Step 3: Confidence check
        color = self._color_for_score(score)
        bar_length = 30
        filled = int(score * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        self._print_agent(
            "confidence_checker", CYAN,
            f"Score: {color}{BOLD}{score:.4f}{RESET} [{color}{bar}{RESET}]",
        )

        answers_with_scores = result.get("answers_with_scores", [])
        if answers_with_scores:
            print(f"{DIM}  │  Beam search answers:{RESET}")
            for j, entry in enumerate(answers_with_scores):
                d = entry.get("density", 0.0)
                dc = self._color_for_score(d)
                snippet = entry.get("answer", "")[:75]
                print(f"{DIM}  │    {j+1}. [{dc}d={d:.3f}{RESET}{DIM}] {snippet}{RESET}")
        print(f"{DIM}  │{RESET}")

        # Step 4: Soothsayer adapts behavior based on confidence
        if score >= self.THRESHOLD_HIGH:
            self._print_agent(
                "soothsayer", MAGENTA,
                f"{GREEN}{BOLD}✓ HIGH CONFIDENCE{RESET} — presenting answer directly:",
            )
            print(f"  {BOLD}  → {best_answer}{RESET}")
            self._speak(
                f"Confidence is {score:.2f}, which is high. "
                f"The Soothsayer presents the answer directly: {best_answer}")
        elif score >= self.THRESHOLD_MODERATE:
            self._print_agent(
                "soothsayer", MAGENTA,
                f"{YELLOW}{BOLD}⚠ MODERATE CONFIDENCE{RESET} — adding caveat:",
            )
            print(f"  {BOLD}  → {best_answer}{RESET}")
            print(f"  {YELLOW}  ⚠ Note: Confidence is moderate ({score:.2f}). Consider verifying.{RESET}")
            self._speak(
                f"Confidence is {score:.2f}, which is moderate. "
                f"The Soothsayer adds a caveat: the answer is {best_answer}, "
                "but you may want to verify this from another source.")
        else:
            self._print_agent(
                "soothsayer", MAGENTA,
                f"{RED}{BOLD}✗ LOW CONFIDENCE{RESET} — flagging as unreliable:",
            )
            print(f"  {RED}  → ⚠ This answer may be unreliable: {best_answer}{RESET}")
            print(f"  {RED}  → Please verify from authoritative sources.{RESET}")
            self._speak(
                f"Confidence is only {score:.2f}, which is low. "
                "The Soothsayer flags the answer as potentially unreliable "
                "and advises the user to check authoritative sources.")

        if elapsed:
            print(f"{DIM}  │  Time: {elapsed:.1f}s{RESET}")
        print(f"{DIM}  └{'─' * 69}{RESET}\n")

        self._wait_for_speech(8)

    def _run_wrapup(self):
        """Wrap-up section (~30s)."""
        print(f"{BOLD}{CYAN}{'═' * 70}{RESET}")
        print(f"{BOLD}{CYAN}  Summary{RESET}")
        print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")

        print(f"  {BOLD}What we built:{RESET}")
        print(f"    • SemanticDensityEngine — core algorithm as a Python class")
        print(f"    • SemanticDensityTool — async CodedTool wrapper for neuro-san")
        print(f"    • HOCON agent network — soothsayer + answerer + confidence_checker")
        print(f"    • 9 unit tests, all passing")
        print(f"    • Demo scripts with TTS narration and t-SNE visualization\n")

        print(f"  {BOLD}Key insight:{RESET}")
        print(f"    Agents can now {GREEN}self-assess{RESET} their confidence and")
        print(f"    {GREEN}adapt their behavior{RESET} — no external calibration needed.\n")

        self._speak(
            "To summarize: we took a research prototype, refactored the algorithm "
            "into a clean engine class, wrapped it as a CodedTool with proper async support, "
            "and wired it into an agent network via HOCON. "
            "Any neuro-san network with GPU access can now self-assess confidence. "
            "High confidence? Give the answer. Low confidence? Flag it. "
            "No external calibration needed. Thanks for watching!")
        self._wait_for_speech(14)

        print(f"{BOLD}{CYAN}{'═' * 70}{RESET}\n")

    def run(self):
        """Run the full 5-minute FedEx Day demo."""
        self._load_engine_or_cache()
        self._run_intro()

        print(f"{BOLD}{WHITE}  Agent Network: soothsayer → answerer + confidence_checker{RESET}")
        print(f"{DIM}  The Soothsayer asks for an answer, checks confidence,{RESET}")
        print(f"{DIM}  then adapts its response based on the score.{RESET}\n")
        print(f"{DIM}{'─' * 70}{RESET}\n")

        self._speak(
            "Let's see it in action. We have a simple agent network: "
            "a Soothsayer that delegates to an Answerer agent and a Confidence Checker. "
            "Watch how the Soothsayer changes its behavior based on the confidence score.")
        self._wait_for_speech(10)

        for i, q_info in enumerate(self.DEMO_QUESTIONS, 1):
            self._run_question(i, q_info)

        self._run_wrapup()

    @staticmethod
    def main():
        """CLI entrypoint."""
        parser = argparse.ArgumentParser(description="FedEx Day 5-minute demo")
        parser.add_argument("--audio-url", default=None, help="Audio server URL for TTS")
        parser.add_argument("--precomputed", default=None, help="Path to pre-computed results JSON")
        cli_args = parser.parse_args()

        demo = DemoRunner(
            audio_url=cli_args.audio_url,
            precomputed_path=cli_args.precomputed,
        )
        demo.run()


if __name__ == "__main__":
    DemoRunner.main()
