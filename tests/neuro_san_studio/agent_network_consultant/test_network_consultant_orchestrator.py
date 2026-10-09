# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""Behavior tests for the stateful Agent Network Consultant orchestrator."""

import json
import logging
import os
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import call
from unittest.mock import patch

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.generated_tests_cache import GeneratedTestsCache
from neuro_san_studio.agent_network_consultant.network_consultant_orchestrator import NetworkConsultantOrchestrator
from neuro_san_studio.agent_network_consultant.network_test_environment import NetworkTestEnvironment


class TestNetworkConsultantOrchestrator(TestCase):
    """Verify orchestration through public entry points and real run state."""

    LOGGER_NAME = "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator"

    @staticmethod
    def _context(
        max_iterations: int = 2,
        only_fixtures: list[str] | None = None,
        success_ratio: str = "3/3",
    ) -> ConsultantRunContext:
        """
        Build one isolated run context with a mocked Neuro SAN session boundary.

        :param max_iterations: The configured repair iteration limit.
        :param only_fixtures: The optional initial fixture selection.
        :param success_ratio: The confidence-verification ratio.
        :return: The run context.
        """
        options = ConsultantOptions(
            force_generate=False,
            hocon_file="example.hocon",
            max_iterations=max_iterations,
            only_fixtures=only_fixtures,
            success_ratio=success_ratio,
            test_guidance="",
            test_level="normal",
            ungrounded="stop",
            use_case=None,
        )
        session = Mock(spec=ConsultantSession)
        session.run_identifier.return_value = "run-one"
        session.chat.return_value = "Repairs complete."
        session.sly_data_value.return_value = 0
        return ConsultantRunContext(
            options=options,
            session=session,
            target=ConsultantTarget("example.hocon", "example", "Preserve behavior", "registries/example.hocon"),
        )

    @staticmethod
    def _failure(fixture_path: str, fixture_name: str = "failure.hocon") -> dict[str, Any]:
        """
        Build one ordinary fixture failure that the real diagnosis builder can read.

        :param fixture_path: The readable fixture path.
        :param fixture_name: The fixture basename reported to the workflow.
        :return: The fixture result.
        """
        return {
            "fixture": fixture_name,
            "path": fixture_path,
            "passed": False,
            "message": "Expected behavior was not observed.",
            "criteria_passed": 0,
            "criteria_total": 1,
        }

    @staticmethod
    def _passing(fixture_name: str = "passing.hocon") -> dict[str, Any]:
        """
        Build one passing fixture result.

        :param fixture_name: The fixture basename reported to the workflow.
        :return: The fixture result.
        """
        return {
            "fixture": fixture_name,
            "passed": True,
            "criteria_passed": 1,
            "criteria_total": 1,
        }

    @staticmethod
    def _write_fixture(directory: str, fixture_name: str = "failure.hocon") -> str:
        """
        Create a readable fixture body for the real diagnosis prompt.

        :param directory: The temporary directory that owns the fixture.
        :param fixture_name: The fixture file name.
        :return: The fixture path.
        """
        fixture_path = Path(directory) / fixture_name
        fixture_path.write_text("test_cases = []\n", encoding="utf-8")
        return str(fixture_path)

    @staticmethod
    def _options_payload(options: ConsultantOptions) -> dict[str, object]:
        """
        Serialize the data-only options object for a process-boundary test.

        :param options: The selected run options.
        :return: The JSON-compatible option values.
        """
        return {
            "use_case": options.use_case,
            "hocon_file": options.hocon_file,
            "direction": options.direction,
            "test_level": options.test_level,
            "test_guidance": options.test_guidance,
            "force_generate": options.force_generate,
            "ungrounded": options.ungrounded,
            "only_fixtures": options.only_fixtures,
            "max_iterations": options.max_iterations,
            "success_ratio": options.success_ratio,
        }

    @staticmethod
    def _record_session_directory(
        directories: list[tuple[str, str, bool]],
        agent_name: str,
        thinking_directory: str,
    ) -> Mock:
        """
        Record whether a run-owned thinking directory exists during session construction.

        :param directories: The collected directory observations.
        :param agent_name: The explicit network reference used for the direct session.
        :param thinking_directory: The run-owned thinking directory.
        :return: An inert session boundary.
        """
        directories.append((agent_name, thinking_directory, os.path.isdir(thinking_directory)))
        session = Mock(spec=ConsultantSession)
        session.run_identifier.return_value = "run-one"
        session.chat.return_value = "Repairs complete."
        session.sly_data_value.return_value = 0
        return session

    def _probe_results(
        self,
        directory: str,
        passing_subset: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Build subset and regressed full-suite results for a widening probe.

        :param directory: The temporary directory that owns readable failure fixtures.
        :param passing_subset: Whether the selected subset passes before the complete-suite probe.
        :return: The subset results followed by the regressed complete-suite results.
        """
        first_path = self._write_fixture(directory, "a.hocon")
        second_path = self._write_fixture(directory, "b.hocon")
        subset_results: list[dict[str, Any]] = []
        if passing_subset:
            subset_results.append(self._passing("a.hocon"))
            subset_results.append(self._passing("b.hocon"))
        else:
            subset_results.append(self._failure(first_path, "a.hocon"))
            subset_results.append(self._failure(second_path, "b.hocon"))
        full_results: list[dict[str, Any]] = []
        full_results.append(self._failure(first_path, "a.hocon"))
        full_results.append(self._failure(second_path, "b.hocon"))
        for index in range(8):
            full_results.append(self._passing(f"passing-{index}.hocon"))
        return subset_results, full_results

    def test_iteration_preserves_stage_order(self) -> None:
        """Run fixtures, publish progress, and consult in the established order."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            context = self._context()
            context.round_state().start_iteration(1)
            orchestrator = NetworkConsultantOrchestrator(context)
            result = self._failure(fixture_path)
            timeline = Mock()
            with patch.object(FixtureRunner, "run_all_tests", return_value=[result]) as run_tests:
                with patch.object(context.progress_tracker(), "record") as record_progress:
                    timeline.attach_mock(run_tests, "run_tests")
                    timeline.attach_mock(record_progress, "record_progress")
                    timeline.attach_mock(context.session().chat, "chat")
                    should_stop = orchestrator.run_iteration()

        stage_names: list[str] = []
        for recorded_call in timeline.mock_calls:
            stage_names.append(recorded_call[0])
        self.assertFalse(should_stop)
        self.assertEqual(["run_tests", "record_progress", "chat"], stage_names)

    def test_current_stale_subset_round_triggers_full_suite_without_an_extra_iteration(self) -> None:
        """Widen a stale subset immediately instead of spending another repair iteration."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            context = self._context()
            round_state = context.round_state()
            round_state.start_iteration(2)
            round_state.set_fixture_selection(["failure.hocon"], 1)
            context.scores().record_full_score((0, 0))
            for _unused_index in range(ConsultantScoring.PLATEAU_STRIKES):
                context.scores().record_subset_score((0, 0))
            context.session().chat.return_value = "TOOL_ISSUE: stop safely"
            orchestrator = NetworkConsultantOrchestrator(context)
            subset_result = self._failure(fixture_path)
            full_result = self._failure(fixture_path)
            with patch.object(
                FixtureRunner, "run_all_tests", side_effect=[[subset_result], [full_result]]
            ) as run_tests:
                should_stop = orchestrator.run_iteration()

        self.assertTrue(should_stop)
        self.assertEqual(2, run_tests.call_count)
        self.assertIsNone(round_state.fixture_selection())
        context.session().chat.assert_called_once()

    def test_nonterminal_full_suite_probes_do_not_publish_after(self) -> None:
        """Do not label a regressed full-suite probe as the terminal After checkpoint."""
        with TemporaryDirectory() as directory:
            for passing_subset in (True, False):
                with self.subTest(passing_subset=passing_subset):
                    context = self._context()
                    round_state = context.round_state()
                    round_state.start_iteration(2)
                    round_state.set_fixture_selection(["a.hocon", "b.hocon"], 10)
                    context.scores().record_full_score((9, 9))
                    if not passing_subset:
                        for _unused_index in range(ConsultantScoring.PLATEAU_STRIKES):
                            context.scores().record_subset_score((8, 8))
                    context.session().chat.return_value = "TOOL_ISSUE: manual repair required"
                    subset_results, full_results = self._probe_results(directory, passing_subset)
                    orchestrator = NetworkConsultantOrchestrator(context)
                    with patch.object(
                        FixtureRunner,
                        "run_all_tests",
                        side_effect=[subset_results, full_results],
                    ):
                        with patch.object(context.progress_tracker(), "record") as record_progress:
                            should_stop = orchestrator.run_iteration()

                    checkpoints: list[str] = []
                    for recorded_call in record_progress.call_args_list:
                        checkpoints.append(recorded_call.args[1])
                    self.assertTrue(should_stop)
                    self.assertNotIn("after", checkpoints)
                    self.assertFalse(round_state.is_subset_check())
                    self.assertEqual([], context.scores().subset_scores())

    def test_shrinking_failure_subsets_count_as_progress(self) -> None:
        """Keep repairing when each subset round removes another failure."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            context = self._context(max_iterations=4)
            round_state = context.round_state()
            round_state.set_fixture_selection(
                ["a.hocon", "b.hocon", "c.hocon", "d.hocon", "e.hocon"],
                6,
            )
            shrinking_results: list[list[dict[str, Any]]] = []
            for remaining_failures in (4, 3, 2, 1):
                current_results: list[dict[str, Any]] = []
                current_results.append(self._passing(f"fixed-{remaining_failures}.hocon"))
                for failure_index in range(remaining_failures):
                    current_results.append(self._failure(fixture_path, f"failure-{failure_index}.hocon"))
                shrinking_results.append(current_results)
            orchestrator = NetworkConsultantOrchestrator(context)
            stop_results: list[bool] = []
            with patch.object(FixtureRunner, "run_all_tests", side_effect=shrinking_results) as run_tests:
                for iteration in range(1, 5):
                    round_state.start_iteration(iteration)
                    stop_results.append(orchestrator.run_iteration())

        self.assertEqual([False, False, False, False], stop_results)
        self.assertEqual(4, run_tests.call_count)
        for recorded_call in run_tests.call_args_list:
            self.assertIsNotNone(recorded_call.kwargs.get("only_fixtures"))

    def test_iteration_stops_before_recording_infrastructure_failure(self) -> None:
        """Do not score or modify a network after fixture infrastructure fails."""
        context = self._context()
        context.round_state().start_iteration(1)
        orchestrator = NetworkConsultantOrchestrator(context)
        result = {
            "fixture": "failure.hocon",
            "passed": False,
            "infrastructure_error": True,
            "message": "OPENAI_API_KEY=sk-proj-sensitive-value",
        }
        with patch.object(FixtureRunner, "run_all_tests", return_value=[result]):
            with patch.object(context.progress_tracker(), "record") as record_progress:
                with self.assertLogs(self.LOGGER_NAME, level="ERROR") as captured:
                    should_stop = orchestrator.run_iteration()

        self.assertTrue(should_stop)
        record_progress.assert_not_called()
        context.session().chat.assert_not_called()
        self.assertNotIn("sk-proj-sensitive-value", "\n".join(captured.output))
        self.assertIn("[REDACTED]", "\n".join(captured.output))

    def test_passing_full_suite_stops_without_another_consultant_edit(self) -> None:
        """Treat a passing complete suite as terminal without another Consultant edit."""
        context = self._context()
        context.round_state().start_iteration(1)
        orchestrator = NetworkConsultantOrchestrator(context)
        results = [self._passing()]
        with patch.object(FixtureRunner, "run_all_tests", return_value=results) as run_tests:
            with patch.object(context.progress_tracker(), "record") as record_progress:
                should_stop = orchestrator.run_iteration()

        self.assertTrue(should_stop)
        run_tests.assert_called_once_with("example", only_fixtures=None)
        context.session().chat.assert_not_called()
        self.assertEqual(
            [call(results, "before", 1), call(results, "after", 1)],
            record_progress.call_args_list,
        )

    def test_consult_does_not_log_response_content(self) -> None:
        """Keep model responses that may echo private answers out of logs."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            context = self._context()
            context.round_state().start_iteration(1)
            private_response = "The private account identifier is customer-secret-123"
            context.session().chat.return_value = private_response
            orchestrator = NetworkConsultantOrchestrator(context)
            with patch.object(FixtureRunner, "run_all_tests", return_value=[self._failure(fixture_path)]):
                with self.assertLogs(self.LOGGER_NAME, level="INFO") as captured:
                    should_stop = orchestrator.run_iteration()

        log_output = "\n".join(captured.output)
        self.assertFalse(should_stop)
        self.assertIn("Consultant response received", log_output)
        self.assertNotIn(private_response, log_output)

    def test_consult_passes_the_current_round_state_to_diagnosis(self) -> None:
        """Describe current subset coverage from the real round state in the diagnosis prompt."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory, "two.hocon")
            context = self._context()
            round_state = context.round_state()
            round_state.start_iteration(2)
            round_state.set_fixture_selection(["one.hocon", "two.hocon"], 5)
            orchestrator = NetworkConsultantOrchestrator(context)
            results = [self._passing("one.hocon"), self._failure(fixture_path, "two.hocon")]
            with patch.object(FixtureRunner, "run_all_tests", return_value=results):
                should_stop = orchestrator.run_iteration()

        prompt = context.session().chat.call_args.args[0]
        self.assertFalse(should_stop)
        self.assertIn("2 of the 5 total fixtures", prompt)
        self.assertIn("Preserve behavior", prompt)

    def test_generation_flows_do_not_log_free_form_content(self) -> None:
        """Keep private design and test-generation content out of orchestration logs."""
        self._assert_design_network_does_not_log_free_form_content()
        self._assert_generate_tests_does_not_log_free_form_content()

    def _assert_design_network_does_not_log_free_form_content(self) -> None:
        """Keep the use case and Designer response out of orchestration logs."""
        private_request = "Build a network for private customer account 123."
        private_response = "Created the private customer account network."
        options = ConsultantOptions(use_case=private_request, max_iterations=0)
        consultant_session = Mock(spec=ConsultantSession)
        consultant_session.run_identifier.return_value = "run-one"
        designer_session = Mock(spec=ConsultantSession)
        designer_session.chat.return_value = private_response
        designer_session.sly_data_value.return_value = "customer_network"
        with patch(
            "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.ConsultantSession",
            side_effect=[consultant_session, designer_session],
        ):
            with patch.object(FixtureRunner, "fixture_paths", return_value=["existing.hocon"]):
                with patch.object(FixtureRunner, "run_all_tests", return_value=[self._passing()]):
                    with self.assertLogs(self.LOGGER_NAME, level="INFO") as captured:
                        NetworkConsultantOrchestrator.run(options)

        log_output = "\n".join(captured.output)
        designer_session.chat.assert_called_once_with(private_request)
        designer_session.sly_data_value.assert_called_once_with(AGENT_NETWORK_NAME)
        self.assertIn("Designer response received", log_output)
        self.assertNotIn(private_request, log_output)
        self.assertNotIn(private_response, log_output)

    def _assert_generate_tests_does_not_log_free_form_content(self) -> None:
        """Keep private test guidance and the ANTeGen response out of logs."""
        private_guidance = "Test private customer account 123."
        private_response = "Generated fixtures for private customer account 123."
        options = ConsultantOptions(
            hocon_file="example.hocon",
            max_iterations=0,
            test_guidance=private_guidance,
        )
        consultant_session = Mock(spec=ConsultantSession)
        consultant_session.run_identifier.return_value = "run-one"
        testgen_session = Mock(spec=ConsultantSession)
        testgen_session.chat.return_value = private_response
        with patch(
            "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.ConsultantSession",
            side_effect=[consultant_session, testgen_session],
        ):
            with patch.object(FixtureRunner, "fixture_paths", return_value=[]):
                with patch.object(FixtureRunner, "run_all_tests", return_value=[self._passing()]):
                    with self.assertLogs(self.LOGGER_NAME, level="INFO") as captured:
                        NetworkConsultantOrchestrator.run(options)

        request = testgen_session.chat.call_args.args[0]
        log_output = "\n".join(captured.output)
        self.assertIn(private_guidance, request)
        self.assertIn("ANTeGen response received", log_output)
        self.assertNotIn(private_guidance, log_output)
        self.assertNotIn(private_response, log_output)

    def test_consult_handles_operational_and_contract_errors(self) -> None:
        """Redact operational failures while allowing programming errors to propagate."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            secret = "customer-secret-123"
            context = self._context()
            context.round_state().start_iteration(1)
            context.session().chat.side_effect = RuntimeError(f"api_key={secret}")
            orchestrator = NetworkConsultantOrchestrator(context)
            with patch.object(FixtureRunner, "run_all_tests", return_value=[self._failure(fixture_path)]):
                with self.assertLogs(self.LOGGER_NAME, level="ERROR") as captured:
                    should_stop = orchestrator.run_iteration()
            self.assertTrue(should_stop)
            self.assertNotIn(secret, "\n".join(captured.output))
            self.assertIn("[REDACTED]", "\n".join(captured.output))

            errors: tuple[TypeError | ValueError, ...] = (
                TypeError("contract failure"),
                ValueError("contract failure"),
            )
            for error in errors:
                with self.subTest(exception_type=type(error)):
                    context = self._context()
                    context.round_state().start_iteration(1)
                    context.session().chat.side_effect = error
                    orchestrator = NetworkConsultantOrchestrator(context)
                    with patch.object(FixtureRunner, "run_all_tests", return_value=[self._failure(fixture_path)]):
                        with self.assertRaisesRegex(type(error), "contract failure"):
                            orchestrator.run_iteration()

    def test_round_rechecks_apply_in_memory_ratio_overrides(self) -> None:
        """Give ordinary rechecks their in-memory confidence-ratio overrides."""
        context = self._context()
        context.round_state().start_iteration(1)
        context.round_state().remember_success_ratio_overrides(["failure.hocon"], "3/3")
        orchestrator = NetworkConsultantOrchestrator(context)
        ratio_runner = Mock(spec=FixtureRunner)
        ratio_runner.run_all_tests.return_value = [self._passing("failure.hocon")]
        with patch(
            "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.FixtureRunner",
            return_value=ratio_runner,
        ) as runner_constructor:
            with patch.object(FixtureRunner, "run_all_tests", return_value=[self._passing("failure.hocon")]):
                should_stop = orchestrator.run_iteration()

        self.assertTrue(should_stop)
        runner_constructor.assert_called_once_with(
            "run-one",
            success_ratio_overrides={"failure.hocon": "3/3"},
        )

    def test_full_suite_uses_declared_fixture_ratios(self) -> None:
        """Exclude temporary confidence overrides from authoritative full-suite scoring."""
        context = self._context()
        round_state = context.round_state()
        round_state.start_iteration(2)
        round_state.set_fixture_selection(["failure.hocon"], 1)
        round_state.remember_success_ratio_overrides(["failure.hocon"], "3/3")
        orchestrator = NetworkConsultantOrchestrator(context)
        subset_runner = Mock(spec=FixtureRunner)
        subset_runner.run_all_tests.return_value = [self._passing("failure.hocon")]
        with patch(
            "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.FixtureRunner",
            return_value=subset_runner,
        ) as runner_constructor:
            with patch.object(
                FixtureRunner, "run_all_tests", return_value=[self._passing("failure.hocon")]
            ) as full_run:
                should_stop = orchestrator.run_iteration()

        self.assertTrue(should_stop)
        runner_constructor.assert_called_once_with(
            "run-one",
            success_ratio_overrides={"failure.hocon": "3/3"},
        )
        full_run.assert_called_once_with("example")

    def test_initial_fixture_selection_bypasses_cache_and_confirms_full_suite(self) -> None:
        """Run the requested fixtures first, then confirm success against the complete suite."""
        with TemporaryDirectory() as job_directory:
            environment = {"NSFLOW_JOB_ID": "job-one", "NSFLOW_JOB_DIR": job_directory}
            with patch.dict(os.environ, environment):
                context = self._context(only_fixtures=["selected.hocon"])
                orchestrator = NetworkConsultantOrchestrator(context)
                selected_results = [self._passing("selected.hocon")]
                full_results = [self._passing("selected.hocon"), self._passing("other.hocon")]
                with patch.object(
                    FixtureRunner,
                    "fixture_paths",
                    return_value=["selected.hocon", "other.hocon"],
                ):
                    with patch.object(
                        FixtureRunner,
                        "run_all_tests",
                        side_effect=[selected_results, full_results],
                    ) as run_tests:
                        with patch.object(GeneratedTestsCache, "load") as cache_load:
                            orchestrator.execute()

                progress_path = Path(job_directory) / "job-one.progress.jsonl"
                progress_entries: list[dict[str, Any]] = []
                for line in progress_path.read_text(encoding="utf-8").splitlines():
                    progress_entries.append(json.loads(line))

        checkpoints: list[Any] = []
        for entry in progress_entries:
            checkpoints.append(entry.get("checkpoint"))
        cache_load.assert_not_called()
        self.assertEqual(2, run_tests.call_count)
        self.assertEqual(["before", "after"], checkpoints)
        context.session().chat.assert_not_called()

    def test_max_iterations_verifies_final_outcomes(self) -> None:
        """Verify the final repaired state and handle an unverified infrastructure result safely."""
        self._assert_max_iterations_keeps_the_final_repair()
        self._assert_max_iterations_reports_infrastructure_failure()

    def _assert_max_iterations_keeps_the_final_repair(self) -> None:
        """Measure and retain the final repair after the configured ceiling."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            context = self._context(max_iterations=1)
            orchestrator = NetworkConsultantOrchestrator(context)
            first_result = self._failure(fixture_path)
            final_result = self._failure(fixture_path)
            with patch.object(
                FixtureRunner,
                "run_all_tests",
                side_effect=[[first_result], [final_result]],
            ) as run_tests:
                with patch.object(context.progress_tracker(), "record") as record_progress:
                    orchestrator.execute()

        self.assertEqual(2, run_tests.call_count)
        context.session().chat.assert_called_once()
        self.assertEqual(final_result, context.round_state().results()[0])
        self.assertEqual("after", record_progress.call_args_list[-1].args[1])

    def _assert_max_iterations_reports_infrastructure_failure(self) -> None:
        """Report an unverified final repair without publishing a terminal success checkpoint."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            context = self._context(max_iterations=1)
            orchestrator = NetworkConsultantOrchestrator(context)
            first_result = self._failure(fixture_path)
            infrastructure_result = {
                "fixture": "failure.hocon",
                "passed": False,
                "infrastructure_error": True,
                "message": "The provider was unavailable.",
            }
            with patch.object(
                FixtureRunner,
                "run_all_tests",
                side_effect=[[first_result], [infrastructure_result]],
            ) as run_tests:
                with patch.object(context.progress_tracker(), "record") as record_progress:
                    with self.assertLogs(self.LOGGER_NAME, level="ERROR") as captured:
                        orchestrator.execute()

        self.assertEqual(2, run_tests.call_count)
        context.session().chat.assert_called_once()
        checkpoints: list[str] = []
        for recorded_call in record_progress.call_args_list:
            checkpoints.append(recorded_call.args[1])
        self.assertEqual(["before"], checkpoints)
        self.assertIn("Final confirmation could not complete", "\n".join(captured.output))

    def test_zero_iterations_runs_tests_directly_without_caching(self) -> None:
        """Run fixtures without repairs or cache writes in a direct terminal context."""
        context = self._context(max_iterations=0)
        orchestrator = NetworkConsultantOrchestrator(context)
        results = [self._passing(), {"fixture": "failing.hocon", "passed": False}]
        with patch.object(FixtureRunner, "run_all_tests", return_value=results) as run_tests:
            with patch.object(GeneratedTestsCache, "save") as cache_save:
                with self.assertLogs(self.LOGGER_NAME, level="INFO") as captured:
                    orchestrator.execute()

        run_tests.assert_called_once_with("example", only_fixtures=None)
        cache_save.assert_not_called()
        context.session().chat.assert_not_called()
        self.assertIn("Result: 1/2 passing.", "\n".join(captured.output))

    def test_zero_iterations_does_not_cache_infrastructure_failures(self) -> None:
        """Require a later nsflow repair job to retry an infrastructure-failed baseline."""
        with TemporaryDirectory() as job_directory:
            environment = {"NSFLOW_JOB_ID": "job-one", "NSFLOW_JOB_DIR": job_directory}
            with patch.dict(os.environ, environment):
                context = self._context(max_iterations=0)
                orchestrator = NetworkConsultantOrchestrator(context)
                result = {
                    "fixture": "failure.hocon",
                    "passed": False,
                    "infrastructure_error": True,
                    "message": "OPENAI_API_KEY=customer-secret-123",
                }
                with patch.object(FixtureRunner, "run_all_tests", return_value=[result]):
                    with patch.object(GeneratedTestsCache, "save") as cache_save:
                        with self.assertLogs(self.LOGGER_NAME, level="ERROR") as captured:
                            orchestrator.execute()
                progress_path = Path(job_directory) / "job-one.progress.jsonl"
                progress_exists = progress_path.exists()

        cache_save.assert_not_called()
        self.assertFalse(progress_exists)
        self.assertIn("results were not cached", "\n".join(captured.output))
        self.assertNotIn("customer-secret-123", "\n".join(captured.output))

    def test_unknown_fixture_selection_is_rejected(self) -> None:
        """Reject unknown fixture selections before repair work."""
        context = self._context(only_fixtures=["missing.hocon"])
        orchestrator = NetworkConsultantOrchestrator(context)
        with patch.object(FixtureRunner, "fixture_paths", return_value=["available.hocon"]):
            with patch.object(
                FixtureRunner,
                "run_all_tests",
                side_effect=ValueError("Requested fixture(s) not found: missing.hocon"),
            ):
                with self.assertRaisesRegex(ValueError, "missing.hocon"):
                    orchestrator.execute()
        context.session().chat.assert_not_called()

    def test_each_response_gets_its_own_protocol_processor(self) -> None:
        """Parse every Consultant response independently instead of retaining prior directives."""
        with TemporaryDirectory() as directory:
            fixture_path = self._write_fixture(directory)
            context = self._context()
            context.session().chat.side_effect = [
                "Repairs complete.",
                "STRUCTURAL_CHANGE_REQUIRED: add a new tool",
            ]
            orchestrator = NetworkConsultantOrchestrator(context)
            result = self._failure(fixture_path)
            outcomes: list[bool] = []
            with patch.object(FixtureRunner, "run_all_tests", side_effect=[[result], [result]]):
                context.round_state().start_iteration(1)
                outcomes.append(orchestrator.run_iteration())
                context.round_state().start_iteration(2)
                outcomes.append(orchestrator.run_iteration())

        self.assertEqual([False, True], outcomes)
        self.assertEqual(2, context.session().chat.call_count)

    def test_owned_thinking_directories_are_always_cleaned(self) -> None:
        """Clean parent-created and child-owned thinking directories on every exit path."""
        self._assert_run_scopes_session_thinking_to_an_automatic_temporary_directory()
        self._assert_serialized_run_always_cleans_the_child_thinking_directory()
        self._assert_serialized_invalid_options_clean_the_child_thinking_directory()
        self._assert_payload_file_forwards_the_exact_content()

    def _assert_run_scopes_session_thinking_to_an_automatic_temporary_directory(self) -> None:
        """Give every session one run-owned thinking directory and remove it afterward."""
        options = self._context(max_iterations=0).options()
        directories: list[tuple[str, str, bool]] = []
        session_factory = partial(self._record_session_directory, directories)
        with patch(
            "neuro_san_studio.agent_network_consultant.network_consultant_orchestrator.ConsultantSession",
            side_effect=session_factory,
        ):
            with patch.object(FixtureRunner, "fixture_paths", return_value=["existing.hocon"]):
                with patch.object(FixtureRunner, "run_all_tests", return_value=[self._passing()]):
                    NetworkConsultantOrchestrator.run(options)

        self.assertEqual(1, len(directories))
        agent_name, thinking_directory, existed_during_run = directories[0]
        self.assertEqual(NetworkConsultantOrchestrator.CONSULTANT_NETWORK_FILE, agent_name)
        self.assertTrue(existed_during_run)
        self.assertFalse(os.path.exists(thinking_directory))

    def _assert_serialized_run_always_cleans_the_child_thinking_directory(self) -> None:
        """Remove child-owned raw traces even when Consultant execution fails."""
        with TemporaryDirectory(prefix=NetworkTestEnvironment.THINKING_DIRECTORY_PREFIX) as thinking_directory:
            serialized_run = json.dumps(
                {
                    "options": self._options_payload(self._context().options()),
                    "owned_thinking_directory": thinking_directory,
                }
            )
            with patch.object(NetworkConsultantOrchestrator, "run", side_effect=RuntimeError("run failed")):
                with self.assertRaisesRegex(RuntimeError, "run failed"):
                    NetworkConsultantOrchestrator.run_serialized(serialized_run)
            self.assertFalse(os.path.exists(thinking_directory))

    def _assert_serialized_invalid_options_clean_the_child_thinking_directory(self) -> None:
        """Translate invalid option construction into ValueError and retain cleanup guarantees."""
        with TemporaryDirectory(prefix=NetworkTestEnvironment.THINKING_DIRECTORY_PREFIX) as thinking_directory:
            serialized_run = json.dumps(
                {
                    "options": {"hocon_file": "example.hocon", "unknown_option": True},
                    "owned_thinking_directory": thinking_directory,
                }
            )

            with self.assertRaisesRegex(ValueError, "serialized Consultant options are invalid") as raised:
                NetworkConsultantOrchestrator.run_serialized(serialized_run)

            self.assertIsNotNone(raised.exception.__cause__)
            self.assertFalse(os.path.exists(thinking_directory))

    def _assert_payload_file_forwards_the_exact_content(self) -> None:
        """Read the process-boundary payload from disk and forward its complete serialized content."""
        with TemporaryDirectory() as directory:
            payload_path = Path(directory) / "consultant.json"
            serialized_run = '{"options": {"hocon_file": "example.hocon"}}'
            payload_path.write_text(serialized_run, encoding="utf-8")

            with patch.object(NetworkConsultantOrchestrator, "run_serialized") as run_serialized:
                NetworkConsultantOrchestrator.run_payload_file(str(payload_path))

        run_serialized.assert_called_once_with(serialized_run)

    def test_configure_logging_does_not_configure_the_root_logger(self) -> None:
        """Keep host and unrelated logger configuration unchanged when Consultant starts."""
        root_logger = logging.getLogger()
        package_logger = logging.getLogger("neuro_san_studio.agent_network_consultant")
        served_manifest_logger = logging.getLogger("ServedManifestConfigFilter")
        original_package_level = package_logger.level
        original_root_level = root_logger.level
        original_root_handlers = tuple(root_logger.handlers)
        original_served_manifest_level = served_manifest_logger.level
        try:
            NetworkConsultantOrchestrator.configure_logging()
            self.assertEqual(logging.INFO, package_logger.level)
            self.assertEqual(original_root_level, root_logger.level)
            self.assertEqual(original_root_handlers, tuple(root_logger.handlers))
            self.assertEqual(original_served_manifest_level, served_manifest_logger.level)
        finally:
            package_logger.setLevel(original_package_level)
