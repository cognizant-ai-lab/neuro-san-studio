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
"""Reusable orchestration for the Network Consultant CLI."""

import logging
from pathlib import PurePosixPath
from typing import Any

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.parse_error_capture import ParseErrorCapture
from neuro_san_studio.agent_network_consultant.stuck_patch_error import StuckPatchError

logger = logging.getLogger("network_consultant")


class ConsultantWorkflow:
    """Coordinate Consultant conversations, prompts, and nsflow reporting."""

    @staticmethod
    def _ask_headless(question: str) -> str:
        """
        Write `question` to a file nsflow's backend surfaces in the UI, then block until a human answers it there
        (a file appears in the same directory), and return that answer.

        :param question: The clarification question to present.
        :return: The resulting text.
        """
        return ConsultantJobFiles.ask(question, ConsultantSession.headless_poll_interval())

    CLARIFICATION_PREFIX = "NEEDS_CLARIFICATION:"
    STRUCTURAL_CHANGE_PREFIX = "STRUCTURAL_CHANGE_REQUIRED:"
    CONFIDENT_FIX_PREFIX = "CONFIDENT_FIX:"
    TOOL_ISSUE_PREFIX = "TOOL_ISSUE:"
    # A criterion asking for a fact the network has no way to obtain, because a tool it depends on
    # returns nothing. Distinct from TOOL_ISSUE (that is an exception, this tool works fine and
    # politely has no data) and from AGENT FIX (no instruction rewrite can conjure the fact).
    UNGROUNDED_PREFIX = "UNGROUNDED:"

    @staticmethod
    def write_tool_issues(tool_issues: list[str]) -> None:
        """
        Persist reported tool issues to a file nsflow's backend surfaces in the UI (mirrors _ask_headless's
        question file) -- a no-op when not running as an nsflow job.

        :param tool_issues: The coded-tool issues to report.
        """
        ConsultantJobFiles.write("tool_issues.txt", "\n".join(tool_issues))

    @staticmethod
    def write_ungrounded(entries: list[str]) -> None:
        """
        Persist reported ungrounded criteria where nsflow's backend can surface them (mirrors write_tool_issues) --
        a no-op when not running as an nsflow job.

        :param entries: The ungrounded entries to report.
        """
        ConsultantJobFiles.write("ungrounded.txt", "\n".join(entries))

    @staticmethod
    def _guarded_chat(
        session: ConsultantSession,
        message: str,
        hocon_file: str,
        sly_data: dict[str, Any] | None = None,
    ) -> str:
        """
        ConsultantSession.chat(), but raises StuckPatchError if the parse-error signature repeats during the call
        instead of letting consultant retry a doomed tool call indefinitely.

        :param session: The active Consultant session.
        :param message: The message sent to the Consultant or stored in a verdict.
        :param hocon_file: The registries-relative HOCON file name.
        :param sly_data: The shared agent runtime data.
        :return: The response text from the Consultant.
        :raises StuckPatchError: Raised when the requested operation cannot complete.
        """
        capture = ParseErrorCapture()
        root_logger = logging.getLogger()
        root_logger.addHandler(capture)
        try:
            response = session.chat(message, sly_data=sly_data)
        finally:
            root_logger.removeHandler(capture)
        if capture.is_stuck():
            raise StuckPatchError(
                f"consultant is stuck patching {hocon_file} -- its source-preserving editor "
                "doesn't support this file's brace-less/'=' HOCON style. Skipping."
            )
        return response

    @staticmethod
    def structural_change_prefix() -> str:
        """
        Return the structural-review control prefix.

        :return: The structural-review prefix.
        """
        return ConsultantWorkflow.STRUCTURAL_CHANGE_PREFIX

    @staticmethod
    def tool_issue_prefix() -> str:
        """
        Return the coded-tool issue control prefix.

        :return: The coded-tool issue prefix.
        """
        return ConsultantWorkflow.TOOL_ISSUE_PREFIX

    @staticmethod
    def ungrounded_prefix() -> str:
        """
        Return the ungrounded-criterion control prefix.

        :return: The ungrounded-criterion prefix.
        """
        return ConsultantWorkflow.UNGROUNDED_PREFIX

    @staticmethod
    def confident_fix_prefix() -> str:
        """
        Return the confident-fix control prefix.

        :return: The confident-fix prefix.
        """
        return ConsultantWorkflow.CONFIDENT_FIX_PREFIX

    @staticmethod
    def normalize_hocon_reference(value: str) -> str:
        """
        Return a safe registries-relative HOCON reference for network and fixture lookup.

        :param value: The value to validate, redact, or return.
        :return: The resulting text.
        :raises ValueError: Raised when the requested operation cannot complete.
        """
        normalized = value.strip().replace("\\", "/")
        if normalized.startswith("registries/"):
            normalized = normalized[len("registries/") :]
        path = PurePosixPath(normalized)
        has_unsafe_part = False
        for part in path.parts:
            if part in {"", ".", ".."}:
                has_unsafe_part = True
                break
        if path.is_absolute() or path.suffix != ".hocon" or has_unsafe_part:
            raise ValueError("HOCON file must be a safe .hocon path relative to registries/.")
        return path.as_posix()

    @staticmethod
    def consult(
        session: ConsultantSession,
        message: str,
        hocon_file: str,
        fixture_paths_: dict[str, str],
    ) -> str:
        """
        Send one diagnosis/follow-up message to consultant, and keep answering any NEEDS_CLARIFICATION questions it
        comes back with (asking the actual person running this script) until it returns a turn with no more open
        questions.

        :param session: The active Consultant session.
        :param message: The message sent to the Consultant or stored in a verdict.
        :param hocon_file: The registries-relative HOCON file name.
        :param fixture_paths_: The failing fixture paths available to the Consultant.
        :return: The final response text after resolving any clarification questions.
        """
        logger.info("consult start: hocon_file=%s fixtures=%d", hocon_file, len(fixture_paths_))
        response = ConsultantWorkflow._guarded_chat(
            session,
            message,
            hocon_file,
            sly_data={"agent_network_hocon_file": hocon_file, "test_fixture_paths": fixture_paths_},
        )
        while True:
            questions = ConsultantScoring.extract_prefixed(response, ConsultantWorkflow.CLARIFICATION_PREFIX)
            if not questions:
                logger.info("consult done: no more open questions")
                return response

            logger.info("consult: %d clarification question(s) raised", len(questions))
            logger.info("The consultant needs clarification before it can continue:")
            answers = []
            for question in questions:
                if ConsultantJobFiles.active():
                    answer = ConsultantWorkflow._ask_headless(question)
                else:
                    logger.info("  ? %s", question)
                    answer = input("    your answer: ").strip()
                logger.info("consult: Q=%r A=%r", question, answer)
                answers.append(f"Q: {question}\nA: {answer}")

            follow_up = "This message answers the clarification question(s) you just asked:\n\n" + "\n\n".join(answers)
            response = ConsultantWorkflow._guarded_chat(session, follow_up, hocon_file)

    @staticmethod
    def consult_all_passing(
        session: ConsultantSession,
        direction: str,
        total_fixture_count: int,
        hocon_file: str,
    ) -> None:
        """
        Give consultant one chance to act on `direction` (e.g. token reduction) even when there's nothing failing
        to fix -- otherwise the front man is never invoked at all, and its "run token_reduction_advisor even with
        no failures" instruction never gets a chance to fire.

        :param session: The active Consultant session.
        :param direction: The user's requested improvement direction.
        :param total_fixture_count: The number of fixtures in the complete suite.
        :param hocon_file: The registries-relative HOCON file name.
        """
        if not direction:
            return
        try:
            response = ConsultantWorkflow.consult(
                session, ConsultantWorkflow.all_passing_prompt(direction, total_fixture_count), hocon_file, {}
            )
            logger.info("consultant response: %s", response)
        except StuckPatchError as exc:
            logger.error("Consultant patch failed: %s: %s", type(exc).__name__, exc)
            ConsultantWorkflow.write_tool_issues([str(exc)])
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.error("consultant call failed: %s: %s", type(exc).__name__, exc)

    @staticmethod
    def has_existing_fixtures(network_name: str) -> bool:
        """
        Whether tests/fixtures/<network_name>/ already has any generated fixture.

        :param network_name: The target network name.
        :return: Whether the requested condition is met.
        """
        return bool(FixtureRunner.fixture_paths(network_name))

    @staticmethod
    def diagnosis_prompt(
        failures: list[dict[str, Any]],
        direction: str,
        total_fixture_count: int,
        is_subset_check: bool,
        ungrounded: str = "stop",
    ) -> str:
        """
        Builds the failing-test report handed to consultant, including each fixture's current content -- needed
        since it may decide to correct the fixture itself, not just the network's instructions.

        :param failures: The failures value.
        :param direction: The user's requested improvement direction.
        :param total_fixture_count: How many fixtures exist in the network's full suite.
        :param is_subset_check: Whether this round only re-checked a subset (the fixtures still
        :param ungrounded: What the caller wants done about criteria no tool can satisfy --
        :return: The resulting text.
        """
        lines = ["User's intended behavior and approximate vision:", direction, ""]
        if is_subset_check:
            lines.append(
                f"This round only re-checked {len(failures)} of the {total_fixture_count} total fixtures in the "
                "suite (the ones still failing last round) -- not a full run. The following are failing:"
            )
        else:
            lines.append(f"The full suite of {total_fixture_count} fixtures was run. The following are failing:")
        lines.append("")
        for failure in failures:
            path = str(failure.get("path", ""))
            fixture_name = str(failure.get("fixture", ""))
            message = str(failure.get("message", ""))
            with open(path, encoding="utf-8") as fixture_file:
                fixture_content = fixture_file.read()
            lines.append(f"### Fixture file: {fixture_name}")
            lines.append(f"Failure: {message.strip()}")
            lines.append("Current fixture content:")
            lines.append(fixture_content.strip())
            lines.append("")
        lines.append(
            "If a criterion asks for a concrete fact the network cannot obtain -- because a tool it "
            "depends on returns NO DATA (an unwired retrieval agent, an empty index, a stub asking the "
            "caller to supply the source) -- that is UNGROUNDED, not an agent defect. Confirm it in the "
            "thinking trace by finding the tool's own reply and checking it carries no content. No "
            "instruction rewrite can ever satisfy such a criterion, so do NOT classify it as AGENT FIX; "
            "that is the trap that burns every remaining round rewriting agents that were never at fault. "
            "Report one line per criterion: `UNGROUNDED: <fixture>: <toolname>: <the exact criterion "
            "text>`, naming a tool that actually EXISTS in the network you were given -- copy it "
            "character-for-character, never invent a plausible-sounding retriever."
        )
        if ungrounded == "continue":
            lines.append(
                "For each UNGROUNDED criterion, ALSO call `fixture_expectation_fixer`, naming the exact "
                "criteria to remove and saying they are ungrounded, then carry on fixing anything else "
                "that fixture gets wrong."
            )
        else:
            lines.append(
                "Output the UNGROUNDED lines and change neither the network nor the fixture for them; "
                "the run stops so a human can wire up the missing data source."
            )
        lines.append(
            "Never satisfy an ungrounded criterion by having the network state the fact anyway -- a "
            "fabricated answer is worse than a failing test."
        )
        lines.append(
            "Next round re-checks whichever fixtures are still failing after your fix -- not the full suite. "
            "A full sweep still runs once before success is declared."
        )
        return "\n".join(lines)

    @staticmethod
    def all_passing_prompt(direction: str, total_fixture_count: int) -> str:
        """
        Report handed to consultant when every fixture already passes -- there's nothing to fix, but the user's
        direction (e.g. "reduce token usage") may still call for the token_reduction_advisor pass, which only ever
        runs if the front man is actually invoked.

        :param direction: The user's requested improvement direction.
        :param total_fixture_count: The number of fixtures in the complete suite.
        :return: The resulting text.
        """
        return (
            "User's intended behavior and approximate vision:\n"
            f"{direction}\n\n"
            f"All {total_fixture_count} fixtures in the test suite are currently passing. There are no failures to "
            "fix. If the direction above calls for something to still be done (e.g. reducing token usage), do that "
            "now; otherwise say plainly that there is nothing to do."
        )
