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
network_consultant's fixture-running engine: run every ANTeGen-generated test fixture for a
network and report pass/fail per fixture, without going through pytest. Reuses neuro_san's own
data-driven test driver -- the same one `make test-integration` uses -- so results match
exactly what CI would report.

Imported by network_consultant.py, which adds the consult-and-fix loop on top. The dependency
only points that way: nothing here knows the loop exists, so a caller that just wants to run a
suite pays for none of it.

The direct-session environment defaults are initialized before neuro-san is imported so its
configuration is consistent for both fixture-only and consult-and-fix callers.
"""

import concurrent.futures
import glob
import importlib
import json
import logging
import os
import queue
import re
import threading
import time
from logging.handlers import QueueHandler
from typing import Any
from unittest import TestCase

from leaf_common.time.timeout_reached_exception import TimeoutReachedException

from neuro_san_studio.network_consultant.consultant_environment import ConsultantEnvironment
from neuro_san_studio.network_consultant.scorecard_assert_forwarder import ScorecardAssertForwarder

# Not __name__: network_consultant.py runs as "__main__" via `python -m`, and logging both halves
# under one name keeps the job log a single readable stream for nsflow to tail.
logger = logging.getLogger("network_consultant")

# Ceiling on how many fixtures run at once. Each one nests its own pool underneath -- neuro-san's
# DataDrivenAgentTestDriver.one_test runs a fixture's success_ratio iterations in parallel too --
# so peak live agent sessions is this times the ratio, and an uncapped 15-fixture suite at 3/3
# was 45 of them: straight into provider rate limits, which surface here as fixture failures and
# send consultant off to "fix" a network that was fine.
MAX_PARALLEL_FIXTURES = 7
# Matches coded_tools/agent_network_consultant/read_thinking_trace.py's THINKING_DIR
# and the "--- <agent_origin> ---" section headers it parses.
IMPROVEMENT_THINKING_DIR = os.path.join("logs", "thinking_dir", "improvement")

# Matches ThinkingFileMessageProcessor._write_to_file's entry header exactly:
# f"\n[{message_type_str}{use_origin}] @ {timestamp_str}:\n"
_THINKING_ENTRY_HEADER = re.compile(r"^\[(?P<type>[A-Z_]+)[^\]]*\] @ .+:$", re.MULTILINE)

# Telemetry keys unique to neuro-san's own token/cost-accounting report -- never part of an
# agent's actual reasoning or AAOSA dialogue.
_COST_ACCOUNTING_KEYS = ("prompt_tokens", "completion_tokens", "total_cost", "total_tokens")
SUCCESS_RATIO_PATTERN = re.compile(r'("success_ratio"\s*:\s*")(\d+/\d+)(")')

# Set by nsflow's backend job runner when this script is launched as a detached subprocess
# with no interactive stdin -- input() would just hang forever waiting for a terminal that
# doesn't exist. When set, clarification questions are exchanged via files in this directory
# instead (see _ask_headless).
NSFLOW_JOB_ID = os.environ.get("NSFLOW_JOB_ID")
NSFLOW_JOB_DIR = os.environ.get("NSFLOW_JOB_DIR")


class FixtureRunner:
    """Run and report Network Consultant fixtures without invoking pytest."""

    API_KEY_ERROR_MARKER = "API KEY error detected"

    @staticmethod
    def _create_driver(asserts: ScorecardAssertForwarder, fixture_name: str) -> Any:
        """Create the neuro-san driver after consultant environment initialization."""
        ConsultantEnvironment.configure()
        driver_module = importlib.import_module("neuro_san.test.driver.data_driven_agent_test_driver")
        return driver_module.DataDrivenAgentTestDriver(asserts, test_name=fixture_name)

    @staticmethod
    def _is_noise_paragraph(paragraph: str) -> bool:
        """A chat_context dump (conversation-continuation bookkeeping) or a token/cost-accounting
        report -- both are telemetry a diagnosing agent has no use for, not dialogue content."""
        if paragraph.startswith("chat_context:"):
            return True
        body = paragraph.strip("`").removeprefix("json").strip() if paragraph.startswith("```") else paragraph
        return body.startswith("{") and any(key in body for key in _COST_ACCOUNTING_KEYS)

    @staticmethod
    def _strip_system_entries(raw_text: str) -> str:
        """Drop every [SYSTEM ...] entry (an agent's full instructions/system prompt) from one
        agent's raw thinking file, keeping everything else -- its own reasoning, the AAOSA
        inquiry/response exchange with its down-chain agents, tool calls/results, final answer.
        Also drops chat_context dumps and cost-accounting reports, wherever they appear."""
        headers = list(_THINKING_ENTRY_HEADER.finditer(raw_text))
        if not headers:
            return raw_text.strip()
        kept: list[str] = []
        for index, header in enumerate(headers):
            if header.group("type") == "SYSTEM":
                continue
            end = headers[index + 1].start() if index + 1 < len(headers) else len(raw_text)
            # Split header from body BEFORE paragraph-splitting: a noise block (chat_context dump,
            # cost report) can immediately follow the header with no blank line in between, which
            # would otherwise glue it onto the header into one paragraph that starts with "[TYPE...]"
            # instead of "{" or "```" -- invisible to _is_noise_paragraph.
            header_line = header.group(0)
            body = raw_text[header.end() : end].strip()
            paragraphs = [p for p in body.split("\n\n") if not FixtureRunner._is_noise_paragraph(p.strip())]
            body = "\n\n".join(paragraphs).strip()
            entry = f"{header_line}\n{body}" if body else ""
            if entry:
                kept.append(entry)
        return "\n\n".join(kept)

    @staticmethod
    def _iteration_of(run_dir: str) -> str:
        """Return a thinking directory's success-ratio iteration suffix."""
        match = re.search(r"_(\d+)$", os.path.basename(run_dir))
        return match.group(1) if match else ""

    @staticmethod
    def _thinking_run_dirs(basis_dir: str, fixture_name: str, started: float) -> list[str]:
        """Find this fixture run's thinking directories for one representative iteration."""
        run_dirs = sorted(
            directory
            for directory in glob.glob(os.path.join(basis_dir, f"*_{fixture_name}*"))
            if os.path.isdir(directory) and os.path.getmtime(directory) >= started
        )
        if not run_dirs:
            return []

        # A fixture with success_ratio > 1 (e.g. "3/3") runs several iterations of the SAME
        # interactions concurrently (see DataDrivenAgentTestDriver.one_test), each iteration
        # getting its own thinking directories, named "..._<iteration_index>". Consolidating every
        # iteration would glue N near-identical retries together under one section per agent --
        # wasted tokens, and it obscures which attempt a diagnosing agent is even looking at. Keep
        # only the earliest iteration's directories (every turn of it, since turns of the SAME
        # iteration share that suffix) -- a failing fixture almost always fails the same way across
        # iterations, so one is representative. A single-iteration fixture (no suffix at all) is
        # unaffected: every directory shares the same (empty) key below.
        first_iteration = FixtureRunner._iteration_of(run_dirs[0])
        return [directory for directory in run_dirs if FixtureRunner._iteration_of(directory) == first_iteration]

    @staticmethod
    def _read_thinking_section(path: str, agent_file: str) -> tuple[str, str]:
        """Read and filter one agent's thinking trace section."""
        with open(path, encoding="utf-8", errors="replace") as file:
            raw = file.read()
        # First line is always "Agent: <origin_str>\n" (ThinkingFileMessageProcessor); use that
        # as the true origin name rather than the "/"->"__" sanitized filename.
        first_line, _, rest = raw.partition("\n")
        agent_origin = first_line[len("Agent: ") :].strip() if first_line.startswith("Agent: ") else agent_file
        return agent_origin, FixtureRunner._strip_system_entries(rest)

    @staticmethod
    def _thinking_sections(run_dirs: list[str]) -> dict[str, list[str]]:
        """Group filtered thinking traces by their originating agent."""
        sections: dict[str, list[str]] = {}
        for run_dir in run_dirs:
            for agent_file in sorted(os.listdir(run_dir)):
                path = os.path.join(run_dir, agent_file)
                if not os.path.isfile(path):
                    continue
                agent_origin, filtered = FixtureRunner._read_thinking_section(path, agent_file)
                if filtered:
                    sections.setdefault(agent_origin, []).append(filtered)
        return sections

    @staticmethod
    def _write_consolidated_thinking(fixture_name: str, started: float) -> None:
        """Consolidate one fixture run's raw per-agent thinking into a filtered diagnostic trace.

        Only the earliest success-ratio iteration is retained. Older directories are excluded by
        modification time, system prompts and telemetry are stripped, and each agent gets one
        section. Missing configuration or missing output is a no-op.

        Neuro-san currently names per-turn directories with second-level timestamp precision. Two
        turns from one iteration can therefore collide upstream; this module cannot recover a trace
        that the installed package already replaced.
        """
        basis_dir = os.environ.get("AGENT_TEST_THINKING_BASIS")
        if not basis_dir:
            return
        run_dirs = FixtureRunner._thinking_run_dirs(basis_dir, fixture_name, started)
        sections = FixtureRunner._thinking_sections(run_dirs)

        if not sections:
            return

        os.makedirs(IMPROVEMENT_THINKING_DIR, exist_ok=True)
        out_path = os.path.join(IMPROVEMENT_THINKING_DIR, f"{fixture_name}.txt")
        with open(out_path, "w", encoding="utf-8") as out_file:
            for agent_origin, chunks in sections.items():
                out_file.write(f"--- {agent_origin} ---\n")
                out_file.write("\n\n".join(chunks))
                out_file.write("\n\n")
        logger.info("Consolidated thinking trace written: %s (%d agent(s))", out_path, len(sections))

    @staticmethod
    def fixture_paths(fixtures_dir: str) -> list[str]:
        """:return: Sorted list of fixture HOCON paths under tests/fixtures/<fixtures_dir>/."""
        search_dir = os.path.join("tests", "fixtures", fixtures_dir)
        return sorted(glob.glob(os.path.join(search_dir, "*.hocon")))

    @staticmethod
    def _set_success_ratio_for_paths(paths: list[str], ratio: str) -> dict[str, str]:
        """Overwrite success_ratio in place for exactly the given fixture paths."""
        originals: dict[str, str] = {}
        for path in paths:
            with open(path, encoding="utf-8") as fixture_file:
                text = fixture_file.read()
            match = SUCCESS_RATIO_PATTERN.search(text)
            if not match or match.group(2) == ratio:
                continue
            originals.update({path: match.group(2)})
            with open(path, "w", encoding="utf-8") as fixture_file:
                fixture_file.write(SUCCESS_RATIO_PATTERN.sub(rf"\g<1>{ratio}\g<3>", text, count=1))
            logger.info("success_ratio %s -> %s: %s", originals.get(path), ratio, path)
        return originals

    @staticmethod
    def set_success_ratio_for_fixtures(fixtures_dir: str, fixture_names: list[str], ratio: str) -> dict[str, str]:
        """
        Overwrite success_ratio in place for specific fixtures only (by basename), e.g. those the
        consultant flagged CONFIDENT_FIX for -- letting most fixtures stay cheap (1/1) while only
        the ones worth the extra token spend get re-verified at a stricter ratio.

        :param fixtures_dir: Network path under tests/fixtures/, as in run_all_tests.
        :param fixture_names: Basenames (e.g. "foo.hocon") to change; others are left untouched.
        :param ratio: New value, e.g. "3/3".
        :return: {fixture_path: original_ratio} for every fixture actually changed, so the
                 caller can restore it later via restore_success_ratios.
        """
        wanted = set(fixture_names)
        paths = [path for path in FixtureRunner.fixture_paths(fixtures_dir) if os.path.basename(path) in wanted]
        return FixtureRunner._set_success_ratio_for_paths(paths, ratio)

    @staticmethod
    def set_success_ratios(fixtures_dir: str, ratio: str) -> dict[str, str]:
        """
        Overwrite every fixture's top-level success_ratio in place.

        :param fixtures_dir: Network path under tests/fixtures/, as in run_all_tests.
        :param ratio: New value, e.g. "3/3".
        :return: {fixture_path: original_ratio} for every fixture actually changed, so the
                 caller can restore it later via restore_success_ratios.
        """
        originals = FixtureRunner._set_success_ratio_for_paths(FixtureRunner.fixture_paths(fixtures_dir), ratio)
        logger.info(
            "FixtureRunner.set_success_ratios(%s, %s): changed %d/%d fixtures",
            fixtures_dir,
            ratio,
            len(originals),
            len(FixtureRunner.fixture_paths(fixtures_dir)),
        )
        return originals

    @staticmethod
    def restore_success_ratios(originals: dict[str, str]) -> None:
        """Undo set_success_ratios, restoring each fixture's original success_ratio.

        Never raises, and never gives up partway. This runs from main()'s `finally` and from the
        SIGTERM handler, where an exception on one fixture would abandon every fixture after it
        still bumped -- and, from the `finally`, would replace whatever actually went wrong with a
        confusing error from the cleanup path. A fixture can legitimately be gone by now (deleted
        while the run was in flight), and a missing file needs no restoring anyway.
        """
        restored = 0
        for path, ratio in originals.items():
            try:
                with open(path, encoding="utf-8") as fixture_file:
                    text = fixture_file.read()
                with open(path, "w", encoding="utf-8") as fixture_file:
                    fixture_file.write(SUCCESS_RATIO_PATTERN.sub(rf"\g<1>{ratio}\g<3>", text, count=1))
            except OSError as error:
                logger.warning("Could not restore success_ratio %s on %s: %s", ratio, path, error)
                continue
            restored += 1
            logger.info("success_ratio restored -> %s: %s", ratio, path)
        logger.info("restore_success_ratios: restored %d/%d fixture(s)", restored, len(originals))

    @staticmethod
    def run_real_ratio_suite(fixtures_dir: str, original_ratios: dict[str, str], ratio: str) -> list[dict[str, Any]]:
        """Run the full suite for an authoritative Before/After bar. Those bars always score against
        each fixture's own success_ratio -- that is the network's real score -- so lift any
        CONFIDENT_FIX bump for the duration of the run, then put it straight back: the loop often
        continues afterwards, and a fix the consultant vouched for should stay on its stricter ratio
        when it does.

        `original_ratios` is updated in place, so it keeps tracking exactly what needs undoing.
        """
        bumped_paths = list(original_ratios)
        FixtureRunner.restore_success_ratios(original_ratios)
        original_ratios.clear()
        try:
            return FixtureRunner.run_all_tests(fixtures_dir)
        finally:
            original_ratios.update(FixtureRunner._set_success_ratio_for_paths(bumped_paths, ratio))

    @staticmethod
    def scorecard_message(cause: BaseException, scorecard: list[tuple[str, int, int]]) -> str:
        """Turn a fixture's criteria into a report naming EVERY failure, not just the first.

        neuro-san checks all of them and then re-raises only asserts[0], so a consultant fixing a
        fixture used to see one failure of several and learn about the next a whole round later.

        Only the failures are listed. The count still says how many criteria there were in total
        ("2 of 6"), so the scale is visible without the message carrying -- and persisting -- the
        full text of everything that already works.
        """
        if not scorecard:
            return str(cause)

        failing = [(name, met, total) for name, met, total in scorecard if met < total]
        if not failing:
            return str(cause)

        lines = [f"{len(failing)} of {len(scorecard)} acceptance criteria failing:"]
        for name, met, total in failing:
            # "met on 1 of 3" is a flaky criterion, not a broken one -- rewriting an agent that is
            # already right a third of the time makes it worse, and the bump to a stricter ratio
            # then turns a 1-in-3 into a 1-in-27.
            suffix = f"  (met on {met} of {total} attempts)" if met else ""
            lines.append(f"  - {name}{suffix}")
        lines.append("")
        lines.append(f"First failure in detail:\n{cause}")
        return "\n".join(lines)

    @staticmethod
    def _fixture_verdict(
        fixture_path: str,
        asserts: ScorecardAssertForwarder,
        passed: bool,
        message: str | None,
        infrastructure_error: bool = False,
    ) -> dict[str, Any]:
        """Build a consistently shaped fixture result."""
        fixture_name = os.path.basename(fixture_path)
        met, total = (0, 0) if infrastructure_error else asserts.criteria_counts()
        return {
            "fixture": fixture_name,
            "path": fixture_path,
            "passed": passed,
            "message": message,
            "infrastructure_error": infrastructure_error,
            "criteria_passed": met,
            "criteria_total": total,
        }

    @staticmethod
    def _api_key_error_capture() -> QueueHandler:
        """Return a standard logging handler filtered to API-key errors on this thread."""
        capture_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
        capture = QueueHandler(capture_queue)
        capture.setLevel(logging.ERROR)
        fixture_thread_id = threading.get_ident()
        capture.addFilter(
            lambda record: (
                record.thread == fixture_thread_id and FixtureRunner.API_KEY_ERROR_MARKER in record.getMessage()
            )
        )
        return capture

    @staticmethod
    def _captured_api_key_summary(capture: QueueHandler) -> str | None:
        """Drain captured provider API-key errors and return one summary when present."""
        messages: list[str] = []
        while True:
            try:
                record = capture.queue.get_nowait()
            except queue.Empty:
                return "\n".join(messages) or None
            messages.append(record.getMessage().strip())

    @staticmethod
    def run_fixture(fixture_path: str) -> dict[str, Any]:
        """
        :param fixture_path: Path to a single test fixture HOCON file.
        :return: Result with fixture/path/passed/message/infrastructure_error fields.
        """
        # one_test() raises a single AssertionError (summarizing every interaction/iteration
        # mismatch) only if the fixture's success_ratio wasn't met, so a plain try/except
        # is all the aggregation this needs.
        fixture_name = os.path.basename(fixture_path)
        asserts = ScorecardAssertForwarder(TestCase())
        driver = FixtureRunner._create_driver(asserts, fixture_name)

        logger.info("run_fixture start: %s", fixture_name)
        started = time.time()
        capture = FixtureRunner._api_key_error_capture()
        root_logger = logging.getLogger()
        root_logger.addHandler(capture)
        try:
            driver.one_test(fixture_path)
            logger.info("run_fixture pass (%.1fs): %s", time.time() - started, fixture_name)
            return FixtureRunner._fixture_verdict(fixture_path, asserts, True, None)
        except AssertionError as exc:
            cause = exc.__cause__ or exc
            api_key_summary = FixtureRunner._captured_api_key_summary(capture)
            if api_key_summary:
                logger.warning(
                    "run_fixture infrastructure_error (%.1fs, API key error): %s", time.time() - started, fixture_name
                )
                return FixtureRunner._fixture_verdict(
                    fixture_path,
                    asserts,
                    False,
                    f"{api_key_summary}\n\n(Original assertion, likely a symptom of the above: {cause})",
                    infrastructure_error=True,
                )
            message = FixtureRunner.scorecard_message(cause, asserts.scorecard())
            met, total = asserts.criteria_counts()
            logger.info(
                "run_fixture fail (%.1fs): %s (%d/%d criteria) -- %s",
                time.time() - started,
                fixture_name,
                met,
                total,
                cause,
            )
            return FixtureRunner._fixture_verdict(fixture_path, asserts, False, message)
        except TimeoutReachedException as exc:
            # exc carries no message of its own (leaf_common never sets one) -- report the interaction's
            # own timeout budget so a human knows to raise timeout_in_seconds, not chase a phantom bug.
            limit = exc.timeout.get_limit_in_seconds()
            name = exc.timeout.get_name() or fixture_name
            message = (
                f"TIMEOUT_ISSUE: {fixture_name}: interaction {name!r} exceeded its {limit:.0f}s timeout -- "
                f"increase timeout_in_seconds in this fixture."
            )
            logger.warning(
                "run_fixture infrastructure_error (%.1fs, timeout): %s", time.time() - started, fixture_name
            )
            return FixtureRunner._fixture_verdict(fixture_path, asserts, False, message, infrastructure_error=True)
        except (AttributeError, ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            message = f"{type(exc).__name__}: {exc}"
            api_key_summary = FixtureRunner._captured_api_key_summary(capture)
            if api_key_summary:
                message = f"{api_key_summary}\n\n(Original exception, likely a symptom of the above: {message})"
            logger.warning(
                "run_fixture infrastructure_error (%.1fs): %s -- %s",
                time.time() - started,
                fixture_name,
                type(exc).__name__,
            )
            return FixtureRunner._fixture_verdict(fixture_path, asserts, False, message, infrastructure_error=True)
        finally:
            root_logger.removeHandler(capture)
            FixtureRunner._write_consolidated_thinking(fixture_name, started)

    @staticmethod
    def run_all_tests(fixtures_dir: str, only_fixtures: list[str] | None = None) -> list[dict[str, Any]]:
        """
        :param fixtures_dir: Network path under tests/fixtures/, e.g. "generated/coffee_shop"
                    (matches ANTeGen's target_agent_name, i.e. the hocon file path minus ".hocon").
        :param only_fixtures: If given, run only these basenames (e.g. ["foo.hocon"]) instead of
                    every fixture in the directory -- lets a caller cheaply re-verify just the
                    handful of fixtures it touched instead of paying for the full suite every round.
        :return: One result dict (see run_fixture) per fixture found, in fixture_paths order
                    (independent of the order fixtures actually finished in).
        """
        paths = FixtureRunner.fixture_paths(fixtures_dir)
        if only_fixtures is not None:
            wanted = set(only_fixtures)
            paths = [path for path in paths if os.path.basename(path) in wanted]
        if not paths:
            search_dir = os.path.join("tests", "fixtures", fixtures_dir)
            logger.warning("run_all_tests: no fixtures found under %s (only_fixtures=%s)", search_dir, only_fixtures)
            return [
                {
                    "fixture": "<fixture discovery>",
                    "path": search_dir,
                    "passed": False,
                    "message": f"No test fixtures found under '{search_dir}'.",
                    "infrastructure_error": True,
                }
            ]
        logger.info(
            "run_all_tests start: %d fixture(s) under %s%s",
            len(paths),
            fixtures_dir,
            f" (subset of {only_fixtures})" if only_fixtures is not None else "",
        )
        started = time.time()
        # Run fixtures concurrently (one thread each) instead of one at a time -- run_fixture
        # is already safe to call this way: _write_consolidated_thinking is keyed by fixture name,
        # and each log capture filters to its own thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(paths), MAX_PARALLEL_FIXTURES)) as executor:
            results = list(executor.map(FixtureRunner.run_fixture, paths))
        passed = sum(1 for result in results if result.get("passed"))
        logger.info(
            "run_all_tests done (%.1fs): %d/%d passing under %s",
            time.time() - started,
            passed,
            len(results),
            fixtures_dir,
        )
        # Written here rather than at each call site: every path that produces per-fixture
        # verdicts goes through this function, so one call covers the whole runner.
        FixtureRunner.write_fixture_results(results)
        return results

    @staticmethod
    def write_fixture_results(results: list[dict[str, Any]]) -> None:
        """Record each fixture's verdict for an nsflow-launched run, so the UI can show pass/fail
        and the reason per test instead of leaving them to be scraped out of the log.

        Merged into the existing map rather than replacing it: the runner frequently re-tests only
        the fixtures that were failing, and a subset re-check says nothing about the ones it didn't
        run -- they keep their last known verdict, exactly as ProgressTracker carries them forward
        for the chart. A no-op outside an nsflow job, like the tracker's own write.

        :param results: run_fixture result dicts for the fixtures this round actually ran
        """
        if not (NSFLOW_JOB_ID and NSFLOW_JOB_DIR):
            return
        path = os.path.join(NSFLOW_JOB_DIR, f"{NSFLOW_JOB_ID}.results.json")
        try:
            with open(path, encoding="utf-8") as results_file:
                merged: dict[str, Any] = json.load(results_file)
        except (OSError, json.JSONDecodeError):
            # Absent on the first round, and a half-written file is not worth failing a test run
            # over -- this round's results are about to replace what matters in it anyway.
            merged = {}
        for result in results:
            fixture_name = result.get("fixture", "")
            merged.update(
                {
                    fixture_name: {
                        "passed": bool(result.get("passed")),
                        "message": result.get("message"),
                        "infrastructure_error": bool(result.get("infrastructure_error")),
                    }
                }
            )
        try:
            with open(path, "w", encoding="utf-8") as results_file:
                json.dump(merged, results_file, indent=2)
        except OSError as error:
            logger.warning("Could not write fixture results to %s: %s", path, error)
