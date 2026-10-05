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

"""Characterization tests for the refactored Network Consultant run orchestration."""

import json
import logging
import os
import shutil
from contextlib import ExitStack
from functools import partial
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import call
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant import thinking_trace_collector
from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.agent_network_consultant.network_consultant_orchestrator import NetworkConsultantOrchestrator
from neuro_san_studio.agent_network_consultant.progress_tracker import ProgressTracker
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector


class TestNetworkConsultantOrchestrator(TestCase):
    """Verify the extracted orchestration preserves its original control flow."""

    @staticmethod
    def _context(max_iterations: int = 2) -> ConsultantRunContext:
        """
        Build an inert run context for orchestration tests.

        :param max_iterations: The configured repair iteration limit.
        :return: The resulting value.
        """
        options = ConsultantOptions(
            force_generate=False,
            git_versions=False,
            hocon_file="example.hocon",
            max_iterations=max_iterations,
            only_fixtures=None,
            success_ratio="3/3",
            test_guidance="",
            test_level="normal",
            ungrounded="stop",
            use_case=None,
        )
        session = Mock(spec=ConsultantSession)
        session.run_identifier.return_value = "run-one"
        return ConsultantRunContext(
            options,
            session,
            ConsultantTarget("example.hocon", "example", "Preserve behavior", "registries/example.hocon"),
            ConsultantResources(),
            ConsultantScoreState(),
            ConsultantRoundState(),
            ProgressTracker(),
        )

    @staticmethod
    def _load_failing_round(calls: list[str], run_context: ConsultantRunContext) -> None:
        """
        Populate one ordinary failing round and record the load stage.

        :param calls: The calls value.
        :param run_context: The Consultant run context populated by the test helper.
        """
        calls.append("load")
        run_context.round_state().record_results([{"fixture": "failure.hocon", "passed": False}])

    @staticmethod
    def _load_infrastructure_error(run_context: ConsultantRunContext) -> None:
        """
        Populate one infrastructure failure.

        :param run_context: The Consultant run context populated by the test helper.
        """
        run_context.round_state().record_results(
            [
                {
                    "fixture": "failure.hocon",
                    "passed": False,
                    "infrastructure_error": True,
                    "message": "OPENAI_API_KEY=sk-proj-sensitive-value",
                }
            ]
        )

    @staticmethod
    def _record_call(calls: list[Any], name: str, _context: Any) -> None:
        """
        Record an orchestration stage invoked through a monkeypatch.

        :param calls: The calls value.
        :param name: The callback or agent name.
        :param _context: The unused run context required by the patched interface.
        """
        calls.append(name)

    @staticmethod
    def _record_call_and_return(calls: list[Any], name: str, result: bool, _context: Any) -> bool:
        """
        Record an orchestration stage and return its configured control result.

        :param calls: The calls value.
        :param name: The callback or agent name.
        :param result: The configured callback result.
        :param _context: The unused run context required by the patched interface.
        :return: Whether the requested condition is met.
        """
        calls.append(name)
        return result

    @staticmethod
    def _return_worktree(_context: ConsultantRunContext) -> str:
        """
        Return the synthetic worktree used by the cleanup test.

        :param _context: The unused run context required by the patched interface.
        :return: The resulting text.
        """
        return "worktree"

    @staticmethod
    def _return_true(_context: ConsultantRunContext) -> bool:
        """
        Return a terminal orchestration result for the cleanup test.

        :param _context: The unused run context required by the patched interface.
        :return: Whether the requested condition is met.
        """
        return True

    @staticmethod
    def _record_cleanup_call(cleanup_calls: list[tuple[str, Any]], name: str, value: Any) -> None:
        """
        Record one cleanup callback and its argument.

        :param cleanup_calls: The list that records cleanup callbacks.
        :param name: The callback or agent name.
        :param value: The value to validate, redact, or return.
        """
        cleanup_calls.append((name, value))

    @staticmethod
    def _ignore_signal_registration(*_args: Any) -> None:
        """
        Replace signal registration during the isolated unit test.

        :param _args: Unused positional arguments required by the patched interface.
        """

    @staticmethod
    def _remove_or_fail_improvement_cleanup(
        real_rmtree: Any,
        path: Any,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Fail improvement-trace cleanup while preserving unrelated temporary cleanup.

        :param real_rmtree: The unpatched recursive directory remover.
        :param path: The directory selected for removal.
        :param args: Additional positional arguments accepted by the remover.
        :param kwargs: Additional keyword arguments accepted by the remover.
        :raises OSError: Raised for the configured improvement-trace directory.
        """
        expected_path = ThinkingTraceCollector.run_directory("run-one")
        if os.path.normpath(os.fspath(path)) == os.path.normpath(expected_path):
            raise OSError("cleanup denied")
        real_rmtree(path, *args, **kwargs)

    @staticmethod
    def _record_session_directory(
        directories: list[tuple[str, bool]],
        _agent_name: str,
        thinking_directory: str,
    ) -> Mock:
        """
        Record whether the run-owned thinking directory exists during session construction.

        :param directories: The directory observations collected by the test.
        :param _agent_name: The unused agent name required by the patched interface.
        :param thinking_directory: The run-owned thinking directory.
        :return: An inert Consultant session replacement.
        """
        directories.append((thinking_directory, os.path.isdir(thinking_directory)))
        session = Mock(spec=ConsultantSession)
        session.run_identifier.return_value = "run-one"
        return session

    def test_iteration_preserves_stage_order(self) -> None:
        """
        Keep load, record, score, and consult stages in their original order.
        """
        context = self._context()
        calls: list[str] = []

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    NetworkConsultantOrchestrator, "_load_round_results", partial(self._load_failing_round, calls)
                )
            )
            stack.enter_context(
                patch.object(
                    NetworkConsultantOrchestrator, "_record_round", partial(self._record_call, calls, "record")
                )
            )
            stack.enter_context(
                patch.object(
                    NetworkConsultantOrchestrator,
                    "_log_and_commit_round",
                    partial(self._record_call, calls, "commit"),
                )
            )
            stack.enter_context(
                patch.object(
                    NetworkConsultantOrchestrator,
                    "_widen_stale_subset",
                    partial(self._record_call_and_return, calls, "widen", False),
                )
            )
            stack.enter_context(
                patch.object(
                    NetworkConsultantOrchestrator, "_update_scores", partial(self._record_call, calls, "score")
                )
            )
            stack.enter_context(
                patch.object(
                    NetworkConsultantOrchestrator,
                    "_stop_for_plateau",
                    partial(self._record_call_and_return, calls, "plateau", False),
                )
            )
            stack.enter_context(
                patch.object(
                    NetworkConsultantOrchestrator,
                    "_consult_and_apply",
                    partial(self._record_call_and_return, calls, "consult", False),
                )
            )
            should_stop = NetworkConsultantOrchestrator.run_iteration(context)

        self.assertFalse(should_stop)
        self.assertEqual(calls, ["load", "record", "commit", "widen", "score", "plateau", "consult"])

    def test_iteration_stops_before_recording_infrastructure_failure(self) -> None:
        """
        Do not score or modify a network when fixture infrastructure fails.
        """
        context = self._context()
        calls: list[str] = []

        with patch.object(NetworkConsultantOrchestrator, "_load_round_results", self._load_infrastructure_error):
            with (
                patch.object(
                    NetworkConsultantOrchestrator, "_record_round", partial(self._record_call, calls, "record")
                ),
                self.assertLogs("network_consultant", level="ERROR") as captured,
            ):
                should_stop = NetworkConsultantOrchestrator.run_iteration(context)

        self.assertTrue(should_stop)
        self.assertFalse(calls)
        self.assertNotIn("sk-proj-sensitive-value", "\n".join(captured.output))
        self.assertIn("[REDACTED]", "\n".join(captured.output))

    def test_execute_always_cleans_temporary_resources(self) -> None:
        """
        Stop versioning even after an early terminal round.
        """
        context = self._context()
        cleanup_calls: list[tuple[str, Any]] = []

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(NetworkConsultantOrchestrator, "_start_git_versioning", self._return_worktree)
            )
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_iterate", self._return_true))
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "GitVersioning.stop_git_versioning",
                    partial(self._record_cleanup_call, cleanup_calls, "git"),
                )
            )
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.signal.signal",
                    self._ignore_signal_registration,
                )
            )
            NetworkConsultantOrchestrator.execute(context)

        self.assertEqual(cleanup_calls, [("git", "worktree")])

    def test_round_rechecks_apply_in_memory_ratio_overrides(self) -> None:
        """Pass confidence ratios to ordinary fixture rechecks without editing fixture files."""
        context = self._context()
        context.resources().remember_success_ratio_overrides(["failure.hocon"], "3/3")
        results = [{"fixture": "failure.hocon", "passed": True}]

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "ConsultantJobFiles.active",
                    return_value=False,
                )
            )
            run_all_tests = stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "FixtureRunner.run_all_tests",
                    return_value=results,
                )
            )
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_record_round"))
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_log_and_commit_round"))
            stack.enter_context(
                patch.object(NetworkConsultantOrchestrator, "_handle_passing_round", return_value=True)
            )

            should_stop = NetworkConsultantOrchestrator.run_iteration(context)

        self.assertTrue(should_stop)
        run_all_tests.assert_called_once_with(
            "example",
            "run-one",
            only_fixtures=None,
            success_ratio_overrides={"failure.hocon": "3/3"},
        )

    def test_full_suite_uses_declared_fixture_ratios(self) -> None:
        """Exclude confidence overrides from authoritative full-suite scoring."""
        context = self._context()
        context.round_state().record_results([{"fixture": "failure.hocon", "passed": False}])
        context.round_state().schedule_failure_retests()
        context.round_state().start_iteration(2)
        context.resources().remember_success_ratio_overrides(["failure.hocon"], "3/3")
        passing_results = [{"fixture": "failure.hocon", "passed": True}]

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "ConsultantJobFiles.active",
                    return_value=False,
                )
            )
            run_all_tests = stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "FixtureRunner.run_all_tests",
                    side_effect=[passing_results, passing_results],
                )
            )
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_record_round"))
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_log_and_commit_round"))
            stack.enter_context(
                patch.object(NetworkConsultantOrchestrator, "_handle_satisfied_network", return_value=True)
            )
            stack.enter_context(patch.object(context.progress_tracker(), "record"))
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "GitVersioning.commit_hocon_version"
                )
            )

            should_stop = NetworkConsultantOrchestrator.run_iteration(context)

        self.assertTrue(should_stop)
        self.assertEqual(
            run_all_tests.call_args_list,
            [
                call(
                    "example",
                    "run-one",
                    only_fixtures=["failure.hocon"],
                    success_ratio_overrides={"failure.hocon": "3/3"},
                ),
                call("example", "run-one"),
            ],
        )

    def test_zero_iterations_runs_tests_directly_without_caching(self) -> None:
        """Run fixtures without repairs or nsflow-only cache writes in a direct CLI context."""
        context = self._context(max_iterations=0)
        results = [
            {"fixture": "passing.hocon", "passed": True},
            {"fixture": "failing.hocon", "passed": False},
        ]

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "ConsultantJobFiles.active",
                    return_value=False,
                )
            )
            run_all_tests = stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "FixtureRunner.run_all_tests",
                    return_value=results,
                )
            )
            cache_save = stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator."
                    "GeneratedTestsCache.save"
                )
            )
            progress_record = stack.enter_context(patch.object(context.progress_tracker(), "record"))
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.signal.signal",
                    self._ignore_signal_registration,
                )
            )
            captured = stack.enter_context(self.assertLogs("network_consultant", level="INFO"))

            NetworkConsultantOrchestrator.execute(context)

        run_all_tests.assert_called_once_with("example", "run-one", only_fixtures=None)
        cache_save.assert_not_called()
        progress_record.assert_not_called()
        self.assertIn("Result: 1/2 passing.", "\n".join(captured.output))

    def test_run_reports_a_thinking_trace_cleanup_failure(self) -> None:
        """Continue initialization while reporting a failed best-effort trace cleanup."""
        options = self._context().options()
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(NetworkConsultantOrchestrator, "_validate_options", return_value="example.hocon")
            )
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "configure_logging"))
            consultant_session = stack.enter_context(
                patch("neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.ConsultantSession")
            )
            consultant_session.return_value.run_identifier.return_value = "run-one"
            stack.enter_context(
                patch("coded_tools.agent_network_consultant.network_scratchpad.NetworkScratchpad.clear_for_hocon_file")
            )
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.os.path.exists",
                    return_value=True,
                )
            )
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.shutil.rmtree",
                    side_effect=partial(self._remove_or_fail_improvement_cleanup, shutil.rmtree),
                )
            )
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_generate_tests"))
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "execute"))
            captured = stack.enter_context(self.assertLogs("network_consultant", level="WARNING"))

            NetworkConsultantOrchestrator.run(options)

        self.assertIn("cleanup denied", "\n".join(captured.output))

    def test_improvement_trace_cleanup_removes_only_the_current_run(self) -> None:
        """Preserve another active Consultant run's consolidated traces during initialization."""
        options = self._context().options()
        with TemporaryDirectory() as temporary_directory:
            first_run = os.path.join(temporary_directory, "run-one")
            second_run = os.path.join(temporary_directory, "run-two")
            os.makedirs(first_run)
            os.makedirs(second_run)
            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(NetworkConsultantOrchestrator, "_validate_options", return_value="example.hocon")
                )
                stack.enter_context(patch.object(NetworkConsultantOrchestrator, "configure_logging"))
                consultant_session = stack.enter_context(
                    patch(
                        "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.ConsultantSession"
                    )
                )
                consultant_session.return_value.run_identifier.return_value = "run-one"
                stack.enter_context(
                    patch(
                        "coded_tools.agent_network_consultant.network_scratchpad.NetworkScratchpad."
                        "clear_for_hocon_file"
                    )
                )
                stack.enter_context(
                    patch.object(
                        thinking_trace_collector,
                        "IMPROVEMENT_THINKING_DIR",
                        temporary_directory,
                    )
                )
                stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_generate_tests"))
                stack.enter_context(patch.object(NetworkConsultantOrchestrator, "execute"))

                NetworkConsultantOrchestrator.run(options)

            self.assertFalse(os.path.exists(first_run))
            self.assertTrue(os.path.exists(second_run))

    def test_run_scopes_session_thinking_to_an_automatic_temporary_directory(self) -> None:
        """Give every session one run-owned thinking directory and remove it afterward."""
        options = self._context().options()
        directories: list[tuple[str, bool]] = []
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(NetworkConsultantOrchestrator, "_validate_options", return_value="example.hocon")
            )
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "configure_logging"))
            stack.enter_context(
                patch(
                    "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.ConsultantSession",
                    side_effect=partial(self._record_session_directory, directories),
                )
            )
            stack.enter_context(
                patch("coded_tools.agent_network_consultant.network_scratchpad.NetworkScratchpad.clear_for_hocon_file")
            )
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_clear_improvement_thinking"))
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "_generate_tests"))
            stack.enter_context(patch.object(NetworkConsultantOrchestrator, "execute"))

            NetworkConsultantOrchestrator.run(options)

        self.assertEqual(1, len(directories))
        thinking_directory, existed_during_run = directories[0]
        self.assertTrue(existed_during_run)
        self.assertFalse(os.path.exists(thinking_directory))

    def test_serialized_run_always_cleans_the_child_thinking_directory(self) -> None:
        """Remove child-owned raw traces even when Consultant execution fails."""
        with TemporaryDirectory() as temporary_directory:
            thinking_directory = os.path.join(temporary_directory, "raw-thinking")
            os.makedirs(thinking_directory)
            serialized_run = json.dumps(
                {
                    "options": self._context().options()._asdict(),
                    "owned_thinking_directory": thinking_directory,
                }
            )
            with (
                patch.object(NetworkConsultantOrchestrator, "run", side_effect=RuntimeError("run failed")),
                self.assertRaisesRegex(RuntimeError, "run failed"),
            ):
                NetworkConsultantOrchestrator.run_serialized(serialized_run)

            self.assertFalse(os.path.exists(thinking_directory))

    def test_configure_logging_does_not_configure_the_root_logger(self) -> None:
        """Keep host-application root logging unchanged when Consultant starts."""
        root_logger = logging.getLogger()
        original_level = root_logger.level
        original_handlers = list(root_logger.handlers)

        with patch(
            "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.logging.basicConfig"
        ) as basic_config:
            NetworkConsultantOrchestrator.configure_logging()

        basic_config.assert_not_called()
        self.assertEqual(root_logger.level, original_level)
        self.assertEqual(root_logger.handlers, original_handlers)

    def test_validation_requires_the_git_versions_destination_before_initialization(self) -> None:
        """Reject an unconfigured snapshot run before opening sessions or generating fixtures."""
        options = ConsultantOptions(
            force_generate=False,
            git_versions=True,
            hocon_file="example.hocon",
            max_iterations=2,
            only_fixtures=None,
            success_ratio="3/3",
            test_guidance="",
            test_level="normal",
            ungrounded="stop",
            use_case=None,
        )

        with (
            patch.dict("os.environ", {"NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE": ""}),
            self.assertRaisesRegex(ValueError, "NETWORK_CONSULTANT_GIT_VERSIONS_REMOTE"),
        ):
            NetworkConsultantOrchestrator.run(options)
