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
Orchestrate the Network Consultant's iterative test-and-fix workflow.

The fix step calls the specialized agent_network_consultant network. Consultant classifies each failure before it
changes anything: it can repair agent instructions, correct an invalid fixture expectation, delegate a structural
change to Agent Network Designer, or stop for a tool, infrastructure, or grounding problem.

The reusable fixture-running engine lives beside this module in fixture_runner.py; this module is
the consulting loop that drives it -- generate, test, diagnose, repair, re-test.

This runs in-process, so no Neuro SAN server is required.

Usage:
    python -m neuro_san_studio consultant --use-case "A coffee shop order-status bot"
    python -m neuro_san_studio consultant --hocon-file generated/coffee_shop.hocon --direction "Preserve lookup"
"""

import logging
import os
import shutil
import signal
import time
from collections.abc import Callable
from tempfile import TemporaryDirectory
from typing import Any

from coded_tools.agent_network_consultant.network_scratchpad import NetworkScratchpad
from neuro_san_studio.agent_network_consultant.consultant_cleanup import ConsultantCleanup
from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.agent_network_consultant.consultant_response_processor import ConsultantResponseProcessor
from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.agent_network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.generated_tests_cache import GeneratedTestsCache
from neuro_san_studio.agent_network_consultant.git_versioning import GitVersioning
from neuro_san_studio.agent_network_consultant.network_test_environment import NetworkTestEnvironment
from neuro_san_studio.agent_network_consultant.progress_tracker import ProgressTracker
from neuro_san_studio.agent_network_consultant.stuck_patch_error import StuckPatchError
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector

logger = logging.getLogger("network_consultant")

PLATEAU_STRIKES = 3
GOOD_ENOUGH_RATIO = 0.8


class NetworkConsultantOrchestrator:
    """Run the Network Consultant command-line workflow."""

    @staticmethod
    def run(options: ConsultantOptions) -> None:
        """
        Validate options, prepare the target, and execute the requested workflow.

        :param options: The typed options selected by the caller.
        :raises ValueError: If the options do not identify a safe, fully described target.
        """
        normalized_hocon_file = NetworkConsultantOrchestrator._validate_options(options)
        with NetworkTestEnvironment(), TemporaryDirectory(prefix="network_consultant_thinking_") as thinking_directory:
            NetworkConsultantOrchestrator.configure_logging()
            context = NetworkConsultantOrchestrator._initialize_context(
                options,
                normalized_hocon_file,
                thinking_directory,
            )
            if context is None:
                return
            NetworkConsultantOrchestrator._generate_tests(context, thinking_directory)
            NetworkConsultantOrchestrator.execute(context)

    @staticmethod
    def configure_logging() -> None:
        """
        Configure Consultant-owned loggers without changing the process root logger.
        """
        logger.setLevel(logging.INFO)
        logging.getLogger("ServedManifestConfigFilter").setLevel(logging.ERROR)

    @staticmethod
    def _clear_improvement_thinking(run_id: str) -> None:
        """
        Remove this run's prior improvement traces while reporting cleanup failures.

        :param run_id: The unique Consultant run identifier.
        """
        run_directory = ThinkingTraceCollector.run_directory(run_id)
        if not os.path.exists(run_directory):
            return
        try:
            shutil.rmtree(run_directory)
        except OSError as error:
            logger.warning("Could not clear improvement thinking traces from %s: %s", run_directory, error)

    @staticmethod
    def _validate_options(options: ConsultantOptions) -> str | None:
        """
        Validate and normalize options before any Consultant work begins.

        :param options: The typed options selected by the caller.
        :return: The normalized existing-network HOCON reference, when supplied.
        :raises ValueError: If an option is malformed or required target context is missing.
        """
        options.validate()
        if options.uses_git_versions():
            GitVersioning.configured_remote()
        hocon_file = options.existing_hocon_file()
        if not hocon_file:
            return None
        return ConsultantWorkflow.normalize_hocon_reference(hocon_file)

    @staticmethod
    def _initialize_context(
        options: ConsultantOptions,
        normalized_hocon_file: str | None,
        thinking_directory: str,
    ) -> ConsultantRunContext | None:
        """
        Open the consultant and resolve or create the target network.

        :param options: The typed options selected by the caller.
        :param normalized_hocon_file: The validated existing-network HOCON reference.
        :param thinking_directory: The isolated directory owned by this Consultant run.
        :return: The resulting value, or `None` when unavailable.
        """
        consultant_session = ConsultantSession("agent_network_consultant", thinking_directory)
        hocon_file = normalized_hocon_file or NetworkConsultantOrchestrator._design_network(
            options,
            thinking_directory,
        )
        if not hocon_file:
            return None
        network_name = os.path.splitext(hocon_file)[0]
        direction = options.target_direction()
        logger.info("Target network: %s (hocon_file=%s)", network_name, hocon_file)
        run_id = consultant_session.run_identifier()
        NetworkScratchpad.clear_for_hocon_file(hocon_file, run_id)
        NetworkConsultantOrchestrator._clear_improvement_thinking(run_id)
        return ConsultantRunContext(
            options,
            consultant_session,
            ConsultantTarget(hocon_file, network_name, direction, os.path.join("registries", hocon_file)),
            ConsultantResources(),
            ConsultantScoreState(),
            ConsultantRoundState(),
            ProgressTracker(),
        )

    @staticmethod
    def _design_network(options: ConsultantOptions, thinking_directory: str) -> str | None:
        """
        Create a network through the existing Designer when no HOCON was supplied.

        :param options: The typed options selected by the caller.
        :param thinking_directory: The isolated directory owned by this Consultant run.
        :return: The resulting value, or `None` when unavailable.
        """
        design_request = options.design_request()
        logger.info("Designing a new network (use_case=%r)...", design_request)
        designer_session = ConsultantSession("agent_network_designer", thinking_directory)
        response = designer_session.chat(design_request)
        network_name = designer_session.sly_data_value("agent_network_name")
        logger.info("Designer response: %s", response)
        if not network_name:
            logger.error(
                "Designer did not return an agent_network_name; cannot continue. Its response may explain why:\n%s",
                response,
            )
            return None
        try:
            return ConsultantWorkflow.normalize_hocon_reference(f"generated/{network_name}.hocon")
        except ValueError as exc:
            logger.error("Designer returned an unsafe agent_network_name (%r): %s", network_name, exc)
            return None

    @staticmethod
    def _generate_tests(context: ConsultantRunContext, thinking_directory: str) -> None:
        """
        Generate fixtures unless reusable fixtures already exist.

        :param context: The active Consultant run context.
        :param thinking_directory: The isolated directory owned by this Consultant run.
        """
        options = context.options()
        network_name = context.target().network_name()
        fixtures_exist = ConsultantWorkflow.has_existing_fixtures(network_name)
        if not options.should_generate_tests(fixtures_exist):
            logger.info("Existing test fixtures found for %s; skipping ANTeGen.", network_name)
            return
        logger.info("Generating tests (ANTeGen, test_level=%s)...", options.test_level_name())
        testgen_session = ConsultantSession("agent_network_test_generator", thinking_directory)
        request = options.test_generation_request(network_name)
        logger.info("ANTeGen request: %s", request)
        response = testgen_session.chat(request)
        logger.info("ANTeGen response: %s", response)

    @staticmethod
    def execute(context: ConsultantRunContext) -> None:
        """
        Run the requested test or iterative repair mode with guaranteed cleanup.

        :param context: The active Consultant run context.
        """
        ConsultantCleanup.configure()
        signal.signal(signal.SIGTERM, ConsultantCleanup.handle_sigterm)
        try:
            if context.options().fixes_disabled():
                NetworkConsultantOrchestrator._run_without_fixes(context)
                return
            context.resources().set_git_worktree(NetworkConsultantOrchestrator._start_git_versioning(context))
            ConsultantCleanup.remember_worktree(context.resources().git_worktree())
            if not NetworkConsultantOrchestrator._iterate(context):
                NetworkConsultantOrchestrator._finish_max_iterations(context)
        finally:
            GitVersioning.stop_git_versioning(context.resources().git_worktree())

    @staticmethod
    def _run_without_fixes(context: ConsultantRunContext) -> None:
        """
        Run the fixture suite once when the fix loop is disabled.

        :param context: The active Consultant run context.
        """
        only_fixtures = context.options().fixture_selection()
        is_subset = bool(only_fixtures)
        if is_subset:
            logger.info("Test run, no fix loop (subset of %s)...", only_fixtures)
        else:
            logger.info("Test run, no fix loop...")
        run_id = context.session().run_identifier()
        results = FixtureRunner.run_all_tests(
            context.target().network_name(),
            run_id,
            only_fixtures=only_fixtures,
        )
        failures: list[dict[str, Any]] = []
        for result in results:
            if not result.get("passed"):
                failures.append(result)
        if not is_subset and ConsultantJobFiles.active():
            GeneratedTestsCache.save(
                context.target().network_name(),
                context.target().hocon_path(),
                results,
                run_id,
            )
            context.progress_tracker().record(results, "generated", len(results))
        logger.info("Result: %d/%d passing.", len(results) - len(failures), len(results))

    @staticmethod
    def _start_git_versioning(context: ConsultantRunContext) -> str | None:
        """
        Start optional version snapshots for the target network.

        :param context: The active Consultant run context.
        :return: The resulting value, or `None` when unavailable.
        """
        if not context.options().uses_git_versions():
            return None
        return GitVersioning.start_git_versioning(context.target().network_name(), time.strftime("%Y%m%d-%H%M%S"))

    @staticmethod
    def _iterate(context: ConsultantRunContext) -> bool:
        """
        Run repair rounds until one requests a terminal stop.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        for iteration in context.options().iteration_numbers():
            context.round_state().start_iteration(iteration)
            if NetworkConsultantOrchestrator.run_iteration(context):
                return True
        return False

    @staticmethod
    def run_iteration(context: ConsultantRunContext) -> bool:
        """
        Run one test, scoring, and repair round; return whether execution should stop.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        logger.info(
            "--- Iteration %d/%d: running tests ---",
            context.round_state().iteration(),
            context.options().iteration_limit(),
        )
        NetworkConsultantOrchestrator._load_round_results(context)
        if NetworkConsultantOrchestrator._report_infrastructure_errors(
            context, "Test infrastructure failed; no network or fixture changes were attempted:"
        ):
            return True
        NetworkConsultantOrchestrator._record_round(context)
        NetworkConsultantOrchestrator._log_and_commit_round(context)
        if not context.round_state().has_failures() and NetworkConsultantOrchestrator._handle_passing_round(context):
            return True
        if NetworkConsultantOrchestrator._widen_stale_subset(context):
            return True
        NetworkConsultantOrchestrator._update_scores(context)
        if NetworkConsultantOrchestrator._stop_for_plateau(context):
            return True
        return NetworkConsultantOrchestrator._consult_and_apply(context)

    @staticmethod
    def _load_round_results(context: ConsultantRunContext) -> None:
        """
        Load a valid cached baseline or execute the current fixture selection.

        :param context: The active Consultant run context.
        """
        round_state = context.round_state()
        target = context.target()
        round_state.begin_round()
        cached_results = (
            GeneratedTestsCache.load(
                target.network_name(),
                target.hocon_path(),
                context.session().run_identifier(),
            )
            if round_state.iteration() == 1 and ConsultantJobFiles.active()
            else None
        )
        if cached_results is not None:
            logger.info("Reusing the Generate Tests baseline (network unchanged since) -- skipping re-test.")
            round_state.record_results(cached_results)
            FixtureRunner.write_fixture_results(round_state.results())
        else:
            round_state.record_results(
                FixtureRunner.run_all_tests(
                    target.network_name(),
                    context.session().run_identifier(),
                    only_fixtures=round_state.fixture_selection(),
                    success_ratio_overrides=context.resources().success_ratio_overrides(),
                )
            )

    @staticmethod
    def _record_round(context: ConsultantRunContext) -> None:
        """
        Record a complete or incremental chart checkpoint.

        :param context: The active Consultant run context.
        """
        round_state = context.round_state()
        if round_state.iteration() == 1:
            context.progress_tracker().record(round_state.results(), "before", round_state.total_fixture_count())
            return
        context.progress_tracker().record(
            round_state.results(),
            "iteration",
            round_state.total_fixture_count(),
            round_state.next_improvement_iteration(),
        )

    @staticmethod
    def _log_and_commit_round(context: ConsultantRunContext) -> None:
        """
        Report and optionally snapshot the current round result.

        :param context: The active Consultant run context.
        """
        round_state = context.round_state()
        passed = round_state.result_count() - round_state.failure_count()
        subset_suffix = " (subset re-check)" if round_state.is_subset_check() else ""
        logger.info("%d/%d fixtures passing%s.", passed, round_state.result_count(), subset_suffix)
        label = "Before" if round_state.iteration() == 1 else f"Iteration {round_state.iteration()}"
        GitVersioning.commit_hocon_version(
            context.resources().git_worktree(),
            context.target().hocon_file(),
            f"{label}: {passed}/{round_state.result_count()} passing{subset_suffix}",
        )

    @staticmethod
    def _handle_passing_round(context: ConsultantRunContext) -> bool:
        """
        Confirm a passing subset or let the consultant act on a passing full suite.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        round_state = context.round_state()
        if round_state.fixture_selection() is not None:
            logger.info("Subset re-check passed; running full suite once to confirm no regressions...")
            NetworkConsultantOrchestrator._run_full_suite(context)
            if NetworkConsultantOrchestrator._report_infrastructure_errors(
                context, "Full-suite confirmation could not complete because test infrastructure failed."
            ):
                return True
            context.progress_tracker().record(round_state.results(), "after", round_state.total_fixture_count())
            GitVersioning.commit_hocon_version(
                context.resources().git_worktree(),
                context.target().hocon_file(),
                f"Iteration {round_state.iteration()} (full-suite confirmation): "
                f"{round_state.passing_count()}/{round_state.total_fixture_count()} passing",
            )
            if round_state.has_failures():
                if NetworkConsultantOrchestrator._stop_if_good_enough(context):
                    return True
                round_state.clear_subset()
        if round_state.has_failures():
            return False
        return NetworkConsultantOrchestrator._handle_satisfied_network(context)

    @staticmethod
    def _handle_satisfied_network(context: ConsultantRunContext) -> bool:
        """
        Run optional all-passing advice and verify any resulting edit.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        target = context.target()
        round_state = context.round_state()
        logger.info("All tests passing. Network is satisfiable.")
        with open(target.hocon_path(), encoding="utf-8") as before_file:
            hocon_before_consult = before_file.read()
        ConsultantWorkflow.consult_all_passing(
            context.session(),
            target.direction(),
            round_state.total_fixture_count(),
            target.hocon_file(),
        )
        with open(target.hocon_path(), encoding="utf-8") as after_file:
            hocon_after_consult = after_file.read()
        if hocon_after_consult == hocon_before_consult:
            return NetworkConsultantOrchestrator._finish_unchanged_satisfied_network(context)

        logger.info("Re-running full suite to verify that change didn't break anything...")
        NetworkConsultantOrchestrator._run_full_suite(context)
        if NetworkConsultantOrchestrator._report_infrastructure_errors(
            context, "Final confirmation could not complete because test infrastructure failed."
        ):
            return True
        context.progress_tracker().record(round_state.results(), "after", round_state.total_fixture_count())
        GitVersioning.commit_hocon_version(
            context.resources().git_worktree(),
            target.hocon_file(),
            f"After: {round_state.passing_count()}/{round_state.total_fixture_count()} passing",
        )
        if not round_state.has_failures():
            logger.info("Still all passing after verification. Stopping.")
            return True
        if NetworkConsultantOrchestrator._stop_if_good_enough(context):
            return True
        logger.warning(
            "That change introduced %d regression(s); continuing to fix them instead of stopping.",
            round_state.failure_count(),
        )
        round_state.clear_subset()
        return False

    @staticmethod
    def _finish_unchanged_satisfied_network(context: ConsultantRunContext) -> bool:
        """
        Record the final result without a redundant verification run when possible.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        if context.resources().has_success_ratio_overrides():
            logger.info(
                "consultant made no changes; re-scoring the full suite on the fixtures' own ratios for the After bar."
            )
            NetworkConsultantOrchestrator._run_full_suite(context)
        else:
            logger.info("consultant made no changes; skipping the redundant re-verification run.")
        round_state = context.round_state()
        context.progress_tracker().record(round_state.results(), "after", round_state.total_fixture_count())
        return True

    @staticmethod
    def _widen_stale_subset(context: ConsultantRunContext) -> bool:
        """
        Replace a stalled subset estimate with an authoritative full-suite result.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        round_state = context.round_state()
        if not context.scores().subset_plateau_reached(PLATEAU_STRIKES, round_state.is_subset_check()):
            return False
        logger.warning(
            "The failing subset hasn't improved for %d rounds; re-checking the whole suite.",
            PLATEAU_STRIKES,
        )
        NetworkConsultantOrchestrator._run_full_suite(context)
        if NetworkConsultantOrchestrator._report_infrastructure_errors(
            context, "Full-suite re-check could not complete because test infrastructure failed."
        ):
            return True
        passed_count = round_state.passing_count()
        context.progress_tracker().record(round_state.results(), "after", round_state.total_fixture_count())
        GitVersioning.commit_hocon_version(
            context.resources().git_worktree(),
            context.target().hocon_file(),
            f"After: {passed_count}/{round_state.total_fixture_count()} passing",
        )
        logger.info("Full suite: %d/%d passing.", passed_count, round_state.total_fixture_count())
        if NetworkConsultantOrchestrator._stop_if_good_enough(context):
            return True
        logger.warning(
            "%d/%d passing is below %.0f%%; continuing against the full set of failures.",
            passed_count,
            round_state.total_fixture_count(),
            GOOD_ENOUGH_RATIO * 100,
        )
        round_state.clear_subset()
        context.scores().reset_subset()
        return False

    @staticmethod
    def _run_full_suite(context: ConsultantRunContext) -> None:
        """
        Run the complete suite on its declared fixture ratios and update current results.

        :param context: The active Consultant run context.
        """
        context.round_state().record_results(
            FixtureRunner.run_all_tests(
                context.target().network_name(),
                context.session().run_identifier(),
            ),
            full_suite=True,
        )

    @staticmethod
    def _report_infrastructure_errors(context: ConsultantRunContext, heading: str) -> bool:
        """
        Log infrastructure errors and return whether the round must stop.

        :param context: The active Consultant run context.
        :param heading: The heading value.
        :return: Whether the requested condition is met.
        """
        errors = context.round_state().infrastructure_errors()
        if not errors:
            return False
        logger.error(heading)
        for error in errors:
            safe_message = FixtureRunner.redact_sensitive_text(str(error.get("message", "")).strip())
            logger.error("  - %s: %s", error.get("fixture"), safe_message)
        return True

    @staticmethod
    def _stop_if_good_enough(context: ConsultantRunContext) -> bool:
        """
        Report and accept a full-suite result that meets the configured quality bar.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        round_state = context.round_state()
        passed_count = round_state.passing_count()
        if not ConsultantScoring.good_enough(passed_count, round_state.total_fixture_count()):
            return False
        logger.info(
            "%d/%d passing (>= %.0f%%) on the full suite -- good enough, moving on.",
            passed_count,
            round_state.total_fixture_count(),
            GOOD_ENOUGH_RATIO * 100,
        )
        NetworkConsultantOrchestrator._log_failures(context, logger.info, "  - still failing: %s: %s")
        return True

    @staticmethod
    def _log_failures(
        context: ConsultantRunContext,
        log_method: Callable[..., None],
        message_format: str,
    ) -> None:
        """
        Log each remaining fixture failure through the supplied logger method.

        :param context: The active Consultant run context.
        :param log_method: The logger method used to report each failure.
        :param message_format: The lazy logging format for a fixture failure.
        """
        for failure in context.round_state().failures():
            safe_message = FixtureRunner.redact_sensitive_text(str(failure.get("message", "")).strip())
            log_method(
                message_format,
                failure.get("fixture"),
                safe_message,
            )

    @staticmethod
    def _update_scores(context: ConsultantRunContext) -> None:
        """
        Update independent subset or full-suite plateau bookkeeping.

        :param context: The active Consultant run context.
        """
        round_state = context.round_state()
        score = ConsultantScoring.round_score(round_state.results())
        score_update = context.scores().update(score, round_state.is_subset_check())
        if score_update is None:
            return
        improved, best_score = score_update
        logger.info(
            "Round score: %d/%d fixtures, %d/%d criteria (best so far %d/%d fixtures, %d criteria).",
            score[0],
            round_state.result_count(),
            score[1],
            NetworkConsultantOrchestrator._criteria_total(round_state.results()),
            best_score[0],
            round_state.result_count(),
            best_score[1],
        )
        if improved:
            with open(context.target().hocon_path(), encoding="utf-8") as best_file:
                context.scores().remember_best_hocon(best_file.read(), round_state.iteration())

    @staticmethod
    def _stop_for_plateau(context: ConsultantRunContext) -> bool:
        """
        Restore and measure the best full-suite version after a genuine plateau.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        round_state = context.round_state()
        if not context.scores().plateau_reached(PLATEAU_STRIKES):
            return False
        logger.warning(
            "Tried hard for %d rounds, but this isn't working -- %d/%d fixtures still failing on the full suite. "
            "Giving up here.",
            round_state.iteration(),
            round_state.failure_count(),
            round_state.result_count(),
        )
        logger.warning(
            "No full-suite improvement for %d consecutive rounds. Stopping with %d/%d still failing:",
            PLATEAU_STRIKES,
            round_state.failure_count(),
            round_state.result_count(),
        )
        NetworkConsultantOrchestrator._log_failures(context, logger.warning, "  - %s: %s")
        best_hocon_text, best_hocon_iteration = context.scores().best_hocon()
        ConsultantScoring.restore_best_hocon(context.target().hocon_path(), best_hocon_text, best_hocon_iteration)
        logger.info("Re-running the full suite on the restored best version for the final After bar...")
        NetworkConsultantOrchestrator._run_full_suite(context)
        if not NetworkConsultantOrchestrator._report_infrastructure_errors(
            context, "Final confirmation could not complete because test infrastructure failed."
        ):
            context.progress_tracker().record(round_state.results(), "after", round_state.result_count())
        return True

    @staticmethod
    def _consult_and_apply(context: ConsultantRunContext) -> bool:
        """
        Ask the consultant to repair current failures and process its control signals.

        :param context: The active Consultant run context.
        :return: Whether the requested condition is met.
        """
        logger.info("Consulting consultant to fix failing agents' instructions...")
        fixture_paths: dict[str, str] = {}
        round_state = context.round_state()
        target = context.target()
        for failure in round_state.failures():
            fixture_paths.update({str(failure.get("fixture", "")): str(failure.get("path", ""))})
        try:
            response = ConsultantWorkflow.consult(
                context.session(),
                ConsultantWorkflow.diagnosis_prompt(
                    round_state.failures(),
                    target.direction(),
                    round_state.total_fixture_count(),
                    round_state.is_subset_check(),
                    context.options().ungrounded_policy(),
                ),
                target.hocon_file(),
                fixture_paths,
            )
        except StuckPatchError as exc:
            logger.error("Consultant patch failed: %s: %s", type(exc).__name__, exc)
            ConsultantWorkflow.write_tool_issues([str(exc)])
            return True
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.error("consultant call failed: %s: %s", type(exc).__name__, exc)
            ConsultantWorkflow.write_tool_issues([f"{type(exc).__name__}: {exc}"])
            return True

        logger.info("consultant response: %s", response)
        GitVersioning.commit_hocon_version(
            context.resources().git_worktree(),
            target.hocon_file(),
            f"Change {round_state.iteration()}: fixing {round_state.failure_count()} failing fixture(s)",
        )
        if ConsultantResponseProcessor.process(context, response):
            return True
        round_state.schedule_failure_retests()
        return False

    @staticmethod
    def _finish_max_iterations(context: ConsultantRunContext) -> None:
        """
        Restore and measure the best version after exhausting the safety ceiling.

        :param context: The active Consultant run context.
        """
        logger.warning(
            "Reached max iterations (%d) without a full pass.",
            context.options().iteration_limit(),
        )
        best_hocon_text, best_hocon_iteration = context.scores().best_hocon()
        ConsultantScoring.restore_best_hocon(context.target().hocon_path(), best_hocon_text, best_hocon_iteration)
        logger.info("Re-running the full suite on the restored best version for the final After bar...")
        NetworkConsultantOrchestrator._run_full_suite(context)
        if NetworkConsultantOrchestrator._report_infrastructure_errors(
            context, "Final confirmation could not complete because test infrastructure failed."
        ):
            return
        round_state = context.round_state()
        context.progress_tracker().record(round_state.results(), "after", round_state.result_count())

    @staticmethod
    def _criteria_total(results: list[dict[str, Any]]) -> int:
        """
        Return the total number of evaluated criteria in a fixture result set.

        :param results: The fixture result records.
        :return: The resulting value.
        """
        criteria_total = 0
        for result in results:
            criteria_total += result.get("criteria_total", 0)
        return criteria_total
