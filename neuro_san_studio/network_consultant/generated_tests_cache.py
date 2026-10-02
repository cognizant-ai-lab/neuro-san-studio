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

"""One-shot generated-test result cache for Network Consultant runs."""

import hashlib
import json
import os
import shutil

from neuro_san_studio.network_consultant.fixture_runner import IMPROVEMENT_THINKING_DIR
from neuro_san_studio.network_consultant.fixture_runner import FixtureRunner


class GeneratedTestsCache:
    """Save and consume a matching generated-test baseline exactly once."""

    # One-shot cache: a UI-triggered "Generate Tests" run (max_iterations=0) tests the fresh
    # fixtures once anyway, so a UI-triggered "Self-Improve" launched right after can reuse that
    # result as its own iteration 1 instead of paying to re-run every fixture a second time. Gated
    # on NSFLOW_JOB_ID/NSFLOW_JOB_DIR throughout -- plain CLI usage never writes or reads this cache,
    # so it behaves exactly as before (max_iterations=0 does no test run at all).
    GENTESTS_CACHE_DIR = "/tmp/network_consultant_gentests_cache"

    @staticmethod
    def paths(network_name: str) -> tuple[str, str]:
        """(results_json_path, thinking_traces_dir) for this network's cached baseline, if any."""
        os.makedirs(GeneratedTestsCache.GENTESTS_CACHE_DIR, exist_ok=True)
        safe_name = network_name.replace("/", "_")
        return (
            os.path.join(GeneratedTestsCache.GENTESTS_CACHE_DIR, f"{safe_name}.json"),
            os.path.join(GeneratedTestsCache.GENTESTS_CACHE_DIR, f"{safe_name}_thinking"),
        )

    @staticmethod
    def fingerprint(network_name: str, hocon_path: str) -> str:
        """Hash of everything a test run's outcome for this network actually depends on: the
        network's own HOCON plus the current content of every one of its fixture files. A hocon-only
        hash would miss a fixture being added, edited, or deleted (e.g. by a fresh Generate Tests
        call, or a human editing tests/fixtures/ by hand) between the run that wrote this cache and
        the one that would consume it -- the fixtures wouldn't match what was actually tested, but
        the hocon hash alone would still say "unchanged". Hashing both means the cache is only ever
        reused when literally nothing that could change the result has moved since.
        """
        hasher = hashlib.sha256()
        with open(hocon_path, encoding="utf-8") as hocon_file:
            hasher.update(hocon_file.read().encode("utf-8"))
        for path in FixtureRunner.fixture_paths(network_name):
            hasher.update(path.encode("utf-8"))
            with open(path, encoding="utf-8") as fixture_file:
                hasher.update(fixture_file.read().encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def save(network_name: str, hocon_path: str, results: list) -> None:
        """Cache a generate-tests-only run's results, fingerprinted to the network's current content,
        for one-shot reuse by the next Self-Improve run against this exact network. Also copies each
        fixture's consolidated thinking trace (see IMPROVEMENT_THINKING_DIR) -- without it, a
        self-improve run that skips its own re-test would leave the diagnosing sub-agents with only
        the bare assertion message instead of the full per-agent reasoning a fresh run gives them
        via read_thinking_trace."""
        results_path, thinking_dir = GeneratedTestsCache.paths(network_name)
        tmp_path = f"{results_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as results_file:
            json.dump(
                {"fingerprint": GeneratedTestsCache.fingerprint(network_name, hocon_path), "results": results},
                results_file,
            )
        os.replace(tmp_path, results_path)
        shutil.rmtree(thinking_dir, ignore_errors=True)
        if os.path.isdir(IMPROVEMENT_THINKING_DIR):
            shutil.copytree(IMPROVEMENT_THINKING_DIR, thinking_dir)

    @staticmethod
    def load(network_name: str, hocon_path: str) -> list:
        """Return cached results (restoring their thinking traces into IMPROVEMENT_THINKING_DIR) if
        the network's hocon and every one of its fixtures still match what was cached; None otherwise
        (which means the caller must actually run the tests). Always consumes (deletes) the cache --
        a stale, mismatched, or already-used baseline is never reused, so at most the very next
        Self-Improve run after a Generate Tests run benefits."""
        results_path, thinking_dir = GeneratedTestsCache.paths(network_name)
        if not os.path.exists(results_path):
            return None
        try:
            with open(results_path, encoding="utf-8") as results_file:
                cached = json.load(results_file)
        except (json.JSONDecodeError, OSError):
            cached = None
        os.remove(results_path)
        matches = cached is not None and cached.get("fingerprint") == GeneratedTestsCache.fingerprint(
            network_name, hocon_path
        )
        if matches and os.path.isdir(thinking_dir):
            shutil.copytree(thinking_dir, IMPROVEMENT_THINKING_DIR, dirs_exist_ok=True)
        shutil.rmtree(thinking_dir, ignore_errors=True)
        return cached.get("results") if matches else None
