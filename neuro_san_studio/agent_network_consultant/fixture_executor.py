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

"""Execute one Agent Network Consultant fixture through Neuro SAN's test driver."""

import logging
import os
import queue
import threading
import time
from functools import partial
from logging.handlers import QueueHandler
from typing import Any

from leaf_common.time.timeout_reached_exception import TimeoutReachedException
from pyhocon.exceptions import ConfigException
from pyparsing import ParseBaseException

from neuro_san_studio.agent_network_consultant.fixture_driver import FixtureDriver
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector

logger = logging.getLogger(__name__)


class FixtureExecutor:
    """Execute and report one fixture while isolating the Neuro SAN test-driver boundary."""

    # Neuro SAN currently reports provider credential failures through this RunContext log marker. Replace this
    # coupling with a structured driver status when Neuro SAN exposes one.
    API_KEY_ERROR_MARKER = "API KEY error detected"

    def __init__(
        self,
        fixture_path: str,
        trace_collector: ThinkingTraceCollector,
        success_ratio_override: str | None = None,
    ) -> None:
        """
        Initialize one fixture execution.

        :param fixture_path: Path to the fixture HOCON file.
        :param trace_collector: The filtered thinking-trace collector for this run.
        :param success_ratio_override: The optional ratio used for this execution without changing the fixture.
        """
        self._fixture_path = fixture_path
        self._fixture_name = os.path.basename(fixture_path)
        self._trace_collector = trace_collector
        self._driver = FixtureDriver(fixture_path, success_ratio_override)

    def execute(self) -> dict[str, Any]:
        """
        Execute the fixture and return its redacted verdict.

        :return: Result with fixture, path, pass status, message, and criterion counts.
        """
        logger.info("run_fixture start: %s", self._fixture_name)
        started = time.time()
        capture, capture_queue = self._api_key_error_capture()
        # Provider errors use several logger namespaces. The synchronous filter confines root capture to this thread.
        logging.getLogger().addHandler(capture)
        try:
            self._driver.execute()
            logger.info("run_fixture pass (%.1fs): %s", time.time() - started, self._fixture_name)
            return self._fixture_verdict(True, None)
        except AssertionError as error:
            return self._assertion_verdict(started, capture_queue, error)
        except TimeoutReachedException as error:
            return self._timeout_verdict(started, error)
        except (ConfigException, ImportError, OSError, ParseBaseException, ValueError) as error:
            return self._infrastructure_verdict(started, capture_queue, error)
        finally:
            logging.getLogger().removeHandler(capture)
            try:
                self._trace_collector.write(self._fixture_name, started)
            except OSError as error:
                logger.warning(
                    "Could not collect thinking trace for %s: %s: %s",
                    self._fixture_name,
                    type(error).__name__,
                    SensitiveDataRedactor.redact_text(str(error)),
                )

    def scorecard_message(self, cause: BaseException, scorecard: list[tuple[str, int, int]]) -> str:
        """
        Turn a fixture's criteria into a report naming every failure, not just the first.

        :param cause: The original fixture failure.
        :param scorecard: The recorded acceptance-criterion outcomes.
        :return: The resulting failure report.
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
            # A partly met criterion is flaky rather than wholly broken, which is useful repair context.
            suffix = f"  (met on {met} of {total} attempts)" if met else ""
            lines.append(f"  - {name}{suffix}")
        lines.append("")
        lines.append(f"First failure in detail:\n{cause}")
        return "\n".join(lines)

    def _fixture_verdict(
        self,
        passed: bool,
        message: str | None,
        infrastructure_error: bool = False,
    ) -> dict[str, Any]:
        """
        Build a consistently shaped fixture result.

        :param passed: Whether the fixture passed.
        :param message: The failure message, when present.
        :param infrastructure_error: Whether infrastructure caused the failure.
        :return: The fixture verdict mapping.
        """
        safe_message = SensitiveDataRedactor.redact_text(message) if message is not None else None
        asserts = self._driver.assertions()
        met, total = (0, 0) if infrastructure_error else asserts.criteria_counts()
        return {
            "fixture": self._fixture_name,
            "path": self._fixture_path,
            "passed": passed,
            "message": safe_message,
            "infrastructure_error": infrastructure_error,
            "criteria_passed": met,
            "criteria_total": total,
        }

    def _api_key_error_capture(self) -> tuple[QueueHandler, queue.SimpleQueue[logging.LogRecord]]:
        """
        Return a standard logging handler filtered to API-key errors on this thread.

        :return: The capture handler and its owned record queue.
        """
        capture_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
        capture = QueueHandler(capture_queue)
        capture.setLevel(logging.ERROR)
        fixture_thread_id = threading.get_ident()
        capture.addFilter(partial(self._is_api_key_error_record, fixture_thread_id=fixture_thread_id))
        return capture, capture_queue

    def _is_api_key_error_record(self, record: logging.LogRecord, fixture_thread_id: int) -> bool:
        """
        Return whether a log record is an API-key error from the active fixture thread.

        :param record: The log record to inspect.
        :param fixture_thread_id: The fixture thread identifier.
        :return: Whether the record belongs to this fixture and reports an API-key error.
        """
        return threading.get_ident() == fixture_thread_id and self.API_KEY_ERROR_MARKER in record.getMessage()

    @staticmethod
    def _captured_api_key_summary(capture_queue: queue.SimpleQueue[logging.LogRecord]) -> str | None:
        """
        Drain captured provider API-key errors and return one summary when present.

        :param capture_queue: The owned queue containing captured records.
        :return: The credential failure summary, or `None` when unavailable.
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

    def _assertion_verdict(
        self,
        started: float,
        capture_queue: queue.SimpleQueue[logging.LogRecord],
        error: AssertionError,
    ) -> dict[str, Any]:
        """
        Convert a fixture assertion into a behavior or credential verdict.

        :param started: The fixture start timestamp.
        :param capture_queue: The fixture's captured provider log records.
        :param error: The fixture assertion error.
        :return: The fixture verdict mapping.
        """
        api_key_summary = self._captured_api_key_summary(capture_queue)
        if api_key_summary:
            logger.warning(
                "run_fixture infrastructure_error (%.1fs, API key error): %s",
                time.time() - started,
                self._fixture_name,
            )
            return self._fixture_verdict(False, api_key_summary, infrastructure_error=True)
        cause = error.__cause__ or error
        asserts = self._driver.assertions()
        message = self.scorecard_message(cause, asserts.scorecard())
        met, total = asserts.criteria_counts()
        logger.info(
            "run_fixture fail (%.1fs): %s (%d/%d criteria) -- %s",
            time.time() - started,
            self._fixture_name,
            met,
            total,
            SensitiveDataRedactor.redact_text(str(cause)),
        )
        return self._fixture_verdict(False, message)

    def _timeout_verdict(self, started: float, error: TimeoutReachedException) -> dict[str, Any]:
        """
        Convert a Neuro SAN interaction timeout into an actionable verdict.

        :param started: The fixture start timestamp.
        :param error: The fixture timeout exception.
        :return: The infrastructure-error verdict.
        """
        limit = error.timeout.get_limit_in_seconds()
        interaction_name = error.timeout.get_name() or self._fixture_name
        message = (
            f"TIMEOUT_ISSUE: {self._fixture_name}: interaction {interaction_name!r} exceeded its {limit:.0f}s "
            f"timeout -- increase timeout_in_seconds in this fixture."
        )
        logger.warning(
            "run_fixture infrastructure_error (%.1fs, timeout): %s; increase timeout_in_seconds in the fixture",
            time.time() - started,
            self._fixture_name,
        )
        return self._fixture_verdict(False, message, infrastructure_error=True)

    def _infrastructure_verdict(
        self,
        started: float,
        capture_queue: queue.SimpleQueue[logging.LogRecord],
        error: ConfigException | ImportError | OSError | ParseBaseException | ValueError,
    ) -> dict[str, Any]:
        """
        Convert an expected fixture-runtime failure into a redacted verdict.

        :param started: The fixture start timestamp.
        :param capture_queue: The fixture's captured provider log records.
        :param error: The expected runtime error.
        :return: The infrastructure-error verdict.
        """
        api_key_summary = self._captured_api_key_summary(capture_queue)
        if api_key_summary:
            message = f"{api_key_summary} (Exception type: {type(error).__name__}.)"
            logger.warning(
                "run_fixture infrastructure_error (%.1fs): %s -- %s: provider API-key validation failed; "
                "exception details redacted",
                time.time() - started,
                self._fixture_name,
                type(error).__name__,
            )
        else:
            redacted_error = SensitiveDataRedactor.redact_text(str(error))
            message = f"{type(error).__name__}: {redacted_error}"
            logger.warning(
                "run_fixture infrastructure_error (%.1fs): %s -- %s: %s",
                time.time() - started,
                self._fixture_name,
                type(error).__name__,
                redacted_error,
            )
        return self._fixture_verdict(False, message, infrastructure_error=True)
