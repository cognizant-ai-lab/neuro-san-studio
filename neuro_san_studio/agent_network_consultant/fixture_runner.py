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
"""Run agent-network HOCON fixtures with Neuro SAN's data-driven test drivers."""

import concurrent.futures
import glob
import json
import logging
import os
import time
from collections.abc import Mapping
from typing import Any

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.fixture_executor import FixtureExecutor
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector

logger = logging.getLogger(__name__)


class FixtureRunner:
    """Discover, run, and report fixtures for one isolated Agent Network Consultant run."""

    DEFAULT_FIXTURE_ROOT = os.path.join("tests", "fixtures")
    # Each fixture's Neuro SAN driver may run its ratio attempts concurrently. Seven fixtures per Consultant process
    # keep that process's session fan-out bounded while still allowing independent fixtures to overlap.
    MAX_PARALLEL_FIXTURES = 7

    def __init__(
        self,
        run_id: str,
        success_ratio_overrides: Mapping[str, str] | None = None,
        fixture_root: str | None = None,
        trace_collector: ThinkingTraceCollector | None = None,
    ) -> None:
        """
        Initialize fixture execution for one Consultant run.

        :param run_id: The unique Agent Network Consultant run identifier.
        :param success_ratio_overrides: Ratios keyed by fixture basename for this execution only.
        :param fixture_root: The directory containing network fixture subdirectories.
        :param trace_collector: The filtered thinking-trace collector for this run.
        """
        self._success_ratio_overrides = dict(success_ratio_overrides or {})
        self._fixture_root = fixture_root or self.DEFAULT_FIXTURE_ROOT
        self._job_files = ConsultantJobFiles()
        self._trace_collector = trace_collector or ThinkingTraceCollector(run_id)

    def fixture_paths(self, network_name: str) -> list[str]:
        """
        Return the fixture paths for one runtime network name.

        :param network_name: The network path under the configured fixture root.
        :return: Sorted fixture HOCON paths for the network.
        """
        search_dir = os.path.join(self._fixture_root, network_name)
        return sorted(glob.glob(os.path.join(search_dir, "*.hocon")))

    def run_fixture(self, fixture_path: str) -> dict[str, Any]:
        """
        Run one fixture and return its redacted verdict.

        :param fixture_path: Path to a single test fixture HOCON file.
        :return: Result with fixture, path, pass status, message, and criterion counts.
        """
        fixture_name = os.path.basename(fixture_path)
        ratio_override = self._success_ratio_overrides.get(fixture_name)
        executor = FixtureExecutor(fixture_path, self._trace_collector, ratio_override)
        return executor.execute()

    def run_all_tests(
        self,
        network_name: str,
        only_fixtures: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run a fixture suite without retaining changes to the caller's environment.

        :param network_name: Network path under the configured fixture root, such as `generated/coffee_shop`.
        :param only_fixtures: The optional fixture basenames to run.
        :return: One result mapping per discovered fixture.
        :raises ValueError: If a requested fixture does not exist in the selected fixture directory.
        """
        paths = self._select_fixture_paths(self.fixture_paths(network_name), network_name, only_fixtures)
        if not paths:
            return self._missing_fixture_verdict(network_name, only_fixtures)
        logger.info(
            "run_all_tests start: %d fixture(s) under %s%s",
            len(paths),
            network_name,
            f" (subset of {only_fixtures})" if only_fixtures is not None else "",
        )
        started = time.time()
        # The runner's shared fields are immutable during execution; each worker owns its driver and assertions.
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(paths), self.MAX_PARALLEL_FIXTURES)
        ) as executor:
            results = list(executor.map(self.run_fixture, paths))
        passed = 0
        for result in results:
            if result.get("passed"):
                passed += 1
        logger.info(
            "run_all_tests done (%.1fs): %d/%d passing under %s",
            time.time() - started,
            passed,
            len(results),
            network_name,
        )
        self.write_fixture_results(results)
        return results

    def write_fixture_results(self, results: list[dict[str, Any]]) -> None:
        """
        Merge fixture verdicts into the active nsflow job results.

        :param results: Result mappings for the fixtures run in the current round.
        """
        path = self._job_files.path("results.json")
        if path is None:
            return
        merged = self._existing_results(path)
        for result in results:
            fixture_name = str(result.get("fixture", ""))
            message = result.get("message")
            merged.update(
                {
                    fixture_name: {
                        "passed": bool(result.get("passed")),
                        "message": SensitiveDataRedactor.redact_text(str(message)) if message is not None else None,
                        "infrastructure_error": bool(result.get("infrastructure_error")),
                    }
                }
            )
        try:
            self._job_files.write("results.json", json.dumps(merged, indent=2))
        except OSError as error:
            logger.warning("Could not write fixture results to %s: %s", path, error)

    @staticmethod
    def _select_fixture_paths(
        paths: list[str],
        network_name: str,
        only_fixtures: list[str] | None,
    ) -> list[str]:
        """
        Return requested fixture paths after rejecting unknown names.

        :param paths: Every fixture path discovered for the selected network.
        :param network_name: Network path used in validation errors.
        :param only_fixtures: The optional exact fixture basenames to select.
        :return: Every discovered path, or the validated requested subset.
        :raises ValueError: If a requested fixture does not exist.
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
            raise ValueError(f"Unknown fixture selection under '{network_name}': {missing_names}.")
        selected_paths: list[str] = []
        for path in paths:
            if os.path.basename(path) in wanted:
                selected_paths.append(path)
        return selected_paths

    @staticmethod
    def _existing_results(path: os.PathLike[str]) -> dict[str, Any]:
        """
        Read prior nsflow fixture verdicts before merging a subset re-test.

        :param path: The existing results sidecar path.
        :return: The prior fixture result mapping, or an empty mapping after a reported failure.
        """
        try:
            with open(path, encoding="utf-8") as results_file:
                loaded_results = json.load(results_file)
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Could not read existing fixture results from %s: %s", path, error)
            return {}
        if isinstance(loaded_results, Mapping):
            return dict(loaded_results)
        logger.info(
            "Ignoring malformed fixture results in %s: expected an object, received %s",
            path,
            type(loaded_results).__name__,
        )
        return {}

    def _missing_fixture_verdict(
        self,
        network_name: str,
        only_fixtures: list[str] | None,
    ) -> list[dict[str, Any]]:
        """
        Report an empty fixture directory as an infrastructure failure.

        :param network_name: The network path under the configured fixture root.
        :param only_fixtures: The optional fixture selection used for the run.
        :return: A single fixture-discovery failure verdict.
        """
        search_dir = os.path.join(self._fixture_root, network_name)
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
