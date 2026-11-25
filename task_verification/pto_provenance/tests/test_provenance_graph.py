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

from task_verification.pto_provenance.provenance_graph import ProvenanceGraph


class TestProvenanceGraph:
    """
    The graph's structure, its pending list, and which tampering it detects. The test session's nodes, by position:
      0 run, 1 user, 2 operation, 3 tool_call, 4 tool_reply, 5 verification
    """

    @staticmethod
    def one_verified_call() -> ProvenanceGraph:
        """:return: A graph holding one tool call, its reply and its verification, for E-1042."""
        graph = ProvenanceGraph()
        call = graph.extend("E-1042", "ScheduleLeaveAPI", "tool_call", {"args": {"start_date": "2026-12-03"}})
        graph.extend("E-1042", "ScheduleLeaveAPI", "tool_reply", {"reply": "submitted"})
        graph.extend("E-1042", "ScheduleLeaveAPI", "verification", {"verdict": "verified"}, also=[call])
        return graph

    def test_structure(self) -> None:
        """Branch links via parents, one timeline via prev, the verification points back at its call."""
        graph = self.one_verified_call()
        nodes = graph.nodes
        kinds = [n.get("kind") for n in nodes]
        assert kinds == ["run", "user", "operation", "tool_call", "tool_reply", "verification"]
        assert all(nodes[i].get("prev") == nodes[i - 1].get("hash") for i in range(1, len(nodes)))
        assert nodes[5].get("parents") == [nodes[4].get("hash"), nodes[3].get("hash")]
        assert graph.heads.get("E-1042/ScheduleLeaveAPI") == graph.head()

    def test_pending_lists_calls_not_yet_verified(self) -> None:
        """A call is pending until a verification points to it."""
        graph = ProvenanceGraph()
        call = graph.extend("E-1042", "ScheduleLeaveAPI", "tool_call", {"args": {}})
        assert graph.pending() == [call]
        graph.extend("E-1042", "ScheduleLeaveAPI", "verification", {"verdict": "verified"}, also=[call])
        assert graph.pending() == []

    def test_untouched_graph_is_intact(self) -> None:
        """No tampering: intact, with and without the anchor."""
        graph = self.one_verified_call()
        assert graph.intact()
        assert graph.intact(anchor=graph.head())

    def test_edited_value_is_detected(self) -> None:
        """Flipping a recorded verdict changes the node, so its hash no longer matches."""
        graph = self.one_verified_call()
        graph.nodes[5]["data"]["verdict"] = "not_verified"
        assert not graph.intact()

    def test_added_space_is_detected(self) -> None:
        """Even one added space in a recorded value changes the hash: the encoding never cleans values."""
        graph = self.one_verified_call()
        graph.nodes[3]["data"]["args"]["start_date"] = "2026-12-03 "
        assert not graph.intact()

    def test_deleted_middle_node_is_detected(self) -> None:
        """The node after the gap still names the deleted node as its prev."""
        graph = self.one_verified_call()
        del graph.nodes[4]
        assert not graph.intact()

    def test_deleted_newest_node_needs_the_anchor(self) -> None:
        """Nothing comes after the newest node, so deleting it breaks no link; only the anchor reveals it."""
        graph = self.one_verified_call()
        anchor = graph.head()
        del graph.nodes[-1]
        assert graph.intact()
        assert not graph.intact(anchor=anchor)
