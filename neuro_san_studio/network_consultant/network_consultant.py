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
network_consultant -- same iterative test-and-fix loop as apps/network_improver, except the
fix step calls the specialized agent_network_consultant network instead of
agent_network_designer in modify mode. agent_network_designer is a general create/modify
tool that has to first figure out "is this structural or instructions-only"; consultant
skips that and goes straight from a failing-test report to per-agent instruction fixes.

The fixture-running engine lives next door in fixture_runner.py; this module is the loop that
drives it -- generate, test, diagnose, repair, re-test.

By default this runs in-process (--connection direct), no server needed. Pass --connection
http to instead talk to an already-running `ns run` server -- useful if you want this to share
a server with other clients, but NOT to watch the run in nsflow: nsflow's live view only shows
conversations started through its own UI/websocket, so a script hitting the neuro-san server's
plain chat API directly (this one) never appears there regardless of connection type.

Usage:
    python -m neuro_san_studio.network_consultant.network_consultant --use-case "A coffee shop order-status bot"
    python -m neuro_san_studio.network_consultant.network_consultant --hocon-file generated/coffee_shop.hocon \
        --direction "Preserve order lookup"
    python -m neuro_san_studio.network_consultant.network_consultant --hocon-file generated/coffee_shop.hocon \
        --direction "Preserve order lookup" --connection http
"""

import argparse
import logging
import os
import re
import shutil
import signal
import time
from collections.abc import Callable

from neuro_san_studio.coded_tools.agent_network_consultant.network_scratchpad import NetworkScratchpad
from neuro_san_studio.network_consultant.consultant_connection import ConsultantConnection
from neuro_san_studio.network_consultant.consultant_environment import ConsultantEnvironment
from neuro_san_studio.network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.network_consultant.consultant_workflow import ConsultantWorkflow
from neuro_san_studio.network_consultant.fixture_runner import IMPROVEMENT_THINKING_DIR
from neuro_san_studio.network_consultant.fixture_runner import NSFLOW_JOB_DIR
from neuro_san_studio.network_consultant.fixture_runner import NSFLOW_JOB_ID
from neuro_san_studio.network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.network_consultant.generated_tests_cache import GeneratedTestsCache
from neuro_san_studio.network_consultant.git_versioning import GIT_VERSIONS_BRANCH_PREFIX
from neuro_san_studio.network_consultant.git_versioning import GitVersioning
from neuro_san_studio.network_consultant.progress_tracker import ProgressTracker
from neuro_san_studio.network_consultant.stuck_patch_error import StuckPatchError

logger = logging.getLogger("network_consultant")

CONFIDENT_SUCCESS_RATIO = "3/3"
DEFAULT_MAX_ITERATIONS = 20
PLATEAU_STRIKES = 3
GOOD_ENOUGH_RATIO = 0.8
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080


class NetworkConsultant:
    """Run the Network Consultant command-line workflow."""

    @staticmethod
    def main() -> None:
        """Parse arguments, prepare the target, and execute the requested workflow."""
        ConsultantEnvironment.configure()
        NetworkConsultant.configure_logging()
        parser = NetworkConsultant.build_parser()
        args = NetworkConsultant.parse_arguments(parser)
        context = NetworkConsultant._initialize_context(args)
        if context is None:
            return
        NetworkConsultant._generate_tests(context)
        NetworkConsultant.execute(context)

    @staticmethod
    def configure_logging() -> None:
        """Configure concise application logging without enabling noisy framework loggers."""
        logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        logger.setLevel(logging.INFO)
        logging.getLogger("ServedManifestConfigFilter").setLevel(logging.ERROR)

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        """Build the Network Consultant command-line parser."""
        parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("--use-case", help="Use-case description for a brand new network.")
        parser.add_argument(
            "--hocon-file", help="Existing network hocon (relative to registries/) to iterate on instead."
        )
        parser.add_argument(
            "--direction",
            help="Intended behavior for an existing network; helps distinguish network defects from bad tests.",
        )
        parser.add_argument("--test-level", default="normal", choices=["minimum", "normal", "max"])
        parser.add_argument(
            "--test-guidance",
            default="",
            help="Free text steering what the test generator writes tests ABOUT (e.g. 'the vendor "
            "onboarding path'). Read only by the generator -- --direction is the consultant's "
            "statement of intended behavior and is a different thing.",
        )
        parser.add_argument(
            "--force-generate",
            action="store_true",
            help="Generate tests even when the network already has fixtures. Without this, "
            "generation is skipped whenever any fixture exists, which is right for the fix loop "
            "(it should reuse the suite, not pay to rebuild it) but makes an explicit 'generate' "
            "request silently do nothing. Regenerating overwrites same-named fixtures and adds "
            "new ones; it never deletes.",
        )
        parser.add_argument(
            "--ungrounded",
            default="stop",
            choices=["stop", "continue"],
            help="What to do when the consultant reports a criterion that no tool in the network can "
            "satisfy. 'stop' (default) ends the run so the missing data source can be wired up -- no "
            "instruction rewrite can ever make such a criterion pass. 'continue' tells the consultant "
            "to drop those criteria from their fixtures and keep improving everything else.",
        )
        parser.add_argument(
            "--only-fixtures",
            nargs="+",
            help="Run only these fixture basenames (e.g. 'foo.hocon') instead of the whole suite.",
        )
        parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
        parser.add_argument(
            "--success-ratio",
            default=CONFIDENT_SUCCESS_RATIO,
            help=f"Ratio (e.g. 'N/M') a fixture is bumped to once consultant is CONFIDENT its fix holds up "
            f"under repeated runs (default: {CONFIDENT_SUCCESS_RATIO}). Everything else stays cheap, and the "
            f"Before/After bars always score on each fixture's own ratio.",
        )
        parser.add_argument(
            "--connection",
            default="direct",
            choices=["http", "direct"],
            help="'direct' (default) runs the network in this process, no server needed. "
            "'http' talks to an already-running `ns run` server instead.",
        )
        parser.add_argument("--host", default=DEFAULT_HOST, help="`ns run` server host (--connection http only).")
        parser.add_argument(
            "--port", type=int, default=DEFAULT_PORT, help="`ns run` server port (--connection http only)."
        )
        parser.add_argument(
            "--git-versions",
            action="store_true",
            help="Commit the network hocon to a dedicated "
            f"{GIT_VERSIONS_BRANCH_PREFIX}/<network>/<run-id> branch and push it to origin at each "
            "meaningful test checkpoint (baseline, each retest, final confirmation), so every "
            "version tried is preserved in git history. Off by default -- this pushes to your "
            "'origin' remote repeatedly during the run, so only enable it when you actually want that.",
        )
        return parser

    @staticmethod
    def parse_arguments(parser: argparse.ArgumentParser) -> argparse.Namespace:
        """Parse and validate command-line arguments."""
        args = parser.parse_args()
        if not re.fullmatch(r"\d+/\d+", args.success_ratio):
            parser.error(f"--success-ratio must look like 'N/M' (e.g. '3/3'), got {args.success_ratio!r}.")
        if not args.use_case and not args.hocon_file:
            parser.error("Provide --use-case (to create a network) or --hocon-file (to iterate on an existing one).")
        if args.hocon_file and not args.direction:
            parser.error(
                "--direction is required with --hocon-file so test defects are not guessed from current behavior."
            )
        if args.hocon_file:
            try:
                args.hocon_file = ConsultantWorkflow.normalize_hocon_reference(args.hocon_file)
            except ValueError as exc:
                parser.error(str(exc))
        return args

    @staticmethod
    def _initialize_context(args: argparse.Namespace) -> ConsultantRunContext | None:
        """Open the consultant and resolve or create the target network."""
        consultant_session, consultant_thread = ConsultantSession.open_session(
            "agent_network_consultant", args.connection, args.host, args.port
        )
        hocon_file = args.hocon_file or NetworkConsultant._design_network(args)
        if not hocon_file:
            return None
        network_name = os.path.splitext(hocon_file)[0]
        direction = args.direction or args.use_case or ""
        logger.info("Target network: %s (hocon_file=%s)", network_name, hocon_file)
        NetworkScratchpad.clear_for_hocon_file(hocon_file)
        shutil.rmtree(IMPROVEMENT_THINKING_DIR, ignore_errors=True)
        return ConsultantRunContext(
            args=args,
            connection=ConsultantConnection(consultant_session, consultant_thread),
            target=ConsultantTarget(
                hocon_file=hocon_file,
                network_name=network_name,
                direction=direction,
                hocon_path=os.path.join("registries", hocon_file),
            ),
            resources=ConsultantResources(),
            scores=ConsultantScoreState(),
            round=ConsultantRoundState(),
            progress_tracker=ProgressTracker(),
        )

    @staticmethod
    def _design_network(args: argparse.Namespace) -> str | None:
        """Create a network through the existing Designer when no HOCON was supplied."""
        logger.info("Designing a new network (use_case=%r)...", args.use_case)
        designer_session, designer_thread = ConsultantSession.open_session(
            "agent_network_designer", args.connection, args.host, args.port
        )
        response, designer_thread = ConsultantSession.chat(designer_session, designer_thread, args.use_case)
        network_name = (designer_thread.get("sly_data") or {}).get("agent_network_name")
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
    def _generate_tests(context: ConsultantRunContext) -> None:
        """Generate fixtures unless reusable fixtures already exist."""
        args = context.args
        if not args.force_generate and ConsultantWorkflow.has_existing_fixtures(context.target.network_name):
            logger.info("Existing test fixtures found for %s; skipping ANTeGen.", context.target.network_name)
            return
        logger.info("Generating tests (ANTeGen, test_level=%s)...", args.test_level)
        testgen_session, testgen_thread = ConsultantSession.open_session(
            "agent_network_test_generator", args.connection, args.host, args.port
        )
        request = f"Generate test cases for {context.target.network_name} with {args.test_level} coverage"
        if args.test_guidance.strip():
            request += f". Focus on: {args.test_guidance.strip()}"
        logger.info("ANTeGen request: %s", request)
        response, _ = ConsultantSession.chat(testgen_session, testgen_thread, request)
        logger.info("ANTeGen response: %s", response)

    @staticmethod
    def execute(context: ConsultantRunContext) -> None:
        """Run the requested test or iterative repair mode with guaranteed cleanup."""
        ConsultantWorkflow.cleanup_state.update({"original_ratios": context.resources.original_ratios})
        signal.signal(signal.SIGTERM, ConsultantWorkflow.handle_sigterm)
        try:
            if context.args.max_iterations == 0:
                NetworkConsultant._run_without_fixes(context)
                return
            context.resources.git_worktree = NetworkConsultant._start_git_versioning(context)
            ConsultantWorkflow.cleanup_state.update({"git_worktree": context.resources.git_worktree})
            if not NetworkConsultant._iterate(context):
                NetworkConsultant._finish_max_iterations(context)
        finally:
            logger.info("Restoring original success_ratio values...")
            FixtureRunner.restore_success_ratios(context.resources.original_ratios)
            GitVersioning.stop_git_versioning(context.resources.git_worktree)

    @staticmethod
    def _run_without_fixes(context: ConsultantRunContext) -> None:
        """Run a headless fixture suite once when the fix loop is disabled."""
        if not (NSFLOW_JOB_ID and NSFLOW_JOB_DIR):
            return
        only_fixtures = context.args.only_fixtures
        is_subset = bool(only_fixtures)
        logger.info("Test run, no fix loop%s...", f" (subset of {only_fixtures})" if is_subset else "")
        results = FixtureRunner.run_all_tests(context.target.network_name, only_fixtures=only_fixtures)
        failures = [result for result in results if not result.get("passed")]
        if not is_subset:
            GeneratedTestsCache.save(context.target.network_name, context.target.hocon_path, results)
            context.progress_tracker.record(results, "generated", len(results))
        logger.info("Result: %d/%d passing.", len(results) - len(failures), len(results))

    @staticmethod
    def _start_git_versioning(context: ConsultantRunContext) -> str | None:
        """Start optional version snapshots for the target network."""
        if not context.args.git_versions:
            return None
        return GitVersioning.start_git_versioning(context.target.network_name, time.strftime("%Y%m%d-%H%M%S"))

    @staticmethod
    def _iterate(context: ConsultantRunContext) -> bool:
        """Run repair rounds until one requests a terminal stop."""
        for iteration in range(1, context.args.max_iterations + 1):
            context.round.iteration = iteration
            if NetworkConsultant.run_iteration(context):
                return True
        return False

    @staticmethod
    def run_iteration(context: ConsultantRunContext) -> bool:
        """Run one test, scoring, and repair round; return whether execution should stop."""
        logger.info("--- Iteration %d/%d: running tests ---", context.round.iteration, context.args.max_iterations)
        NetworkConsultant._load_round_results(context)
        if NetworkConsultant._report_infrastructure_errors(
            context, "Test infrastructure failed; no network or fixture changes were attempted:"
        ):
            return True
        NetworkConsultant._record_round(context)
        NetworkConsultant._log_and_commit_round(context)
        if not context.round.failures and NetworkConsultant._handle_passing_round(context):
            return True
        if NetworkConsultant._widen_stale_subset(context):
            return True
        NetworkConsultant._update_scores(context)
        if NetworkConsultant._stop_for_plateau(context):
            return True
        return NetworkConsultant._consult_and_apply(context)

    @staticmethod
    def _load_round_results(context: ConsultantRunContext) -> None:
        """Load a valid cached baseline or execute the current fixture selection."""
        context.round.is_subset_check = context.round.retest_only is not None
        cached_results = (
            GeneratedTestsCache.load(context.target.network_name, context.target.hocon_path)
            if context.round.iteration == 1 and NSFLOW_JOB_ID and NSFLOW_JOB_DIR
            else None
        )
        if cached_results is not None:
            logger.info("Reusing the Generate Tests baseline (network unchanged since) -- skipping re-test.")
            context.round.results = cached_results
            FixtureRunner.write_fixture_results(context.round.results)
        else:
            context.round.results = FixtureRunner.run_all_tests(
                context.target.network_name, only_fixtures=context.round.retest_only
            )
        if not context.round.is_subset_check:
            context.round.total_fixture_count = len(context.round.results)
        context.round.failures = [result for result in context.round.results if not result.get("passed")]

    @staticmethod
    def _record_round(context: ConsultantRunContext) -> None:
        """Record a complete or incremental chart checkpoint."""
        if context.round.iteration == 1:
            context.progress_tracker.record(context.round.results, "before", context.round.total_fixture_count)
            return
        context.round.improvement_iteration += 1
        context.progress_tracker.record(
            context.round.results,
            "iteration",
            context.round.total_fixture_count,
            context.round.improvement_iteration,
        )

    @staticmethod
    def _log_and_commit_round(context: ConsultantRunContext) -> None:
        """Report and optionally snapshot the current round result."""
        passed = len(context.round.results) - len(context.round.failures)
        subset_suffix = " (subset re-check)" if context.round.is_subset_check else ""
        logger.info("%d/%d fixtures passing%s.", passed, len(context.round.results), subset_suffix)
        label = "Before" if context.round.iteration == 1 else f"Iteration {context.round.iteration}"
        GitVersioning.commit_hocon_version(
            context.resources.git_worktree,
            context.target.hocon_file,
            f"{label}: {passed}/{len(context.round.results)} passing{subset_suffix}",
        )

    @staticmethod
    def _handle_passing_round(context: ConsultantRunContext) -> bool:
        """Confirm a passing subset or let the consultant act on a passing full suite."""
        if context.round.retest_only is not None:
            logger.info("Subset re-check passed; running full suite once to confirm no regressions...")
            NetworkConsultant._run_full_suite(context)
            if NetworkConsultant._report_infrastructure_errors(
                context, "Full-suite confirmation could not complete because test infrastructure failed."
            ):
                return True
            context.progress_tracker.record(context.round.results, "after", context.round.total_fixture_count)
            GitVersioning.commit_hocon_version(
                context.resources.git_worktree,
                context.target.hocon_file,
                f"Iteration {context.round.iteration} (full-suite confirmation): "
                f"{context.round.total_fixture_count - len(context.round.failures)}/"
                f"{context.round.total_fixture_count} passing",
            )
            if context.round.failures:
                if NetworkConsultant._stop_if_good_enough(context):
                    return True
                context.round.retest_only = None
                context.round.is_subset_check = False
        if context.round.failures:
            return False
        return NetworkConsultant._handle_satisfied_network(context)

    @staticmethod
    def _handle_satisfied_network(context: ConsultantRunContext) -> bool:
        """Run optional all-passing advice and verify any resulting edit."""
        logger.info("All tests passing. Network is satisfiable.")
        with open(context.target.hocon_path, encoding="utf-8") as before_file:
            hocon_before_consult = before_file.read()
        ConsultantWorkflow.consult_all_passing(
            context.connection.session,
            context.connection.thread,
            context.target.direction,
            context.round.total_fixture_count,
            context.target.hocon_file,
        )
        with open(context.target.hocon_path, encoding="utf-8") as after_file:
            hocon_after_consult = after_file.read()
        if hocon_after_consult == hocon_before_consult:
            return NetworkConsultant._finish_unchanged_satisfied_network(context)

        logger.info("Re-running full suite to verify that change didn't break anything...")
        NetworkConsultant._run_full_suite(context)
        if NetworkConsultant._report_infrastructure_errors(
            context, "Final confirmation could not complete because test infrastructure failed."
        ):
            return True
        context.progress_tracker.record(context.round.results, "after", context.round.total_fixture_count)
        GitVersioning.commit_hocon_version(
            context.resources.git_worktree,
            context.target.hocon_file,
            f"After: {context.round.total_fixture_count - len(context.round.failures)}/"
            f"{context.round.total_fixture_count} passing",
        )
        if not context.round.failures:
            logger.info("Still all passing after verification. Stopping.")
            return True
        if NetworkConsultant._stop_if_good_enough(context):
            return True
        logger.warning(
            "That change introduced %d regression(s); continuing to fix them instead of stopping.",
            len(context.round.failures),
        )
        context.round.retest_only = None
        context.round.is_subset_check = False
        return False

    @staticmethod
    def _finish_unchanged_satisfied_network(context: ConsultantRunContext) -> bool:
        """Record the final result without a redundant verification run when possible."""
        if context.resources.original_ratios:
            logger.info(
                "consultant made no changes; re-scoring the full suite on the fixtures' own ratios for the After bar."
            )
            NetworkConsultant._run_full_suite(context)
        else:
            logger.info("consultant made no changes; skipping the redundant re-verification run.")
        context.progress_tracker.record(context.round.results, "after", context.round.total_fixture_count)
        return True

    @staticmethod
    def _widen_stale_subset(context: ConsultantRunContext) -> bool:
        """Replace a stalled subset estimate with an authoritative full-suite result."""
        if not context.round.is_subset_check or context.scores.subset_stale_rounds < PLATEAU_STRIKES:
            return False
        logger.warning(
            "The failing subset hasn't improved for %d rounds; re-checking the whole suite.",
            PLATEAU_STRIKES,
        )
        NetworkConsultant._run_full_suite(context)
        if NetworkConsultant._report_infrastructure_errors(
            context, "Full-suite re-check could not complete because test infrastructure failed."
        ):
            return True
        passed_count = context.round.total_fixture_count - len(context.round.failures)
        context.progress_tracker.record(context.round.results, "after", context.round.total_fixture_count)
        GitVersioning.commit_hocon_version(
            context.resources.git_worktree,
            context.target.hocon_file,
            f"After: {passed_count}/{context.round.total_fixture_count} passing",
        )
        logger.info("Full suite: %d/%d passing.", passed_count, context.round.total_fixture_count)
        if NetworkConsultant._stop_if_good_enough(context):
            return True
        logger.warning(
            "%d/%d passing is below %.0f%%; continuing against the full set of failures.",
            passed_count,
            context.round.total_fixture_count,
            GOOD_ENOUGH_RATIO * 100,
        )
        context.round.retest_only = None
        context.round.is_subset_check = False
        context.scores.subset_best_score = None
        context.scores.subset_stale_rounds = 0
        return False

    @staticmethod
    def _run_full_suite(context: ConsultantRunContext) -> None:
        """Run the complete suite on its original fixture ratios and update current results."""
        context.round.results = FixtureRunner.run_real_ratio_suite(
            context.target.network_name, context.resources.original_ratios, context.args.success_ratio
        )
        context.round.total_fixture_count = len(context.round.results)
        context.round.failures = [result for result in context.round.results if not result.get("passed")]

    @staticmethod
    def _report_infrastructure_errors(context: ConsultantRunContext, heading: str) -> bool:
        """Log infrastructure errors and return whether the round must stop."""
        errors = [result for result in context.round.results if result.get("infrastructure_error")]
        if not errors:
            return False
        logger.error(heading)
        for error in errors:
            logger.error("  - %s: %s", error.get("fixture"), error.get("message"))
        return True

    @staticmethod
    def _stop_if_good_enough(context: ConsultantRunContext) -> bool:
        """Report and accept a full-suite result that meets the configured quality bar."""
        passed_count = context.round.total_fixture_count - len(context.round.failures)
        if not ConsultantScoring.good_enough(passed_count, context.round.total_fixture_count):
            return False
        print(
            f"[network_consultant] {passed_count}/{context.round.total_fixture_count} passing "
            f"(>= {GOOD_ENOUGH_RATIO:.0%}) on the full suite -- good enough, moving on."
        )
        NetworkConsultant._log_failures(context, logger.info, "  - still failing: %s: %s")
        return True

    @staticmethod
    def _log_failures(
        context: ConsultantRunContext,
        log_method: Callable[..., None],
        message_format: str,
    ) -> None:
        """Log each remaining fixture failure through the supplied logger method."""
        for failure in context.round.failures:
            log_method(
                message_format,
                failure.get("fixture"),
                str(failure.get("message", "")).strip(),
            )

    @staticmethod
    def _update_scores(context: ConsultantRunContext) -> None:
        """Update independent subset or full-suite plateau bookkeeping."""
        score = ConsultantScoring.round_score(context.round.results)
        if context.round.is_subset_check:
            if context.scores.subset_best_score is not None and score <= context.scores.subset_best_score:
                context.scores.subset_stale_rounds += 1
            else:
                context.scores.subset_stale_rounds = 0
            context.scores.subset_best_score = (
                score if context.scores.subset_best_score is None else max(score, context.scores.subset_best_score)
            )
            return

        improved = context.scores.best_score is None or score > context.scores.best_score
        context.scores.stale_rounds = 0 if improved else context.scores.stale_rounds + 1
        context.scores.best_score = (
            score if context.scores.best_score is None else max(score, context.scores.best_score)
        )
        logger.info(
            "Round score: %d/%d fixtures, %d/%d criteria (best so far %d/%d fixtures, %d criteria).",
            score[0],
            len(context.round.results),
            score[1],
            sum(result.get("criteria_total", 0) for result in context.round.results),
            context.scores.best_score[0],
            len(context.round.results),
            context.scores.best_score[1],
        )
        if improved:
            with open(context.target.hocon_path, encoding="utf-8") as best_file:
                context.scores.best_hocon_text = best_file.read()
            context.scores.best_hocon_iteration = context.round.iteration

    @staticmethod
    def _stop_for_plateau(context: ConsultantRunContext) -> bool:
        """Restore and measure the best full-suite version after a genuine plateau."""
        if context.scores.stale_rounds < PLATEAU_STRIKES:
            return False
        print(
            f"[network_consultant] Tried hard for {context.round.iteration} rounds, but this isn't working -- "
            f"{len(context.round.failures)}/{len(context.round.results)} fixtures still failing on the full suite. "
            "Giving up here."
        )
        logger.warning(
            "No full-suite improvement for %d consecutive rounds. Stopping with %d/%d still failing:",
            PLATEAU_STRIKES,
            len(context.round.failures),
            len(context.round.results),
        )
        NetworkConsultant._log_failures(context, logger.warning, "  - %s: %s")
        ConsultantScoring.restore_best_hocon(
            context.target.hocon_path, context.scores.best_hocon_text, context.scores.best_hocon_iteration
        )
        logger.info("Re-running the full suite on the restored best version for the final After bar...")
        NetworkConsultant._run_full_suite(context)
        if not NetworkConsultant._report_infrastructure_errors(
            context, "Final confirmation could not complete because test infrastructure failed."
        ):
            context.progress_tracker.record(context.round.results, "after", len(context.round.results))
        return True

    @staticmethod
    def _consult_and_apply(context: ConsultantRunContext) -> bool:
        """Ask the consultant to repair current failures and process its control signals."""
        logger.info("Consulting consultant to fix failing agents' instructions...")
        fixture_paths = {
            str(failure.get("fixture", "")): str(failure.get("path", "")) for failure in context.round.failures
        }
        try:
            response, context.connection.thread = ConsultantWorkflow.consult(
                context.connection.session,
                context.connection.thread,
                ConsultantWorkflow.diagnosis_prompt(
                    context.round.failures,
                    context.target.direction,
                    context.round.total_fixture_count,
                    context.round.is_subset_check,
                    context.args.ungrounded,
                ),
                context.target.hocon_file,
                fixture_paths,
            )
        except StuckPatchError as exc:
            logger.error(str(exc))
            ConsultantWorkflow.write_tool_issues([str(exc)])
            return True
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.error("consultant call failed: %s: %s", type(exc).__name__, exc)
            ConsultantWorkflow.write_tool_issues([f"{type(exc).__name__}: {exc}"])
            return True

        logger.info("consultant response: %s", response)
        GitVersioning.commit_hocon_version(
            context.resources.git_worktree,
            context.target.hocon_file,
            f"Change {context.round.iteration}: fixing {len(context.round.failures)} failing fixture(s)",
        )
        if NetworkConsultant._requires_structural_review(response):
            return True
        if NetworkConsultant._process_tool_issues(response):
            return True
        if NetworkConsultant._process_ungrounded(context, response):
            return True
        NetworkConsultant._apply_confident_fixes(context, response)
        context.round.retest_only = [str(failure.get("fixture", "")) for failure in context.round.failures]
        return False

    @staticmethod
    def _requires_structural_review(response: str) -> bool:
        """Return whether the consultant requested an out-of-scope structural change."""
        required = any(
            line.strip().startswith(ConsultantWorkflow.STRUCTURAL_CHANGE_PREFIX)
            for line in (response or "").splitlines()
        )
        if required:
            logger.warning("A structural change requires explicit Designer review. Stopping safely.")
        return required

    @staticmethod
    def _process_tool_issues(response: str) -> bool:
        """Report coded-tool failures that require human intervention."""
        tool_issues = ConsultantScoring.extract_prefixed(response, ConsultantWorkflow.TOOL_ISSUE_PREFIX)
        if not tool_issues:
            return False
        print(
            "[network_consultant] A required coded tool is broken -- this needs a human code fix, not "
            "an instructions/fixture change. Stopping so you can fix it and re-run:"
        )
        for issue in tool_issues:
            print(f"  ! {issue}")
        logger.warning("Tool issue(s) reported; stopping for a human fix: %s", tool_issues)
        ConsultantWorkflow.write_tool_issues(tool_issues)
        return True

    @staticmethod
    def _process_ungrounded(context: ConsultantRunContext, response: str) -> bool:
        """Report criteria that cannot be satisfied from the network's available data."""
        ungrounded = ConsultantScoring.extract_prefixed(response, ConsultantWorkflow.UNGROUNDED_PREFIX)
        if not ungrounded:
            return False
        print("[network_consultant] Some criteria ask for facts no tool in this network can supply:")
        for entry in ungrounded:
            print(f"  ? {entry}")
        logger.warning("Ungrounded criteria reported: %s", ungrounded)
        ConsultantWorkflow.write_ungrounded(ungrounded)
        if context.args.ungrounded != "stop":
            return False
        print(
            "[network_consultant] Stopping -- wire up the data source, or re-run with "
            "--ungrounded continue to drop those criteria and keep improving the rest."
        )
        return True

    @staticmethod
    def _apply_confident_fixes(context: ConsultantRunContext, response: str) -> None:
        """Temporarily raise verification ratios for fixes the consultant considers stable."""
        confident_fixtures = ConsultantScoring.extract_prefixed(response, ConsultantWorkflow.CONFIDENT_FIX_PREFIX)
        if not confident_fixtures:
            return
        originals = FixtureRunner.set_success_ratio_for_fixtures(
            context.target.network_name, confident_fixtures, context.args.success_ratio
        )
        context.resources.original_ratios.update(originals)
        logger.info(
            "consultant is confident in %d fix(es); bumped to %s for next round: %s",
            len(confident_fixtures),
            context.args.success_ratio,
            confident_fixtures,
        )

    @staticmethod
    def _finish_max_iterations(context: ConsultantRunContext) -> None:
        """Restore and measure the best version after exhausting the safety ceiling."""
        logger.warning("Reached max iterations (%d) without a full pass.", context.args.max_iterations)
        ConsultantScoring.restore_best_hocon(
            context.target.hocon_path, context.scores.best_hocon_text, context.scores.best_hocon_iteration
        )
        logger.info("Re-running the full suite on the restored best version for the final After bar...")
        NetworkConsultant._run_full_suite(context)
        if NetworkConsultant._report_infrastructure_errors(
            context, "Final confirmation could not complete because test infrastructure failed."
        ):
            return
        context.progress_tracker.record(context.round.results, "after", len(context.round.results))


if __name__ == "__main__":
    NetworkConsultant.main()
