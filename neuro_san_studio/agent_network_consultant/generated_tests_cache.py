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

"""One-shot generated-test result cache for Agent Network Consultant runs."""

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
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector

logger = logging.getLogger(__name__)


class GeneratedTestsCache:
    """Save and consume a matching generated-test baseline for one Consultant run."""

    CACHE_DIRECTORY_NAME = "agent_network_consultant_cache"

    def __init__(
        self,
        run_id: str,
        fixture_runner: FixtureRunner | None = None,
        job_files: ConsultantJobFiles | None = None,
        trace_collector: ThinkingTraceCollector | None = None,
    ) -> None:
        """
        Initialize one generated-test cache gateway.

        :param run_id: The unique Agent Network Consultant run identifier.
        :param fixture_runner: The fixture runner used to discover fingerprint inputs.
        :param job_files: The active nsflow job-file gateway.
        :param trace_collector: The thinking-trace collector owned by this run.
        """
        self._fixture_runner = fixture_runner or FixtureRunner(run_id)
        self._job_files = job_files or ConsultantJobFiles()
        self._trace_collector = trace_collector or ThinkingTraceCollector(run_id)

    def paths(self, network_name: str) -> tuple[str, str] | None:
        """
        Return this job's isolated result and thinking-trace cache paths.

        :param network_name: The target network name.
        :return: The cache paths, or `None` outside an nsflow job.
        """
        cache_directory = self._cache_directory()
        job_id = self._job_files.identifier()
        if cache_directory is None or job_id is None:
            return None
        os.makedirs(cache_directory, exist_ok=True)
        path_basis = os.path.join(cache_directory, f"{self._network_key(network_name)}.{job_id}")
        return f"{path_basis}.json", f"{path_basis}_thinking"

    def fingerprint(self, network_name: str, hocon_path: str) -> str:
        """
        Hash the network HOCON and every fixture that can affect a test result.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :return: The complete input fingerprint.
        :raises OSError: If the network definition or one of its fixtures cannot be read.
        """
        hasher = hashlib.sha256()
        with open(hocon_path, encoding="utf-8") as hocon_file:
            hasher.update(hocon_file.read().encode("utf-8"))
        for path in self._fixture_runner.fixture_paths(network_name):
            hasher.update(path.encode("utf-8"))
            with open(path, encoding="utf-8") as fixture_file:
                hasher.update(fixture_file.read().encode("utf-8"))
        return hasher.hexdigest()

    def save(self, network_name: str, hocon_path: str, results: list[dict[str, Any]]) -> None:
        """
        Cache one generated-test run and its filtered thinking traces.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :param results: The fixture result records.
        :raises OSError: If an input cannot be read or the cache cannot be written.
        """
        cache_paths = self.paths(network_name)
        if cache_paths is None:
            return
        results_path, thinking_dir = cache_paths
        temporary_path = f"{results_path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as results_file:
            json.dump(
                {
                    "fingerprint": self.fingerprint(network_name, hocon_path),
                    "results": self._redact_result_messages(results),
                },
                results_file,
            )
        os.replace(temporary_path, results_path)
        self._remove_thinking_directory(thinking_dir)
        run_directory = self._trace_collector.run_directory()
        if os.path.isdir(run_directory):
            shutil.copytree(run_directory, thinking_dir)

    def load(self, network_name: str, hocon_path: str) -> list[dict[str, Any]] | None:
        """
        Return cached results and restore traces when every input still matches.

        A stale, mismatched, or already-used baseline is consumed and never reused.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :return: The cached fixture results, or `None` when no valid candidate exists.
        """
        for results_path in self._candidate_paths(network_name):
            results = self._load_candidate(network_name, hocon_path, results_path)
            if results is not None:
                return results
        return None

    def _cache_directory(self) -> str | None:
        """
        Resolve project-local cache storage from the active nsflow job directory.

        :return: The cache directory, or `None` outside an nsflow job.
        """
        job_directory = self._job_files.directory()
        if job_directory is None or self._job_files.identifier() is None:
            return None
        return os.path.join(os.path.dirname(os.path.abspath(job_directory)), self.CACHE_DIRECTORY_NAME)

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

    def _remove_thinking_directory(self, thinking_dir: str) -> None:
        """
        Remove cached thinking traces while reporting cleanup failures.

        :param thinking_dir: The cached thinking-trace directory to remove.
        """
        if not os.path.exists(thinking_dir):
            return
        try:
            shutil.rmtree(thinking_dir)
        except OSError as error:
            # A failed cleanup can leave private traces on disk, so it remains actionable at WARNING.
            logger.warning("Could not remove cached thinking traces from %s: %s", thinking_dir, error)

    def _candidate_paths(self, network_name: str) -> list[str]:
        """
        Return isolated cache entries produced by earlier jobs for this network.

        :param network_name: The target network name.
        :return: Candidate result paths in deterministic order.
        """
        cache_directory = self._cache_directory()
        if cache_directory is None or not os.path.isdir(cache_directory):
            return []
        pattern = os.path.join(cache_directory, f"{self._network_key(network_name)}.*.json")
        return sorted(glob.glob(pattern), reverse=True)

    @staticmethod
    def _thinking_path(results_path: str) -> str:
        """
        Return the thinking-trace directory paired with a result cache file.

        :param results_path: The generated-test result cache path.
        :return: The paired thinking-trace directory.
        """
        return f"{results_path.removesuffix('.json')}_thinking"

    def _load_candidate(
        self,
        network_name: str,
        hocon_path: str,
        results_path: str,
    ) -> list[dict[str, Any]] | None:
        """
        Consume one cache entry and return it only when its input fingerprint still matches.

        :param network_name: The target network name.
        :param hocon_path: The target HOCON file path.
        :param results_path: The candidate generated-test result cache path.
        :return: The cached fixture results, or `None` when the candidate is invalid or stale.
        """
        thinking_dir = self._thinking_path(results_path)
        cached = self._read_candidate(results_path)
        try:
            os.remove(results_path)
        except OSError as error:
            # A cache that cannot be consumed violates the one-shot contract and needs operator attention.
            logger.warning("Could not consume generated-tests cache %s: %s", results_path, error)
            self._remove_thinking_directory(thinking_dir)
            return None
        cached = self._validated_candidate(cached, results_path)
        matches = cached is not None and cached.get("fingerprint") == self.fingerprint(network_name, hocon_path)
        if matches and os.path.isdir(thinking_dir):
            shutil.copytree(thinking_dir, self._trace_collector.run_directory(), dirs_exist_ok=True)
        self._remove_thinking_directory(thinking_dir)
        if not matches or cached is None:
            return None
        return self._validated_results(cached.get("results"), results_path)

    @staticmethod
    def _read_candidate(results_path: str) -> Any | None:
        """
        Read one cache entry, treating unreadable content as a reported cache miss.

        :param results_path: The candidate generated-test result cache path.
        :return: The decoded cache value, or `None` when it cannot be read.
        """
        try:
            with open(results_path, encoding="utf-8") as results_file:
                return json.load(results_file)
        except (json.JSONDecodeError, OSError) as error:
            logger.info("Ignoring unreadable generated-tests cache %s: %s", results_path, error)
            return None

    @staticmethod
    def _validated_candidate(cached: Any | None, results_path: str) -> Mapping[str, Any] | None:
        """
        Validate the top-level cache shape and required fields.

        :param cached: The decoded cache value.
        :param results_path: The candidate path used for diagnostics.
        :return: The validated cache mapping, or `None` when malformed.
        """
        if cached is None:
            return None
        if not isinstance(cached, Mapping):
            logger.info(
                "Ignoring malformed generated-tests cache %s: expected an object, received %s",
                results_path,
                type(cached).__name__,
            )
            return None
        if cached.get("fingerprint") is None or cached.get("results") is None:
            logger.info("Ignoring malformed generated-tests cache %s: required fields are missing", results_path)
            return None
        return cached

    @staticmethod
    def _redact_result_messages(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Return detached fixture results with diagnostic messages sanitized.

        :param results: The fixture result records to protect.
        :return: Copies of the fixture results with sensitive message text redacted.
        """
        redacted_results: list[dict[str, Any]] = []
        for result in results:
            redacted_result = dict(result)
            message = redacted_result.get("message")
            if message is not None:
                redacted_result.update({"message": SensitiveDataRedactor.redact_text(str(message))})
            redacted_results.append(redacted_result)
        return redacted_results

    @staticmethod
    def _validated_results(cached_results: Any, results_path: str) -> list[dict[str, Any]] | None:
        """
        Validate and redact fixture results loaded from a cache entry.

        :param cached_results: The decoded cached result value.
        :param results_path: The candidate path used for diagnostics.
        :return: Redacted fixture results, or `None` when malformed.
        """
        if not isinstance(cached_results, MutableSequence):
            logger.info("Ignoring malformed generated-tests cache %s: results must be a list", results_path)
            return None
        results: list[dict[str, Any]] = []
        for cached_result in cached_results:
            if not isinstance(cached_result, Mapping):
                logger.info("Ignoring malformed generated-tests cache %s: result must be an object", results_path)
                return None
            results.append(dict(cached_result))
        return GeneratedTestsCache._redact_result_messages(results)
