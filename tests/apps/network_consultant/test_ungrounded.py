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

"""A criterion no tool in the network can satisfy is not an agent defect."""

from pathlib import Path

import pytest

from neuro_san_studio.network_consultant import consultant_workflow
from neuro_san_studio.network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.network_consultant.consultant_workflow import ConsultantWorkflow

REPLY = """\
hr_check_vacation_balance_today.hocon: fixed AbsenceManagement
UNGROUNDED: it_password_reset_gsd_ticket.hocon: URLProvider: Includes the GSD URL
UNGROUNDED: legal_ambiguous.hocon: URLProvider: Includes at least one internal URL
"""

FAILURE = {"fixture": "a.hocon", "message": "boom", "path": None}


class TestUngrounded:
    """Test ungrounded."""

    @staticmethod
    def _failures(tmp_path: Path) -> list[dict[str, str | None]]:
        """Create one failing fixture report rooted in the temporary directory."""
        fixture = tmp_path / "a.hocon"
        fixture.write_text("{}", encoding="utf-8")
        return [{**FAILURE, "path": str(fixture)}]

    @staticmethod
    def test_ungrounded_lines_are_extracted() -> None:
        """Every ungrounded response line is extracted independently."""
        assert ConsultantScoring.extract_prefixed(REPLY, ConsultantWorkflow.UNGROUNDED_PREFIX) == [
            "it_password_reset_gsd_ticket.hocon: URLProvider: Includes the GSD URL",
            "legal_ambiguous.hocon: URLProvider: Includes at least one internal URL",
        ]

    @staticmethod
    def test_they_are_written_where_nsflow_can_surface_them(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Ungrounded results are written to the active nsflow job directory."""
        monkeypatch.setattr(consultant_workflow, "NSFLOW_JOB_ID", "job1")
        monkeypatch.setattr(consultant_workflow, "NSFLOW_JOB_DIR", str(tmp_path))
        ConsultantWorkflow.write_ungrounded(["a.hocon: URLProvider: Includes the GSD URL"])
        assert "URLProvider" in (tmp_path / "job1.ungrounded.txt").read_text(encoding="utf-8")

    @staticmethod
    def test_no_file_outside_an_nsflow_job(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Plain CLI runs do not create nsflow result files."""
        monkeypatch.setattr(consultant_workflow, "NSFLOW_JOB_ID", None)
        monkeypatch.setattr(consultant_workflow, "NSFLOW_JOB_DIR", str(tmp_path))
        ConsultantWorkflow.write_ungrounded(["x"])
        assert not list(tmp_path.iterdir())

    @staticmethod
    def test_the_prompt_forbids_calling_it_an_agent_fix(tmp_path: Path) -> None:
        """The whole point: misclassifying this as AGENT FIX is what burned four rounds."""
        prompt = ConsultantWorkflow.diagnosis_prompt(TestUngrounded._failures(tmp_path), "keep behaviour", 6, False)
        assert "UNGROUNDED" in prompt
        assert "do NOT classify it as AGENT FIX" in prompt
        assert "fabricated answer is worse than a failing test" in prompt

    @staticmethod
    def test_the_prompt_carries_the_chosen_policy(tmp_path: Path) -> None:
        """The prompt distinguishes stopping from removing ungrounded criteria."""
        stop = ConsultantWorkflow.diagnosis_prompt(TestUngrounded._failures(tmp_path), "d", 6, False, "stop")
        keep = ConsultantWorkflow.diagnosis_prompt(TestUngrounded._failures(tmp_path), "d", 6, False, "continue")
        assert "change neither the network nor the fixture" in stop
        assert "fixture_expectation_fixer" not in stop
        assert "fixture_expectation_fixer" in keep

    @staticmethod
    def test_the_consultant_registry_declares_the_class_and_the_fixer_exception() -> None:
        """Runner-side reporting is useless if the consultant never emits the line.

        Deliberately pins the CONTRACT, not the prose: the failure-class wording is edited by hand
        and a test that locks the exact sentences just breaks every time someone tightens them.
        What must hold is that the class exists, that it names the output format the runner parses
        with UNGROUNDED_PREFIX, and that fixture_expectation_fixer has its exception -- it otherwise
        refuses whenever the network is behaving correctly, which is exactly this case.
        """
        consultant = Path("registries/agent_network_consultant.hocon").read_text(encoding="utf-8")
        assert "UNGROUNDED:" in consultant
        assert "`UNGROUNDED: <fixture>: <toolname>:" in consultant
        assert "read_thinking_trace" in consultant
        assert "2b. EXCEPTION" in consultant
