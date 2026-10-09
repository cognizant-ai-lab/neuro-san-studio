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
"""Reusable orchestration for Agent Network Consultant conversations."""

import logging
from numbers import Integral
from typing import Any
from typing import Literal

from neuro_san_studio.agent_network_consultant.consultant_clarification_answerer import ConsultantClarificationAnswerer
from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.consultant_response_protocol import ConsultantResponseProtocol
from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.stuck_patch_error import StuckPatchError

logger = logging.getLogger(__name__)


class ConsultantWorkflow:
    """Coordinate one Agent Network Consultant session, clarification transport, and fixture runtime."""

    # Three consecutive source-edit failures allow transient retries before the workflow stops safely.
    PERSISTENCE_FAILURE_THRESHOLD = 3
    # Three answered rounds bound runs when the model repeatedly asks for clarification.
    MAX_CLARIFICATION_ROUNDS = 3

    def __init__(
        self,
        session: ConsultantSession,
        answerer: ConsultantClarificationAnswerer,
        job_files: ConsultantJobFiles,
        fixture_runner: FixtureRunner,
    ) -> None:
        """
        Store the collaborators used throughout one Agent Network Consultant conversation.

        :param session: The active Agent Network Consultant session.
        :param answerer: The selected terminal or nsflow clarification transport.
        :param job_files: The optional nsflow job-file interface.
        :param fixture_runner: The fixture runtime for the target project.
        """
        self._session = session
        self._answerer = answerer
        self._job_files = job_files
        self._fixture_runner = fixture_runner

    def write_tool_issues(self, tool_issues: list[str]) -> None:
        """
        Persist coded-tool issues where nsflow can surface them.

        :param tool_issues: The redacted coded-tool issues to report.
        """
        self._job_files.write("tool_issues.txt", "\n".join(tool_issues))

    def write_ungrounded(self, entries: list[str]) -> None:
        """
        Persist ungrounded criteria where nsflow can surface them.

        :param entries: The redacted ungrounded entries to report.
        """
        self._job_files.write("ungrounded.txt", "\n".join(entries))

    def consult(self, message: str, hocon_file: str, fixture_paths: dict[str, str]) -> str:
        """
        Continue one Agent Network Consultant conversation until all clarification questions are answered.

        :param message: The diagnosis or follow-up message sent to Agent Network Consultant.
        :param hocon_file: The registries-relative HOCON file name.
        :param fixture_paths: The failing fixture paths available to Agent Network Consultant.
        :return: The final response after resolving clarification questions.
        :raises RuntimeError: If clarification cannot finish within the allowed rounds.
        :raises TimeoutError: If the selected clarification transport reaches its deadline.
        :raises StuckPatchError: If source-preserving persistence repeatedly fails.
        """
        logger.info("consult start: hocon_file=%s fixtures=%d", hocon_file, len(fixture_paths))
        response = self._guarded_chat(
            message,
            hocon_file,
            sly_data={
                ConsultantState.AGENT_NETWORK_HOCON_FILE: hocon_file,
                ConsultantState.TEST_FIXTURE_PATHS: fixture_paths,
            },
        )
        clarification_round = 0
        response_protocol = ConsultantResponseProtocol(response)
        questions = response_protocol.values(ConsultantResponseProtocol.CLARIFICATION_PREFIX)
        while questions:
            if clarification_round >= self.MAX_CLARIFICATION_ROUNDS:
                raise RuntimeError(
                    "Agent Network Consultant exceeded the maximum number of clarification rounds "
                    f"({self.MAX_CLARIFICATION_ROUNDS})."
                )
            clarification_round += 1
            logger.info("consult: %d clarification question(s) raised", len(questions))
            answers = self._answerer.answer_all(questions)
            logger.info("consult: %d clarification answer(s) received", len(answers))
            answered_questions: list[str] = []
            for index, question in enumerate(questions):
                answered_questions.append(f"Q: {question}\nA: {answers[index]}")
            follow_up = "This message answers the clarification question(s) you just asked:\n\n" + "\n\n".join(
                answered_questions
            )
            response = self._guarded_chat(follow_up, hocon_file)
            response_protocol = ConsultantResponseProtocol(response)
            questions = response_protocol.values(ConsultantResponseProtocol.CLARIFICATION_PREFIX)
        logger.info("consult done: no more open questions")
        return response

    def has_existing_fixtures(self, network_name: str) -> bool:
        """
        Return whether the target network already has generated fixtures.

        :param network_name: The target network name.
        :return: Whether at least one matching fixture exists.
        """
        return bool(self._fixture_runner.fixture_paths(network_name))

    def diagnosis_prompt(
        self,
        failures: list[dict[str, Any]],
        direction: str,
        round_state: ConsultantRoundState,
        ungrounded: Literal["stop", "continue"] = "stop",
    ) -> str:
        """
        Build the failure report and repair constraints sent to Agent Network Consultant.

        :param failures: The current fixture failures.
        :param direction: The user's requested improvement direction.
        :param round_state: The active fixture round and complete-suite coverage.
        :param ungrounded: The selected policy for criteria no available tool can satisfy.
        :return: The complete diagnosis prompt.
        """
        lines = ["User's intended behavior and approximate vision:", direction, ""]
        lines.append(self._fixture_coverage(round_state))
        lines.append("")
        for failure in failures:
            lines.extend(self._fixture_failure_context(failure))
        lines.extend(self._ungrounded_guidance(ungrounded))
        return "\n".join(lines)

    @staticmethod
    def _fixture_coverage(round_state: ConsultantRoundState) -> str:
        """
        Describe whether the current result covers a selected subset, a re-check, or the complete suite.

        :param round_state: The active fixture round and complete-suite coverage.
        :return: The fixture-coverage statement for the diagnosis prompt.
        """
        total_fixture_count = round_state.total_fixture_count()
        round_fixture_count = round_state.result_count()
        is_subset_check = round_state.is_subset_check()
        is_initial_selection = round_state.iteration() == 1 and is_subset_check
        if is_initial_selection:
            return (
                f"The user selected {round_fixture_count} of the {total_fixture_count} total fixtures for this first "
                "round, so this is not a full-suite result. The following selected fixtures are failing:"
            )
        if is_subset_check:
            return (
                f"This round only re-checked {round_fixture_count} of the {total_fixture_count} total fixtures in the "
                "suite (the ones still failing last round) -- not a full run. The following are failing:"
            )
        return f"The full suite of {total_fixture_count} fixtures was run. The following are failing:"

    @staticmethod
    def _fixture_failure_context(failure: dict[str, Any]) -> list[str]:
        """
        Read one failing fixture and format the context needed for diagnosis.

        :param failure: The fixture failure record.
        :return: The formatted failure and current fixture content.
        :raises OSError: If the referenced fixture cannot be read.
        """
        path = str(failure.get("path", ""))
        fixture_name = str(failure.get("fixture", ""))
        failure_message = str(failure.get("message", ""))
        with open(path, encoding="utf-8") as fixture_file:
            fixture_content = fixture_file.read()
        return [
            f"### Fixture file: {fixture_name}",
            f"Failure: {failure_message.strip()}",
            "Current fixture content:",
            fixture_content.strip(),
            "",
        ]

    @staticmethod
    def _ungrounded_guidance(ungrounded: Literal["stop", "continue"]) -> list[str]:
        """
        Build the diagnosis rules for criteria that no available tool can satisfy.

        :param ungrounded: The selected policy for criteria no available tool can satisfy.
        :return: The ungrounded-criteria guidance for the diagnosis prompt.
        """
        lines = [
            "If a criterion asks for a concrete fact the network cannot obtain -- because a tool it depends on "
            "returns NO DATA (an unwired retrieval agent, an empty index, a stub asking the caller to supply the "
            "source) -- that is UNGROUNDED, not an agent defect. Confirm it in the thinking trace by finding the "
            "tool's own reply and checking it carries no content. No instruction rewrite can ever satisfy such a "
            "criterion, so do NOT classify it as AGENT FIX; that is the trap that burns every remaining round "
            "rewriting agents that were never at fault. Report one line per criterion: `UNGROUNDED: <fixture>: "
            "<toolname>: <the exact criterion text>`, naming a tool that actually EXISTS in the network you were "
            "given -- copy it character-for-character, never invent a plausible-sounding retriever."
        ]
        if ungrounded == "continue":
            lines.append(
                "For each UNGROUNDED criterion, ALSO call `fixture_expectation_fixer`, naming the exact criteria to "
                "remove and saying they are ungrounded, then carry on fixing anything else that fixture gets wrong."
            )
        else:
            lines.append(
                "Output the UNGROUNDED lines and change neither the network nor the fixture for them; the run stops "
                "so a human can wire up the missing data source."
            )
        lines.append(
            "Never satisfy an ungrounded criterion by having the network state the fact anyway -- a fabricated "
            "answer is worse than a failing test."
        )
        lines.append(
            "Next round re-checks whichever fixtures are still failing after your fix -- not the full suite. "
            "A full sweep still runs once before success is declared."
        )
        return lines

    def _guarded_chat(
        self,
        message: str,
        hocon_file: str,
        sly_data: dict[str, Any] | None = None,
    ) -> str:
        """
        Run one chat and stop after repeated structured source-persistence failures.

        :param message: The message sent to Agent Network Consultant.
        :param hocon_file: The registries-relative HOCON file name.
        :param sly_data: The shared agent runtime data.
        :return: The response text from Agent Network Consultant.
        :raises StuckPatchError: If source-preserving persistence repeatedly fails.
        :raises TypeError: If middleware returns a noninteger persistence failure count.
        """
        chat_sly_data: dict[str, Any] = dict(sly_data or {})
        chat_sly_data.update({ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT: 0})
        response = self._session.chat(message, sly_data=chat_sly_data)
        failure_count_value: Any = self._session.sly_data_value(
            ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT
        )
        if failure_count_value is None:
            failure_count = 0
        # bool is an Integral in Python, but framework flags must never become numeric failure counts.
        elif (
            failure_count_value is not True
            and failure_count_value is not False
            and isinstance(
                failure_count_value,
                Integral,
            )
        ):
            failure_count = int(failure_count_value)
        else:
            raise TypeError("The persistence failure count must be an integer.")
        if failure_count >= self.PERSISTENCE_FAILURE_THRESHOLD:
            raise StuckPatchError(
                f"Agent Network Consultant could not apply a supported source-preserving change to {hocon_file} "
                f"after {failure_count} consecutive attempts. Review the persistence errors before retrying."
            )
        return response
