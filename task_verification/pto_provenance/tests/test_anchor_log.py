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

from pathlib import Path

import pytest
from task_verification.pto_provenance.anchor_log import AnchorLog
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph


class TestAnchorLog:
    """The anchor log catches the one rewrite the graph cannot catch alone: an edit with every later hash redone."""

    @pytest.fixture(autouse=True)
    def temporary_log(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Runs before each test: point the log at a throwaway file."""
        monkeypatch.setattr(AnchorLog, "PATH", tmp_path / "anchors.jsonl")

    def test_latest_is_the_newest_head_of_this_session(self) -> None:
        """Two sessions share the log; each gets back only its own newest head."""
        AnchorLog.record("session-a", "hash-1")
        AnchorLog.record("session-b", "hash-2")
        AnchorLog.record("session-a", "hash-3")
        assert AnchorLog.latest("session-a") == "hash-3"
        assert AnchorLog.latest("session-b") == "hash-2"
        assert AnchorLog.latest("session-c") is None

    def test_consistent_rewrite_needs_the_anchor(self) -> None:
        """Edit the call's date, then redo every hash after it: the graph alone looks intact, the anchor does not."""
        graph = ProvenanceGraph()
        call = graph.extend("E-1042", "ScheduleLeaveAPI", "tool_call", {"args": {"start_date": "2026-12-03"}})
        graph.extend("E-1042", "ScheduleLeaveAPI", "verification", {"verdict": "verified"}, also=[call])
        AnchorLog.record(graph.run_id, graph.head())

        # The attacker: change the date, then walk forward fixing every hash and every link to an old hash.
        graph.nodes[3]["data"]["args"]["start_date"] = "2026-12-04"
        renamed = {}
        for node in graph.nodes[3:]:
            node["prev"] = renamed.get(node.get("prev"), node.get("prev"))
            node["parents"] = [renamed.get(p, p) for p in node.get("parents")]
            old, node["hash"] = node.get("hash"), ProvenanceGraph.digest(node)
            renamed[old] = node.get("hash")

        assert graph.intact()
        assert not graph.intact(anchor=AnchorLog.latest(graph.run_id))
