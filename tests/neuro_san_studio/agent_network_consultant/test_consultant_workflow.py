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

"""Tests for Agent Network Consultant conversations, prompts, and reporting."""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.consultant_clarification_answerer import ConsultantClarificationAnswerer
from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession
from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.stuck_patch_error import StuckPatchError


class TestConsultantWorkflow(TestCase):
    """Verify the workflow coordinates injected collaborators without choosing their transports."""

    def setUp(self) -> None:
        """Create one isolated workflow directory for each test."""
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Remove the isolated workflow directory after each test."""
        shutil.rmtree(self.tmp_path)

    def _workflow(
        self,
        session: ConsultantSession,
        answerer: ConsultantClarificationAnswerer | None = None,
        job_files: ConsultantJobFiles | None = None,
        fixture_runner: FixtureRunner | None = None,
    ) -> ConsultantWorkflow:
        """
        Build a workflow with only the collaborator relevant to each test replaced.

        :param session: The simulated Agent Network Consultant session.
        :param answerer: The optional clarification transport.
        :param job_files: The optional nsflow job-file interface.
        :param fixture_runner: The optional fixture runtime.
        :return: The configured workflow.
        """
        selected_answerer = answerer or Mock(spec=ConsultantClarificationAnswerer)
        selected_job_files = job_files or Mock(spec=ConsultantJobFiles)
        selected_fixture_runner = fixture_runner or Mock(spec=FixtureRunner)
        return ConsultantWorkflow(session, selected_answerer, selected_job_files, selected_fixture_runner)

    def _failures(self) -> list[dict[str, Any]]:
        """
        Create one failing fixture report rooted in the temporary directory.

        :return: The fixture failure records.
        """
        fixture = self.tmp_path / "a.hocon"
        fixture.write_text("{}", encoding="utf-8")
        return [{"fixture": "a.hocon", "message": "boom", "path": str(fixture)}]

    @staticmethod
    def _round_state(
        total_fixture_count: int,
        round_fixture_count: int,
        is_subset_check: bool,
        iteration: int = 2,
    ) -> ConsultantRoundState:
        """
        Build the fixture coverage interface used by diagnosis prompts.

        :param total_fixture_count: The complete fixture-suite size.
        :param round_fixture_count: The number of fixtures run in the current round.
        :param is_subset_check: Whether the current results cover a subset.
        :param iteration: The current repair iteration.
        :return: The configured round-state interface.
        """
        round_state = Mock(spec=ConsultantRoundState)
        round_state.total_fixture_count.return_value = total_fixture_count
        round_state.result_count.return_value = round_fixture_count
        round_state.is_subset_check.return_value = is_subset_check
        round_state.iteration.return_value = iteration
        return round_state

    @staticmethod
    def _chat_with_unrelated_warning(message: str, sly_data: dict[str, Any] | None = None) -> str:
        """
        Emit an unrelated root warning during one simulated chat.

        :param message: The simulated chat message.
        :param sly_data: The simulated shared session state.
        :return: The simulated response.
        """
        del message, sly_data
        logging.getLogger().warning("unrelated warning")
        return "complete"

    def test_consult_stops_after_structured_persistence_failure_threshold(self) -> None:
        """Stop after the middleware reports three consecutive source-edit failures."""
        session = Mock(spec=ConsultantSession)
        session.chat.return_value = "complete"
        session.sly_data_value.return_value = ConsultantWorkflow.PERSISTENCE_FAILURE_THRESHOLD
        fixture_paths = {"a.hocon": "tests/fixtures/a.hocon"}

        with self.assertRaisesRegex(StuckPatchError, "could not apply.*example.hocon"):
            self._workflow(session).consult("fix it", "example.hocon", fixture_paths)

        chat_sly_data = session.chat.call_args.kwargs.get("sly_data")
        self.assertEqual(0, chat_sly_data.get(ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT))
        self.assertEqual("example.hocon", chat_sly_data.get(ConsultantState.AGENT_NETWORK_HOCON_FILE))
        self.assertEqual(fixture_paths, chat_sly_data.get(ConsultantState.TEST_FIXTURE_PATHS))

    def test_consult_rejects_a_noninteger_persistence_failure_count(self) -> None:
        """Reject malformed middleware state rather than coercing it into a failure count."""
        malformed_values: tuple[Any, Any, Any] = ("3", True, 3.5)
        for malformed_value in malformed_values:
            with self.subTest(malformed_value=malformed_value):
                session = Mock(spec=ConsultantSession)
                session.chat.return_value = "complete"
                session.sly_data_value.return_value = malformed_value

                with self.assertRaises(TypeError):
                    self._workflow(session).consult("fix it", "example.hocon", {})

    def test_consult_ignores_unrelated_root_logger_warnings(self) -> None:
        """Keep unrelated global warnings out of persistence control flow."""
        session = Mock(spec=ConsultantSession)
        session.chat.side_effect = self._chat_with_unrelated_warning
        session.sly_data_value.return_value = 0

        with self.assertLogs(level="WARNING"):
            response = self._workflow(session).consult("fix it", "example.hocon", {})

        self.assertEqual("complete", response)

    def test_clarification_uses_the_injected_answerer_without_logging_the_answer(self) -> None:
        """Delegate clarification transport and keep the user's private answer out of logs."""
        private_answer = "customer-secret-123"
        session = Mock(spec=ConsultantSession)
        session.chat.side_effect = ["NEEDS_CLARIFICATION: Which account?", "Complete"]
        session.sly_data_value.return_value = 0
        answerer = Mock(spec=ConsultantClarificationAnswerer)
        answerer.answer_all.return_value = [private_answer]

        with self.assertLogs(ConsultantWorkflow.__module__, level="INFO") as captured:
            response = self._workflow(session, answerer=answerer).consult("Diagnose", "example.hocon", {})

        self.assertEqual("Complete", response)
        answerer.answer_all.assert_called_once_with(["Which account?"])
        self.assertIn("clarification answer(s) received", "\n".join(captured.output))
        self.assertNotIn(private_answer, "\n".join(captured.output))

    def test_consult_stops_after_the_maximum_clarification_rounds(self) -> None:
        """Stop when the model keeps requesting clarification after every allowed answer round."""
        session = Mock(spec=ConsultantSession)
        session.chat.return_value = "NEEDS_CLARIFICATION: Which account?"
        session.sly_data_value.return_value = 0
        answerer = Mock(spec=ConsultantClarificationAnswerer)
        answerer.answer_all.return_value = ["account 42"]

        with self.assertRaisesRegex(RuntimeError, "maximum number of clarification rounds"):
            self._workflow(session, answerer=answerer).consult("Diagnose", "example.hocon", {})

        self.assertEqual(ConsultantWorkflow.MAX_CLARIFICATION_ROUNDS + 1, session.chat.call_count)
        self.assertEqual(ConsultantWorkflow.MAX_CLARIFICATION_ROUNDS, answerer.answer_all.call_count)

    def test_job_results_are_written_only_when_nsflow_is_active(self) -> None:
        """Use the injected job-file interface for optional nsflow reporting."""
        session = Mock(spec=ConsultantSession)
        with patch.dict(os.environ, {"NSFLOW_JOB_ID": "job1", "NSFLOW_JOB_DIR": str(self.tmp_path)}):
            workflow = self._workflow(session, job_files=ConsultantJobFiles())
            workflow.write_ungrounded(["a.hocon: URLProvider: Includes the GSD URL"])

        result_path = self.tmp_path / "job1.ungrounded.txt"
        self.assertIn("URLProvider", result_path.read_text(encoding="utf-8"))

    def test_diagnosis_prompt_describes_subset_coverage_and_ungrounded_policy(self) -> None:
        """Distinguish subset results and the selected ungrounded-criteria action."""
        session = Mock(spec=ConsultantSession)
        workflow = self._workflow(session)
        prompt = workflow.diagnosis_prompt(self._failures(), "keep behavior", self._round_state(5, 2, True))
        continue_prompt = workflow.diagnosis_prompt(
            self._failures(),
            "keep behavior",
            self._round_state(5, 2, True),
            "continue",
        )

        self.assertIn("only re-checked 2 of the 5 total fixtures", prompt)
        self.assertIn("do NOT classify it as AGENT FIX", prompt)
        self.assertNotIn("fixture_expectation_fixer", prompt)
        self.assertIn("fixture_expectation_fixer", continue_prompt)

    def test_diagnosis_prompt_describes_an_initial_user_selected_subset(self) -> None:
        """Identify an intentionally selected first-round subset without calling it a failure-only re-check."""
        session = Mock(spec=ConsultantSession)
        workflow = self._workflow(session)

        prompt = workflow.diagnosis_prompt(
            self._failures(),
            "keep behavior",
            self._round_state(5, 2, True, iteration=1),
        )

        self.assertIn("selected 2 of the 5 total fixtures for this first round", prompt)
        self.assertNotIn("only re-checked", prompt)

    def test_has_existing_fixtures_delegates_to_the_fixture_runtime(self) -> None:
        """Ask the injected fixture runtime whether a target already has tests."""
        fixture_runner = Mock(spec=FixtureRunner)
        fixture_runner.fixture_paths.return_value = [Path("tests/fixtures/example/a.hocon")]
        session = Mock(spec=ConsultantSession)

        result = self._workflow(session, fixture_runner=fixture_runner).has_existing_fixtures("example")

        self.assertTrue(result)
        fixture_runner.fixture_paths.assert_called_once_with("example")
