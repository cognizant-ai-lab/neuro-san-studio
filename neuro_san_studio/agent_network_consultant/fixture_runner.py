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
Reusable fixture-running engine: run every ANTeGen-generated test fixture for a
network and report pass/fail per fixture, without going through pytest. Reuses neuro_san's own
data-driven test driver -- the same one `make test-integration` uses -- so results match
exactly what CI would report.

Network Consultant adds its consult-and-fix loop on top. The dependency only points that way:
nothing here knows the loop exists, so a caller that only wants to run a suite pays for none of it.

Direct-session configuration is scoped to a suite and restored before control returns to the caller.
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
from collections.abc import Mapping
from copy import deepcopy
from functools import partial
from logging.handlers import QueueHandler
from typing import Any
from unittest import TestCase

from leaf_common.time.timeout_reached_exception import TimeoutReachedException

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.scorecard_assert_forwarder import ScorecardAssertForwarder
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector

# Not __name__: network_consultant.py runs as "__main__" via `python -m`, and logging both halves
# under one name keeps the job log a single readable stream for nsflow to tail.
logger = logging.getLogger("network_consultant")

# Ceiling on how many fixtures run at once. Each one nests its own pool underneath -- neuro-san's
# DataDrivenAgentTestDriver.one_test runs a fixture's success_ratio iterations in parallel too --
# so peak live agent sessions is this times the ratio, and an uncapped 15-fixture suite at 3/3
# was 45 of them: straight into provider rate limits, which surface here as fixture failures and
# send consultant off to "fix" a network that was fine.
MAX_PARALLEL_FIXTURES = 7
SENSITIVE_ENV_NAME_PATTERN = re.compile(
    r"(?:api[_-]?key|authorization|credential|password|secret|access[_-]?token)", re.IGNORECASE
)
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(\b[A-Za-z0-9_-]*(?:api[_-]?key|authorization|credential|password|secret|access[_-]?token)"
    r"[A-Za-z0-9_-]*\s*[:=]\s*)(?:Bearer\s+)?[^\s,;]+",
    re.IGNORECASE,
)
SENSITIVE_TOKEN_PATTERN = re.compile(
    r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]+|xox[baprs]-[A-Za-z0-9-]+)\b"
)
BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)


class FixtureRunner:
    """Run and report agent-network fixtures without invoking pytest."""

    API_KEY_ERROR_MARKER = "API KEY error detected"

    @staticmethod
    def redact_sensitive_text(text: str) -> str:
        """
        Redact credential values from a fixture failure message before it leaves the runner.

        :param text: The failure text to sanitize.
        :return: The text with credential values replaced by a redaction marker.
        """
        redacted = text
        for name, value in os.environ.items():
            if len(value) >= 8 and SENSITIVE_ENV_NAME_PATTERN.search(name):
                redacted = redacted.replace(value, "[REDACTED]")
        redacted = SENSITIVE_ASSIGNMENT_PATTERN.sub(r"\1[REDACTED]", redacted)
        redacted = SENSITIVE_TOKEN_PATTERN.sub("[REDACTED]", redacted)
        return BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", redacted)

    @staticmethod
    def _create_driver(asserts: ScorecardAssertForwarder, fixture_name: str) -> Any:
        """
        Create the neuro-san driver inside the active test-environment scope.

        :param asserts: The assertion forwarder used to collect fixture results.
        :param fixture_name: The fixture base name.
        :return: The resulting value.
        """
        driver_module = importlib.import_module("neuro_san.test.driver.data_driven_agent_test_driver")
        return driver_module.DataDrivenAgentTestDriver(asserts, test_name=fixture_name)

    @staticmethod
    def fixture_paths(fixtures_dir: str) -> list[str]:
        """
        Fixture paths.

        :param fixtures_dir: The network fixture directory.
        :return: Sorted list of fixture HOCON paths under tests/fixtures/<fixtures_dir>/.
        """
        search_dir = os.path.join("tests", "fixtures", fixtures_dir)
        return sorted(glob.glob(os.path.join(search_dir, "*.hocon")))

    @staticmethod
    def _select_fixture_paths(
        paths: list[str],
        fixtures_dir: str,
        only_fixtures: list[str] | None,
    ) -> list[str]:
        """
        Return the requested fixture paths after rejecting unknown fixture names.

        :param paths: Every fixture path discovered under the selected fixture directory.
        :param fixtures_dir: Network path under tests/fixtures/ used in validation errors.
        :param only_fixtures: The optional exact fixture basenames to select.
        :return: Every discovered path, or the validated requested subset.
        :raises ValueError: If a requested fixture does not exist in the selected fixture directory.
        """
        if only_fixtures is None:
            return paths
        wanted = set(only_fixtures)
        available_fixture_names: set[str] = set()
        for path in paths:
            available_fixture_names.add(os.path.basename(path))
        missing_fixture_names: list[str] = []
        for fixture_name in wanted:
            if fixture_name not in available_fixture_names:
                missing_fixture_names.append(fixture_name)
        if missing_fixture_names:
            missing_fixture_names.sort()
            missing_names = ", ".join(missing_fixture_names)
            raise ValueError(f"Unknown fixture selection under '{fixtures_dir}': {missing_names}.")
        selected_paths: list[str] = []
        for path in paths:
            if os.path.basename(path) in wanted:
                selected_paths.append(path)
        return selected_paths

    @staticmethod
    def _run_with_ratio_override(
        fixture_path: str,
        asserts: ScorecardAssertForwarder,
        fixture_name: str,
        success_ratio: str,
    ) -> None:
        """
        Run one parsed fixture with an in-memory success-ratio override.

        This mirrors ``DataDrivenAgentTestDriver.one_test`` while changing only the parsed test-case mapping. The
        upstream driver does not currently accept an override, and changing the mapping avoids modifying the fixture.

        :param fixture_path: Path to a single test fixture HOCON file.
        :param asserts: The assertion forwarder used to collect fixture results.
        :param fixture_name: The fixture base name.
        :param success_ratio: The temporary success ratio used for this execution only.
        """
        tests_util_module = importlib.import_module("neuro_san.test.util.tests_util")
        tests_driver_module = importlib.import_module("neuro_san.test.driver.data_driven_tests_driver")
        test_case: dict[str, Any] = tests_util_module.TestsUtil.parse_hocon_test_case(None, fixture_path)
        test_case["success_ratio"] = success_ratio
        agent = test_case.get("agent")
        asserts.assertIsNotNone(agent)
        required_successes, iteration_count = FixtureRunner._ratio_counts(asserts, success_ratio)
        test_cases = FixtureRunner._repeated_test_cases(test_case, iteration_count)
        test_driver = tests_driver_module.DataDrivenTestsDriver(asserts, test_name=fixture_name)
        test_results = test_driver.run_tests(test_cases, required_successes)
        successful = FixtureRunner._successful_result_count(test_results, required_successes)
        if successful >= required_successes:
            return
        FixtureRunner._raise_ratio_failure(
            test_results,
            successful,
            (required_successes, iteration_count),
            agent,
            fixture_path,
        )

    @staticmethod
    def _ratio_counts(asserts: ScorecardAssertForwarder, success_ratio: str) -> tuple[int, int]:
        """
        Validate a success ratio and return its bounded required and total counts.

        :param asserts: The assertion forwarder used to report an invalid ratio.
        :param success_ratio: The success ratio formatted as required attempts over total attempts.
        :return: The bounded required success count and iteration count.
        """
        asserts.assertIn("/", success_ratio)
        ratio_parts = success_ratio.split("/")
        iteration_count = max(1, int(ratio_parts[-1]))
        return min(int(ratio_parts[0]), iteration_count), iteration_count

    @staticmethod
    def _repeated_test_cases(test_case: dict[str, Any], iteration_count: int) -> list[dict[str, Any]]:
        """
        Create an isolated test-case mapping for every fixture attempt.

        :param test_case: The parsed fixture test case.
        :param iteration_count: The number of fixture attempts to create.
        :return: Deep copies of the fixture test case.
        """
        test_cases: list[dict[str, Any]] = []
        for _index in range(iteration_count):
            test_cases.append(deepcopy(test_case))
        return test_cases

    @staticmethod
    def _successful_result_count(test_results: list[Any], required_successes: int) -> int:
        """
        Count successful attempts until the fixture threshold is met.

        :param test_results: The captured result for every completed fixture attempt.
        :param required_successes: The number of successful attempts required to pass.
        :return: The observed successful attempt count, capped at the required count.
        """
        successful = 0
        for test_result in test_results:
            if not test_result.get_asserts():
                successful += 1
                if successful >= required_successes:
                    return successful
        return successful

    @staticmethod
    def _raise_ratio_failure(
        test_results: list[Any],
        successful: int,
        ratio_counts: tuple[int, int],
        agent: Any,
        fixture_path: str,
    ) -> None:
        """
        Raise the upstream-compatible error from the first failed fixture attempt.

        :param test_results: The captured result for every completed fixture attempt.
        :param successful: The observed successful attempt count.
        :param ratio_counts: The required success count and total attempted fixture count.
        :param agent: The fixture's configured agent name.
        :param fixture_path: Path to the source fixture HOCON file.
        :raises AssertionError: Raised from the first captured assertion when the ratio was not met.
        """
        required_successes, iteration_count = ratio_counts
        for test_result in test_results:
            failures = test_result.get_asserts()
            if failures:
                message = (
                    f"\n{successful} of {iteration_count} iterations on agent {agent} were successful.\n"
                    f"Need at least {required_successes} to consider {fixture_path} test to be successful.\n"
                )
                raise AssertionError(message) from failures[0]

    @staticmethod
    def _execute_fixture(
        fixture_path: str,
        asserts: ScorecardAssertForwarder,
        fixture_name: str,
        success_ratio_overrides: dict[str, str] | None,
    ) -> None:
        """
        Execute one fixture with its declared or in-memory confidence ratio.

        :param fixture_path: Path to a single test fixture HOCON file.
        :param asserts: The assertion forwarder used to collect fixture results.
        :param fixture_name: The fixture base name.
        :param success_ratio_overrides: Ratios keyed by fixture basename for this execution only.
        """
        ratio_override = (success_ratio_overrides or {}).get(fixture_name)
        if ratio_override is not None:
            FixtureRunner._run_with_ratio_override(fixture_path, asserts, fixture_name, ratio_override)
            return
        driver = FixtureRunner._create_driver(asserts, fixture_name)
        driver.one_test(fixture_path)

    @staticmethod
    def scorecard_message(cause: BaseException, scorecard: list[tuple[str, int, int]]) -> str:
        """
        Turn a fixture's criteria into a report naming EVERY failure, not just the first.

        neuro-san checks all of them and then re-raises only asserts[0], so a consultant fixing a fixture used to
        see one failure of several and learn about the next a whole round later.

        Only the failures are listed. The count still says how many criteria there were in total ("2 of 6"), so the
        scale is visible without the message carrying -- and persisting -- the full text of everything that already
        works.

        :param cause: The original fixture failure.
        :param scorecard: The recorded acceptance-criterion outcomes.
        :return: The resulting text.
        """
        if not scorecard:
            return str(cause)

        failing: list[tuple[str, int, int]] = []
        for name, met, total in scorecard:
            if met < total:
                failing.append((name, met, total))
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
        """
        Build a consistently shaped fixture result.

        :param fixture_path: The fixture file path.
        :param asserts: The assertion forwarder used to collect fixture results.
        :param passed: Whether the fixture passed.
        :param message: The message sent to the Consultant or stored in a verdict.
        :param infrastructure_error: The infrastructure error value.
        :return: The resulting mapping.
        """
        fixture_name = os.path.basename(fixture_path)
        safe_message = FixtureRunner.redact_sensitive_text(message) if message is not None else None
        met, total = (0, 0) if infrastructure_error else asserts.criteria_counts()
        return {
            "fixture": fixture_name,
            "path": fixture_path,
            "passed": passed,
            "message": safe_message,
            "infrastructure_error": infrastructure_error,
            "criteria_passed": met,
            "criteria_total": total,
        }

    @staticmethod
    def _api_key_error_capture() -> tuple[QueueHandler, queue.SimpleQueue[logging.LogRecord]]:
        """
        Return a standard logging handler filtered to API-key errors on this thread.

        :return: The capture handler and its owned record queue.
        """
        capture_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
        capture = QueueHandler(capture_queue)
        capture.setLevel(logging.ERROR)
        fixture_thread_id = threading.get_ident()
        capture.addFilter(partial(FixtureRunner._is_api_key_error_record, fixture_thread_id=fixture_thread_id))
        return capture, capture_queue

    @staticmethod
    def _is_api_key_error_record(record: logging.LogRecord, fixture_thread_id: int) -> bool:
        """
        Return whether a log record is an API-key error from the active fixture thread.

        :param record: The log record to inspect.
        :param fixture_thread_id: The fixture thread id value.
        :return: Whether the requested condition is met.
        """
        # Logging filters execute synchronously on the emitting thread, so the current thread id
        # provides the ownership check without reading LogRecord's public data attributes.
        return threading.get_ident() == fixture_thread_id and FixtureRunner.API_KEY_ERROR_MARKER in record.getMessage()

    @staticmethod
    def _captured_api_key_summary(capture_queue: queue.SimpleQueue[logging.LogRecord]) -> str | None:
        """
        Drain captured provider API-key errors and return one summary when present.

        :param capture_queue: The owned queue containing captured records.
        :return: The resulting value, or `None` when unavailable.
        """
        api_key_error_found = False
        while True:
            try:
                capture_queue.get_nowait()
            except queue.Empty:
                if api_key_error_found:
                    return "Provider API-key validation failed. Verify the configured credentials."
                return None
            api_key_error_found = True

    @staticmethod
    def run_fixture(
        fixture_path: str,
        run_id: str,
        success_ratio_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Run fixture.

        :param fixture_path: Path to a single test fixture HOCON file.
        :param run_id: The unique Consultant run identifier.
        :param success_ratio_overrides: Ratios keyed by fixture basename for this execution only.
        :return: Result with fixture/path/passed/message/infrastructure_error fields.
        """
        # one_test() raises a single AssertionError (summarizing every interaction/iteration
        # mismatch) only if the fixture's success_ratio wasn't met, so a plain try/except
        # is all the aggregation this needs.
        fixture_name = os.path.basename(fixture_path)
        asserts = ScorecardAssertForwarder(TestCase())

        logger.info("run_fixture start: %s", fixture_name)
        started = time.time()
        capture, capture_queue = FixtureRunner._api_key_error_capture()
        logging.getLogger().addHandler(capture)
        try:
            FixtureRunner._execute_fixture(fixture_path, asserts, fixture_name, success_ratio_overrides)
            logger.info("run_fixture pass (%.1fs): %s", time.time() - started, fixture_name)
            return FixtureRunner._fixture_verdict(fixture_path, asserts, True, None)
        except AssertionError as exc:
            cause = exc.__cause__ or exc
            api_key_summary = FixtureRunner._captured_api_key_summary(capture_queue)
            if api_key_summary:
                logger.warning(
                    "run_fixture infrastructure_error (%.1fs, API key error): %s", time.time() - started, fixture_name
                )
                return FixtureRunner._fixture_verdict(
                    fixture_path,
                    asserts,
                    False,
                    api_key_summary,
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
                FixtureRunner.redact_sensitive_text(str(cause)),
            )
            return FixtureRunner._fixture_verdict(fixture_path, asserts, False, message)
        except TimeoutReachedException as exc:
            # exc carries no message of its own (leaf_common never sets one) -- report the interaction's
            # own timeout budget so a human knows to raise timeout_in_seconds, not chase a phantom bug.
            limit = exc.timeout.get_limit_in_seconds()
            message = (
                f"TIMEOUT_ISSUE: {fixture_name}: interaction {exc.timeout.get_name() or fixture_name!r} exceeded "
                f"its {limit:.0f}s timeout -- "
                f"increase timeout_in_seconds in this fixture."
            )
            logger.warning(
                "run_fixture infrastructure_error (%.1fs, timeout): %s", time.time() - started, fixture_name
            )
            return FixtureRunner._fixture_verdict(fixture_path, asserts, False, message, infrastructure_error=True)
        except (AttributeError, ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            message = f"{type(exc).__name__}: {exc}"
            api_key_summary = FixtureRunner._captured_api_key_summary(capture_queue)
            if api_key_summary:
                message = f"{api_key_summary} (Exception type: {type(exc).__name__}.)"
            logger.warning(
                "run_fixture infrastructure_error (%.1fs): %s -- %s",
                time.time() - started,
                fixture_name,
                type(exc).__name__,
            )
            return FixtureRunner._fixture_verdict(fixture_path, asserts, False, message, infrastructure_error=True)
        finally:
            logging.getLogger().removeHandler(capture)
            ThinkingTraceCollector.write(fixture_name, started, run_id)

    @staticmethod
    def run_all_tests(
        fixtures_dir: str,
        run_id: str,
        only_fixtures: list[str] | None = None,
        success_ratio_overrides: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run a fixture suite without retaining changes to the caller's environment.

        :param fixtures_dir: Network path under tests/fixtures/, such as `generated/coffee_shop`.
        :param run_id: The unique Consultant run identifier.
        :param only_fixtures: The optional fixture basenames to run.
        :param success_ratio_overrides: Ratios keyed by fixture basename for this execution only.
        :return: One result mapping per discovered fixture.
        :raises ValueError: If a requested fixture does not exist in the selected fixture directory.
        """
        return FixtureRunner._run_all_tests(fixtures_dir, run_id, only_fixtures, success_ratio_overrides)

    @staticmethod
    def _run_all_tests(
        fixtures_dir: str,
        run_id: str,
        only_fixtures: list[str] | None = None,
        success_ratio_overrides: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run all tests.

        :param fixtures_dir: Network path under tests/fixtures/, e.g. "generated/coffee_shop"
        :param run_id: The unique Consultant run identifier.
        :param only_fixtures: If given, run only these exact basenames (for example, `["foo.hocon"]`).
        :param success_ratio_overrides: Ratios keyed by fixture basename for this execution only.
        :return: One result dict (see run_fixture) per fixture found, in fixture_paths order
        :raises ValueError: If a requested fixture does not exist in the selected fixture directory.
        """
        paths = FixtureRunner.fixture_paths(fixtures_dir)
        paths = FixtureRunner._select_fixture_paths(paths, fixtures_dir, only_fixtures)
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
        # is already safe to call this way: consolidated thinking is keyed by run and fixture name,
        # and each log capture filters to its own thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(paths), MAX_PARALLEL_FIXTURES)) as executor:
            run_fixture = partial(
                FixtureRunner.run_fixture,
                run_id=run_id,
                success_ratio_overrides=success_ratio_overrides,
            )
            results = list(executor.map(run_fixture, paths))
        passed = 0
        for result in results:
            if result.get("passed"):
                passed += 1
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
        """
        Record each fixture's verdict for an nsflow-launched run, so the UI can show pass/fail and the reason per
        test instead of leaving them to be scraped out of the log.

        Merged into the existing map rather than replacing it: the runner frequently re-tests only the fixtures
        that were failing, and a subset re-check says nothing about the ones it didn't run -- they keep their last
        known verdict, exactly as ProgressTracker carries them forward for the chart. A no-op outside an nsflow
        job, like the tracker's own write.

        :param results: run_fixture result dicts for the fixtures this round actually ran
        """
        path = ConsultantJobFiles.path("results.json")
        if path is None:
            return
        try:
            with open(path, encoding="utf-8") as results_file:
                loaded_results = json.load(results_file)
        except FileNotFoundError:
            merged = {}
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Could not read existing fixture results from %s: %s", path, error)
            merged = {}
        else:
            if isinstance(loaded_results, Mapping):
                merged = dict(loaded_results)
            else:
                logger.warning(
                    "Ignoring malformed fixture results in %s: expected an object, received %s",
                    path,
                    type(loaded_results).__name__,
                )
                merged = {}
        for result in results:
            fixture_name = result.get("fixture", "")
            merged.update(
                {
                    fixture_name: {
                        "passed": bool(result.get("passed")),
                        "message": FixtureRunner.redact_sensitive_text(str(result.get("message")))
                        if result.get("message") is not None
                        else None,
                        "infrastructure_error": bool(result.get("infrastructure_error")),
                    }
                }
            )
        try:
            with open(path, "w", encoding="utf-8") as results_file:
                json.dump(merged, results_file, indent=2)
        except OSError as error:
            logger.warning("Could not write fixture results to %s: %s", path, error)
