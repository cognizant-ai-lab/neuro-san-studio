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
"""Run the Agent Network Consultant's iterative test-and-fix workflow."""

import json
import logging
import os
import sys
from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.consultant_option_validator import ConsultantOptionValidator
from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_response_processor import ConsultantResponseProcessor
from neuro_san_studio.agent_network_consultant.consultant_response_protocol import ConsultantResponseProtocol
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.generated_tests_cache import GeneratedTestsCache
from neuro_san_studio.agent_network_consultant.headless_clarification_answerer import HeadlessClarificationAnswerer
from neuro_san_studio.agent_network_consultant.network_test_environment import NetworkTestEnvironment
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.agent_network_consultant.stuck_patch_error import StuckPatchError
from neuro_san_studio.agent_network_consultant.terminal_clarification_answerer import TerminalClarificationAnswerer

logger = logging.getLogger(__name__)


class NetworkConsultantOrchestrator:
    """Own the collaborators and control flow for one Agent Network Consultant run."""

    # The server manifest keeps Consultant disabled. The explicit CLI loads its installed definition directly.
    CONSULTANT_NETWORK_FILE = os.path.join("registries", "agent_network_consultant.hocon")

    def __init__(self, context: ConsultantRunContext) -> None:
        """
        Build the cohesive services used by one isolated repair run.

        :param context: The validated target, options, session, and mutable run state.
        """
        self._context = context
        self._run_id = context.session().run_identifier()
        self._job_files = ConsultantJobFiles()
        self._fixture_runner = FixtureRunner(self._run_id)
        self._generated_tests_cache = GeneratedTestsCache(
            self._run_id,
            fixture_runner=self._fixture_runner,
            job_files=self._job_files,
        )
        self._scoring = ConsultantScoring(context.scores())
        if self._job_files.active():
            answerer = HeadlessClarificationAnswerer(self._job_files)
        else:
            answerer = TerminalClarificationAnswerer()
        self._workflow = ConsultantWorkflow(
            context.session(),
            answerer,
            self._job_files,
            self._fixture_runner,
        )

    @classmethod
    def run(cls: type["NetworkConsultantOrchestrator"], options: ConsultantOptions) -> None:
        """
        Validate options, prepare the target, and execute the requested workflow.

        :param options: The typed options selected by the caller.
        :raises ValueError: If the options do not identify a safe, fully described target.
        """
        normalized_hocon_file = ConsultantOptionValidator(options).validate()
        with TemporaryDirectory(prefix="agent_network_consultant_thinking_") as thinking_directory:
            cls.configure_logging()
            context = cls._initialize_context(
                options,
                normalized_hocon_file,
                thinking_directory,
            )
            if context is None:
                return
            orchestrator = cls(context)
            orchestrator._generate_tests(thinking_directory)
            orchestrator.execute()

    @staticmethod
    def run_serialized(serialized_run: str) -> None:
        """
        Run options received by the isolated Consultant process and clean up its owned traces.

        :param serialized_run: JSON containing the options and optional owned thinking directory.
        :raises ValueError: If the serialized payload does not contain an options mapping.
        """
        payload = json.loads(serialized_run)
        if not isinstance(payload, Mapping):
            raise ValueError("The serialized Consultant run must be a JSON object.")
        options_payload = payload.get("options")
        if not isinstance(options_payload, Mapping):
            raise ValueError("The serialized Consultant run is missing its options object.")
        thinking_directory = str(payload.get("owned_thinking_directory") or "") or None
        try:
            try:
                options = ConsultantOptions(**dict(options_payload))
            except TypeError as exc:
                raise ValueError(f"The serialized Consultant options are invalid: {exc}") from exc
            NetworkConsultantOrchestrator.run(options)
        finally:
            NetworkTestEnvironment.cleanup_owned_thinking_directory(thinking_directory)

    @staticmethod
    def run_payload_file(payload_path: str) -> None:
        """
        Read one private process-boundary payload and execute its serialized run.

        :param payload_path: The temporary JSON payload path supplied by Studio's command process.
        :raises OSError: If the payload cannot be read.
        :raises ValueError: If the payload content is malformed.
        """
        serialized_run = Path(payload_path).read_text(encoding="utf-8")
        NetworkConsultantOrchestrator.run_serialized(serialized_run)

    @staticmethod
    def configure_logging() -> None:
        """Configure Consultant-owned loggers without changing the process root logger."""
        logging.getLogger(__package__).setLevel(logging.INFO)

    @staticmethod
    def _initialize_context(
        options: ConsultantOptions,
        normalized_hocon_file: str | None,
        thinking_directory: str,
    ) -> ConsultantRunContext | None:
        """
        Open the Consultant and resolve or create the target network.

        :param options: The typed options selected by the caller.
        :param normalized_hocon_file: The validated existing-network HOCON reference.
        :param thinking_directory: The isolated directory owned by this Consultant run.
        :return: The initialized run context, or `None` when Designer did not produce a target.
        """
        consultant_session = ConsultantSession(
            NetworkConsultantOrchestrator.CONSULTANT_NETWORK_FILE,
            thinking_directory,
        )
        hocon_file = normalized_hocon_file or NetworkConsultantOrchestrator._design_network(
            options,
            thinking_directory,
        )
        if not hocon_file:
            return None
        network_name = os.path.splitext(hocon_file)[0]
        direction = options.direction or options.use_case or ""
        logger.info("Target network: %s (hocon_file=%s)", network_name, hocon_file)
        return ConsultantRunContext(
            options=options,
            session=consultant_session,
            target=ConsultantTarget(hocon_file, network_name, direction, os.path.join("registries", hocon_file)),
        )

    @staticmethod
    def _design_network(options: ConsultantOptions, thinking_directory: str) -> str | None:
        """
        Create a network through the existing Designer when no HOCON was supplied.

        :param options: The typed options selected by the caller.
        :param thinking_directory: The isolated directory owned by this Consultant run.
        :return: The generated network reference, or `None` when Designer did not return a name.
        """
        design_request = options.use_case or ""
        logger.info("Designing a new network...")
        designer_session = ConsultantSession("agent_network_designer", thinking_directory)
        designer_session.chat(design_request)
        network_name = designer_session.sly_data_value(AGENT_NETWORK_NAME)
        logger.info("Designer response received.")
        if not network_name:
            logger.error("Designer did not return an agent_network_name; cannot continue.")
            return None
        try:
            return ConsultantOptionValidator.normalize_hocon_reference(f"generated/{network_name}.hocon")
        except ValueError as exc:
            logger.error("Designer returned an unsafe agent_network_name: %s: %s", type(exc).__name__, exc)
            return None

    def execute(self) -> None:
        """Run the requested test-only or iterative repair mode."""
        if self._context.options().max_iterations == 0:
            self._run_without_fixes()
            return
        if not self._iterate():
            self._finish_max_iterations()

    def run_iteration(self) -> bool:
        """
        Run one test, scoring, and repair round.

        :return: Whether execution should stop after this round.
        """
        round_state = self._context.round_state()
        logger.info(
            "--- Iteration %d/%d: running tests ---",
            round_state.iteration(),
            self._context.options().max_iterations,
        )
        self._load_round_results()
        if self._report_infrastructure_errors(
            "Test infrastructure failed; no network or fixture changes were attempted:"
        ):
            return True
        self._record_round()
        self._log_round()
        if not round_state.has_failures() and self._handle_passing_round():
            return True
        self._update_scores()
        if self._widen_stale_subset():
            return True
        if self._stop_for_plateau():
            return True
        return self._consult_and_apply()

    def _generate_tests(self, thinking_directory: str) -> None:
        """
        Generate fixtures unless reusable fixtures already exist.

        :param thinking_directory: The isolated directory owned by this Consultant run.
        """
        options = self._context.options()
        network_name = self._context.target().network_name()
        fixtures_exist = self._workflow.has_existing_fixtures(network_name)
        if not options.force_generate and fixtures_exist:
            logger.info("Existing test fixtures found for %s; skipping ANTeGen.", network_name)
            return
        logger.info("Generating tests (ANTeGen, test_level=%s)...", options.test_level)
        testgen_session = ConsultantSession("agent_network_test_generator", thinking_directory)
        request = f"Generate test cases for {network_name} with {options.test_level} coverage"
        guidance = options.test_guidance.strip()
        if guidance:
            request += f". Focus on: {guidance}"
        testgen_session.chat(request)
        logger.info("ANTeGen response received.")

    def _run_without_fixes(self) -> None:
        """Run the selected fixture suite once without starting the repair loop."""
        selected_fixtures = self._fixture_selection()
        is_subset = bool(selected_fixtures)
        if is_subset:
            logger.info("Test run, no fix loop (subset of %s)...", selected_fixtures)
        else:
            logger.info("Test run, no fix loop...")
        results = self._fixture_runner.run_all_tests(
            self._context.target().network_name(),
            only_fixtures=selected_fixtures,
        )
        round_state = self._context.round_state()
        round_state.record_results(results, full_suite=not is_subset)
        has_infrastructure_errors = self._report_infrastructure_errors(
            "Test infrastructure failed; generated-test results were not cached:"
        )
        if not is_subset and not has_infrastructure_errors and self._job_files.active():
            self._generated_tests_cache.save(
                self._context.target().network_name(),
                self._context.target().hocon_path(),
                results,
            )
            self._context.progress_tracker().record(results, "generated", len(results))
        logger.info(
            "Result: %d/%d passing.",
            round_state.result_count() - round_state.failure_count(),
            round_state.result_count(),
        )

    def _iterate(self) -> bool:
        """
        Run repair rounds until one requests a terminal stop.

        :return: Whether a round requested a terminal stop.
        """
        fixture_selection = self._fixture_selection()
        total_fixture_count = (
            len(self._fixture_runner.fixture_paths(self._context.target().network_name()))
            if fixture_selection is not None
            else None
        )
        self._context.round_state().set_fixture_selection(fixture_selection, total_fixture_count)
        for iteration in range(1, self._context.options().max_iterations + 1):
            self._context.round_state().start_iteration(iteration)
            if self.run_iteration():
                return True
        return False

    def _load_round_results(self) -> None:
        """Load a valid cached baseline or execute the current fixture selection."""
        round_state = self._context.round_state()
        target = self._context.target()
        round_state.begin_round()
        cached_results = (
            self._generated_tests_cache.load(target.network_name(), target.hocon_path())
            if round_state.iteration() == 1 and round_state.fixture_selection() is None and self._job_files.active()
            else None
        )
        if cached_results is not None:
            logger.info("Reusing the Generate Tests baseline (network unchanged since) -- skipping re-test.")
            round_state.record_results(cached_results)
            self._fixture_runner.write_fixture_results(round_state.results())
            return
        fixture_runner = FixtureRunner(
            self._run_id,
            success_ratio_overrides=round_state.success_ratio_overrides(),
        )
        round_state.record_results(
            fixture_runner.run_all_tests(
                target.network_name(),
                only_fixtures=round_state.fixture_selection(),
            )
        )

    def _record_round(self) -> None:
        """Record a complete or incremental chart checkpoint."""
        round_state = self._context.round_state()
        if round_state.iteration() == 1:
            self._context.progress_tracker().record(
                round_state.results(),
                "before",
                round_state.total_fixture_count(),
            )
            return
        self._context.progress_tracker().record(
            round_state.results(),
            "iteration",
            round_state.total_fixture_count(),
            self._context.progress_tracker().next_improvement_iteration(),
        )

    def _log_round(self) -> None:
        """Report the current round result."""
        round_state = self._context.round_state()
        passed = round_state.result_count() - round_state.failure_count()
        subset_suffix = " (subset re-check)" if round_state.is_subset_check() else ""
        logger.info("%d/%d fixtures passing%s.", passed, round_state.result_count(), subset_suffix)

    def _handle_passing_round(self) -> bool:
        """
        Confirm a passing subset or finish a passing full suite without another edit.

        :return: Whether the run should stop.
        """
        round_state = self._context.round_state()
        if round_state.fixture_selection() is not None:
            logger.info("Subset re-check passed; running full suite once to confirm no regressions...")
            self._run_full_suite()
            if self._report_infrastructure_errors(
                "Full-suite confirmation could not complete because test infrastructure failed."
            ):
                return True
            if round_state.has_failures():
                if self._stop_if_good_enough():
                    self._record_final_progress()
                    return True
            else:
                self._record_final_progress()
                logger.info("All tests passing after full-suite confirmation. Stopping without further changes.")
                return True
        if round_state.has_failures():
            return False
        return self._handle_satisfied_network()

    def _handle_satisfied_network(self) -> bool:
        """
        Record an authoritative passing result without making another network edit.

        :return: Whether the run should stop.
        """
        round_state = self._context.round_state()
        logger.info("All tests passing. Network is satisfiable.")
        if round_state.has_success_ratio_overrides():
            logger.info("Re-scoring the full suite on the fixtures' own ratios before recording the final result.")
            self._run_full_suite()
            if self._report_infrastructure_errors(
                "Final confirmation could not complete because test infrastructure failed."
            ):
                return True
            if round_state.has_failures():
                logger.info("The authoritative full-suite re-score found failures; continuing repairs.")
                return False
        else:
            logger.info("Stopping without changes or a redundant verification run.")
        self._record_final_progress()
        return True

    def _widen_stale_subset(self) -> bool:
        """
        Replace a stalled subset estimate with an authoritative full-suite result.

        :return: Whether the authoritative result stops the run.
        """
        round_state = self._context.round_state()
        if not self._scoring.subset_plateau_reached(round_state.is_subset_check()):
            return False
        logger.info(
            "The failing subset has not improved for %d rounds; re-checking the whole suite.",
            self._scoring.PLATEAU_STRIKES,
        )
        self._run_full_suite()
        if self._report_infrastructure_errors(
            "Full-suite re-check could not complete because test infrastructure failed."
        ):
            return True
        self._update_scores()
        passed_count = round_state.passing_count()
        logger.info("Full suite: %d/%d passing.", passed_count, round_state.total_fixture_count())
        if self._stop_if_good_enough():
            self._record_final_progress()
            return True
        logger.info(
            "%d/%d passing is below %.0f%%; continuing against the full set of failures.",
            passed_count,
            round_state.total_fixture_count(),
            self._scoring.acceptance_percentage(),
        )
        return False

    def _run_full_suite(self) -> None:
        """Run the complete suite on declared fixture ratios and update current results."""
        round_state = self._context.round_state()
        round_state.clear_subset()
        self._scoring.clear_subset_history()
        round_state.record_results(
            self._fixture_runner.run_all_tests(self._context.target().network_name()),
            full_suite=True,
        )
        self._context.progress_tracker().synchronize_full_suite(round_state.results())

    def _report_infrastructure_errors(self, heading: str) -> bool:
        """
        Log infrastructure errors and return whether the round must stop.

        :param heading: The actionable heading shown before individual errors.
        :return: Whether infrastructure errors require a safe stop.
        """
        errors = self._context.round_state().infrastructure_errors()
        if not errors:
            return False
        logger.error(heading)
        for error in errors:
            safe_message = SensitiveDataRedactor.redact_text(str(error.get("message", "")).strip())
            logger.error("  - %s: %s", error.get("fixture"), safe_message)
        return True

    def _stop_if_good_enough(self) -> bool:
        """
        Report and accept a non-regressing full-suite result that clears the quality bar.

        :return: Whether the current complete-suite score can stop the run.
        """
        round_state = self._context.round_state()
        passed_count = round_state.passing_count()
        if not self._scoring.good_enough(passed_count, round_state.total_fixture_count()):
            return False
        score = self._scoring.round_score(round_state.results())
        if self._scoring.regresses_from_best(score):
            logger.info(
                "%d/%d passing meets the %.0f%% quality bar but regresses from an earlier full-suite result; "
                "continuing repairs.",
                passed_count,
                round_state.total_fixture_count(),
                self._scoring.acceptance_percentage(),
            )
            return False
        logger.info(
            "%d/%d passing (>= %.0f%%) on the full suite -- good enough, moving on.",
            passed_count,
            round_state.total_fixture_count(),
            self._scoring.acceptance_percentage(),
        )
        self._log_failures(logger.info, "  - still failing: %s: %s")
        return True

    def _log_failures(self, log_method: Callable[..., None], message_format: str) -> None:
        """
        Log each remaining fixture failure through the supplied logger method.

        :param log_method: The logger method used to report each failure.
        :param message_format: The lazy logging format for a fixture failure.
        """
        for failure in self._context.round_state().failures():
            safe_message = SensitiveDataRedactor.redact_text(str(failure.get("message", "")).strip())
            log_method(message_format, failure.get("fixture"), safe_message)

    def _update_scores(self) -> None:
        """Update independent subset or complete-suite plateau bookkeeping."""
        round_state = self._context.round_state()
        score = self._scoring.round_score(round_state.results())
        if round_state.is_subset_check():
            # A shrinking failure subset still represents cumulative complete-suite progress.
            score = (round_state.passing_count(), score[1])
        best_score = self._scoring.record(score, round_state.is_subset_check())
        if best_score is None:
            return
        logger.info(
            "Round score: %d/%d fixtures, %d/%d criteria (best so far %d/%d fixtures, %d criteria).",
            score[0],
            round_state.result_count(),
            score[1],
            self._scoring.criteria_total(round_state.results()),
            best_score[0],
            round_state.result_count(),
            best_score[1],
        )

    def _stop_for_plateau(self) -> bool:
        """
        Stop on the current verified state after a genuine complete-suite plateau.

        :return: Whether the complete-suite plateau threshold was reached.
        """
        if not self._scoring.plateau_reached():
            return False
        round_state = self._context.round_state()
        logger.warning(
            "No full-suite improvement for %d consecutive rounds; stopping after iteration %d with %d/%d fixtures "
            "still failing:",
            self._scoring.PLATEAU_STRIKES,
            round_state.iteration(),
            round_state.failure_count(),
            round_state.result_count(),
        )
        self._log_failures(logger.info, "  - %s: %s")
        logger.info("Stopping with the current tested network and fixture state; no files are rolled back.")
        self._record_final_progress()
        return True

    def _consult_and_apply(self) -> bool:
        """
        Ask the Consultant to repair current failures and process its control directives.

        :return: Whether the Consultant response requires a safe stop.
        """
        logger.info("Consulting Agent Network Consultant to fix failing agents' instructions...")
        fixture_paths: dict[str, str] = {}
        round_state = self._context.round_state()
        target = self._context.target()
        for failure in round_state.failures():
            fixture_paths.update({str(failure.get("fixture", "")): str(failure.get("path", ""))})
        try:
            response = self._workflow.consult(
                self._workflow.diagnosis_prompt(
                    round_state.failures(),
                    target.direction(),
                    round_state,
                    self._context.options().ungrounded,
                ),
                target.hocon_file(),
                fixture_paths,
            )
        except StuckPatchError as exc:
            safe_message = SensitiveDataRedactor.redact_text(str(exc))
            logger.error("Consultant patch failed: %s: %s", type(exc).__name__, safe_message)
            self._workflow.write_tool_issues([safe_message])
            return True
        except (OSError, RuntimeError) as exc:
            safe_message = SensitiveDataRedactor.redact_text(str(exc))
            logger.error("Consultant call failed: %s: %s", type(exc).__name__, safe_message)
            self._workflow.write_tool_issues([f"{type(exc).__name__}: {safe_message}"])
            return True
        logger.info("Consultant response received")
        response_protocol = ConsultantResponseProtocol(response)
        response_processor = ConsultantResponseProcessor(self._context, self._workflow, response_protocol)
        if response_processor.process():
            return True
        failed_fixtures: list[str] = []
        for failure in round_state.failures():
            failed_fixtures.append(str(failure.get("fixture", "")))
        round_state.set_fixture_selection(failed_fixtures)
        return False

    def _finish_max_iterations(self) -> None:
        """Verify and retain the final repair after exhausting the configured ceiling."""
        logger.warning(
            "Reached max repair iterations (%d); verifying the final repaired state. "
            "Rerun with a larger --max-iterations value to allow more repairs.",
            self._context.options().max_iterations,
        )
        self._run_full_suite()
        if self._report_infrastructure_errors(
            "Final confirmation could not complete because test infrastructure failed."
        ):
            return
        self._update_scores()
        self._record_final_progress()

    def _record_final_progress(self) -> None:
        """Record the active complete-suite result as the terminal chart checkpoint."""
        round_state = self._context.round_state()
        self._context.progress_tracker().record(
            round_state.results(),
            "after",
            round_state.total_fixture_count(),
        )

    def _fixture_selection(self) -> list[str] | None:
        """
        Return an isolated copy of the caller-selected fixture subset.

        :return: The selected fixture names, or `None` for the complete suite.
        """
        selected_fixtures = self._context.options().only_fixtures
        if selected_fixtures is None:
            return None
        return list(selected_fixtures)


if __name__ == "__main__":
    NetworkConsultantOrchestrator.run_payload_file(sys.argv[1])
