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

import argparse
from functools import partial
from typing import Any

import pytest

from neuro_san_studio.network_consultant.consultant_connection import ConsultantConnection
from neuro_san_studio.network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.network_consultant.consultant_score_state import ConsultantScoreState
from neuro_san_studio.network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.network_consultant.network_consultant import NetworkConsultant
from neuro_san_studio.network_consultant.progress_tracker import ProgressTracker


class TestNetworkConsultant:
    """Verify the extracted orchestration preserves its original control flow."""

    @staticmethod
    def _context() -> ConsultantRunContext:
        """Build an inert run context for orchestration tests."""
        args = argparse.Namespace(
            connection="direct",
            force_generate=False,
            git_versions=False,
            hocon_file="example.hocon",
            host="localhost",
            max_iterations=2,
            only_fixtures=None,
            port=8080,
            success_ratio="3/3",
            test_guidance="",
            test_level="normal",
            ungrounded="stop",
            use_case=None,
        )
        return ConsultantRunContext(
            args=args,
            connection=ConsultantConnection(object(), {}),
            target=ConsultantTarget("example.hocon", "example", "Preserve behavior", "registries/example.hocon"),
            resources=ConsultantResources(),
            scores=ConsultantScoreState(),
            round=ConsultantRoundState(),
            progress_tracker=ProgressTracker(),
        )

    @staticmethod
    def _load_failing_round(calls: list[str], run_context: ConsultantRunContext) -> None:
        """Populate one ordinary failing round and record the load stage."""
        calls.append("load")
        run_context.round.results = [{"fixture": "failure.hocon", "passed": False}]
        run_context.round.failures = list(run_context.round.results)
        run_context.round.total_fixture_count = 1

    @staticmethod
    def _load_infrastructure_error(run_context: ConsultantRunContext) -> None:
        """Populate one infrastructure failure."""
        run_context.round.results = [
            {
                "fixture": "failure.hocon",
                "passed": False,
                "infrastructure_error": True,
                "message": "provider unavailable",
            }
        ]
        run_context.round.failures = list(run_context.round.results)

    def test_iteration_preserves_stage_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Keep load, record, score, and consult stages in their original order."""
        context = self._context()
        calls: list[str] = []

        monkeypatch.setattr(NetworkConsultant, "_load_round_results", partial(self._load_failing_round, calls))
        monkeypatch.setattr(NetworkConsultant, "_record_round", lambda _context: calls.append("record"))
        monkeypatch.setattr(NetworkConsultant, "_log_and_commit_round", lambda _context: calls.append("commit"))
        monkeypatch.setattr(NetworkConsultant, "_widen_stale_subset", lambda _context: calls.append("widen") or False)
        monkeypatch.setattr(NetworkConsultant, "_update_scores", lambda _context: calls.append("score"))
        monkeypatch.setattr(NetworkConsultant, "_stop_for_plateau", lambda _context: calls.append("plateau") or False)
        monkeypatch.setattr(NetworkConsultant, "_consult_and_apply", lambda _context: calls.append("consult") or False)

        should_stop = NetworkConsultant.run_iteration(context)

        assert not should_stop
        assert calls == ["load", "record", "commit", "widen", "score", "plateau", "consult"]

    def test_iteration_stops_before_recording_infrastructure_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Do not score or modify a network when fixture infrastructure fails."""
        context = self._context()
        calls: list[str] = []

        monkeypatch.setattr(NetworkConsultant, "_load_round_results", self._load_infrastructure_error)
        monkeypatch.setattr(NetworkConsultant, "_record_round", lambda _context: calls.append("record"))

        should_stop = NetworkConsultant.run_iteration(context)

        assert should_stop
        assert not calls

    def test_execute_always_cleans_temporary_resources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Restore fixture ratios and stop versioning even after an early terminal round."""
        context = self._context()
        context.resources.original_ratios.update({"fixture.hocon": "1/1"})
        cleanup_calls: list[tuple[str, Any]] = []

        monkeypatch.setattr(NetworkConsultant, "_start_git_versioning", lambda _context: "worktree")
        monkeypatch.setattr(NetworkConsultant, "_iterate", lambda _context: True)
        monkeypatch.setattr(
            "neuro_san_studio.network_consultant.network_consultant.FixtureRunner.restore_success_ratios",
            lambda ratios: cleanup_calls.append(("ratios", ratios)),
        )
        monkeypatch.setattr(
            "neuro_san_studio.network_consultant.network_consultant.GitVersioning.stop_git_versioning",
            lambda worktree: cleanup_calls.append(("git", worktree)),
        )
        monkeypatch.setattr(
            "neuro_san_studio.network_consultant.network_consultant.signal.signal", lambda *_args: None
        )

        NetworkConsultant.execute(context)

        assert cleanup_calls == [("ratios", {"fixture.hocon": "1/1"}), ("git", "worktree")]
