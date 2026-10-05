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

import glob
import hashlib
import json
import logging
import os
import shutil
from collections.abc import Mapping
from collections.abc import MutableSequence
from typing import Any

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector

logger = logging.getLogger(__name__)


class GeneratedTestsCache:
    """Save and consume a matching generated-test baseline exactly once."""

    CACHE_DIRECTORY_NAME = "network_consultant_cache"

    @staticmethod
    def _cache_directory() -> str | None:
        """
        Resolve project-local cache storage from the active nsflow job directory.

        The cache sits beside the job directory because nsflow removes completed job sidecars before starting the
        next process. The sibling location remains project-scoped while allowing that next process to consume it.

        :return: The cache directory, or `None` outside an nsflow job.
        """
        job_directory = ConsultantJobFiles.directory()
        if job_directory is None or ConsultantJobFiles.identifier() is None:
            return None
        return os.path.join(os.path.dirname(os.path.abspath(job_directory)), GeneratedTestsCache.CACHE_DIRECTORY_NAME)

    @staticmethod
    def _network_key(network_name: str) -> str:
        """
        Return a readable collision-resistant cache key for one network.

        :param network_name: The target network name.
        :return: The filename-safe network key.
        """
        safe_name = network_name.replace("/", "_").replace("\\", "_")
        digest = hashlib.sha256(network_name.encode("utf-8")).hexdigest()[:12]
        return f"{safe_name}.{digest}"

    @staticmethod
    def _remove_thinking_directory(thinking_dir: str) -> None:
        """
        Remove cached thinking traces while reporting cleanup failures.

        :param thinking_dir: The cached thinking-trace directory to remove.
        """
        if not os.path.exists(thinking_dir):
            return
        try:
            shutil.rmtree(thinking_dir)
        except OSError as error:
            logger.warning("Could not remove cached thinking traces from %s: %s", thinking_dir, error)

    @staticmethod
    def paths(network_name: str) -> tuple[str, str] | None:
        """
        Return this job's isolated result and thinking-trace cache paths.

        :param network_name: The target network name.
        :return: The cache paths, or `None` outside an nsflow job.
        """
        cache_directory = GeneratedTestsCache._cache_directory()
        job_id = ConsultantJobFiles.identifier()
        if cache_directory is None or job_id is None:
            return None
        os.makedirs(cache_directory, exist_ok=True)
        path_basis = os.path.join(cache_directory, f"{GeneratedTestsCache._network_key(network_name)}.{job_id}")
        return (
            f"{path_basis}.json",
            f"{path_basis}_thinking",
        )

    @staticmethod
    def _candidate_paths(network_name: str) -> list[str]:
        """
        Return isolated cache entries produced by earlier jobs for this network.

        :param network_name: The target network name.
        :return: Candidate result paths in deterministic order.
        """
        cache_directory = GeneratedTestsCache._cache_directory()
        if cache_directory is None or not os.path.isdir(cache_directory):
            return []
        pattern = os.path.join(cache_directory, f"{GeneratedTestsCache._network_key(network_name)}.*.json")
        return sorted(glob.glob(pattern), reverse=True)

    @staticmethod
    def _thinking_path(results_path: str) -> str:
        """
        Return the thinking-trace directory paired with a result cache file.

        :param results_path: The generated-test result cache path.
        :return: The paired thinking-trace directory.
        """
        return f"{results_path.removesuffix('.json')}_thinking"

    @staticmethod
    def fingerprint(network_name: str, hocon_path: str) -> str:
        """
        Hash of everything a test run's outcome for this network actually depends on: the network's own HOCON plus
        the current content of every one of its fixture files. A hocon-only hash would miss a fixture being added,
        edited, or deleted (e.g. by a fresh Generate Tests call, or a human editing tests/fixtures/ by hand)
        between the run that wrote this cache and the one that would consume it -- the fixtures wouldn't match what
        was actually tested, but the hocon hash alone would still say "unchanged". Hashing both means the cache is
        only ever reused when literally nothing that could change the result has moved since.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :return: The resulting text.
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
    def save(network_name: str, hocon_path: str, results: list[dict[str, Any]], run_id: str) -> None:
        """
        Cache a generate-tests-only run's results, fingerprinted to the network's current content, for one-shot
        reuse by the next Self-Improve run against this exact network. Also copies each fixture's consolidated
        thinking trace from the run-owned directory -- without it, a self-improve run that skips its own re-test
        would leave the diagnosing sub-agents with only the bare assertion message instead of the full per-agent
        reasoning a fresh run gives them via read_thinking_trace.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :param results: The fixture result records.
        :param run_id: The unique Consultant run identifier that owns the traces being cached.
        """
        cache_paths = GeneratedTestsCache.paths(network_name)
        if cache_paths is None:
            return
        results_path, thinking_dir = cache_paths
        tmp_path = f"{results_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as results_file:
            json.dump(
                {"fingerprint": GeneratedTestsCache.fingerprint(network_name, hocon_path), "results": results},
                results_file,
            )
        os.replace(tmp_path, results_path)
        GeneratedTestsCache._remove_thinking_directory(thinking_dir)
        run_directory = ThinkingTraceCollector.run_directory(run_id)
        if os.path.isdir(run_directory):
            shutil.copytree(run_directory, thinking_dir)

    @staticmethod
    def load(network_name: str, hocon_path: str, run_id: str) -> list[dict[str, Any]] | None:
        """
        Return cached results and restore traces into this run's isolated directory when all inputs still match.

        A stale, mismatched, or already-used baseline is consumed and never reused, so at most the next
        Self-Improve run after a Generate Tests run benefits.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :param run_id: The unique Consultant run identifier that will own the restored traces.
        :return: The collected values.
        """
        for results_path in GeneratedTestsCache._candidate_paths(network_name):
            results = GeneratedTestsCache._load_candidate(network_name, hocon_path, results_path, run_id)
            if results is not None:
                return results
        return None

    @staticmethod
    def _load_candidate(
        network_name: str,
        hocon_path: str,
        results_path: str,
        run_id: str,
    ) -> list[dict[str, Any]] | None:
        """
        Consume one cache entry and return it only when its complete input fingerprint still matches.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :param results_path: The candidate generated-test result cache path.
        :param run_id: The unique Consultant run identifier that will own the restored traces.
        :return: The cached fixture results, or `None` when the candidate is invalid or stale.
        """
        thinking_dir = GeneratedTestsCache._thinking_path(results_path)
        try:
            with open(results_path, encoding="utf-8") as results_file:
                cached = json.load(results_file)
        except (json.JSONDecodeError, OSError) as error:
            logger.warning("Could not read generated-tests cache %s: %s", results_path, error)
            cached = None
        try:
            os.remove(results_path)
        except OSError as error:
            logger.warning("Could not consume generated-tests cache %s: %s", results_path, error)
            GeneratedTestsCache._remove_thinking_directory(thinking_dir)
            return None
        if cached is not None and not isinstance(cached, Mapping):
            logger.warning(
                "Ignoring malformed generated-tests cache %s: expected an object, received %s",
                results_path,
                type(cached).__name__,
            )
            cached = None
        if cached is not None and (cached.get("fingerprint") is None or cached.get("results") is None):
            logger.warning("Ignoring malformed generated-tests cache %s: required fields are missing", results_path)
            cached = None
        matches = cached is not None and cached.get("fingerprint") == GeneratedTestsCache.fingerprint(
            network_name, hocon_path
        )
        if matches and os.path.isdir(thinking_dir):
            run_directory = ThinkingTraceCollector.run_directory(run_id)
            shutil.copytree(thinking_dir, run_directory, dirs_exist_ok=True)
        GeneratedTestsCache._remove_thinking_directory(thinking_dir)
        if not matches:
            return None
        cached_results = cached.get("results")
        if not isinstance(cached_results, MutableSequence):
            logger.warning("Ignoring malformed generated-tests cache %s: results must be a list", results_path)
            return None
        results: list[dict[str, Any]] = []
        for cached_result in cached_results:
            if not isinstance(cached_result, Mapping):
                logger.warning("Ignoring malformed generated-tests cache %s: result must be an object", results_path)
                return None
            result = dict(cached_result)
            message = result.get("message")
            if message is not None:
                result["message"] = FixtureRunner.redact_sensitive_text(str(message))
            results.append(result)
        return results
