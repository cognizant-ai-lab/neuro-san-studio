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

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from task_verification.pto_provenance.anchor_log import AnchorLog
from task_verification.pto_provenance.coded_tools.schedule_pto import SchedulePto
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.idempotency_context import IdempotencyContext
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph
from task_verification.pto_provenance.provenance_middleware import ProvenanceMiddleware


class TestProvenanceMiddleware:
    """The middleware end to end, without an LLM: one tool call goes in, the graph and the anchor log come out."""

    ARGS: dict[str, str] = {"employee_id": "E-1042", "start_date": "2026-12-03", "end_date": "2026-12-03"}

    @pytest.fixture(autouse=True)
    def fresh_session(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Runs before each test: throwaway database and anchor log, no fault, and a new graph (a new chat session)."""
        monkeypatch.setattr(HrDatabase, "PATH", tmp_path / "hr.db")
        monkeypatch.setattr(AnchorLog, "PATH", tmp_path / "anchors.jsonl")
        monkeypatch.setattr(ProvenanceMiddleware, "LIVE_RECORD", tmp_path / "live_record.json")
        monkeypatch.delenv("PTO_FAULT", raising=False)
        HrDatabase.reset()
        ProvenanceGraph.reset()

    @staticmethod
    async def run_tool(request: ToolCallRequest) -> ToolMessage:
        """Stands in for langchain's handler: runs the real tool and wraps its reply the way langchain does."""
        reply: Any = await SchedulePto().async_invoke(request.tool_call.get("args"), {})
        return ToolMessage(content=str(reply), tool_call_id=request.tool_call.get("id"))

    def test_lying_tool_is_recorded_as_not_verified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        The tool writes nothing but tells the agent "submitted" (fault no_write). The agent must get that reply
        unchanged; the graph must hold the call, the reply and a not_verified verdict under one key; and the anchor
        log must hold the graph's newest hash.
        """
        monkeypatch.setenv("PTO_FAULT", "no_write")
        # The agent's tool call, as langchain hands it to the middleware.
        tool_call: dict[str, Any] = {"name": "ScheduleLeaveAPI", "args": dict(self.ARGS), "id": "llm-call-1"}
        request = ToolCallRequest(tool_call=tool_call, tool=None, state={}, runtime=None)

        middleware = ProvenanceMiddleware(tools=["ScheduleLeaveAPI"])
        result: Any = asyncio.run(middleware.awrap_tool_call(request, self.run_tool))

        # The agent sees the tool's (false) success, untouched: the verdict is not fed back.
        assert "submitted" in result.content
        # The key was cleared after the call, so it cannot leak into the next one.
        assert IdempotencyContext.KEY.get() is None

        # The three nodes for this call, in order, all carrying the same key.
        graph: ProvenanceGraph = ProvenanceGraph.active()
        call, reply, verification = graph.nodes[-3:]
        assert [call.get("kind"), reply.get("kind"), verification.get("kind")] == [
            "tool_call",
            "tool_reply",
            "verification",
        ]
        key: str = call.get("data").get("idempotency_key")
        assert reply.get("data").get("idempotency_key") == key == verification.get("data").get("idempotency_key")
        assert call.get("data").get("llm_call_id") == "llm-call-1"

        # The verdict: caught, and linked back to the call it checked, so nothing is left pending.
        assert verification.get("data").get("verdict") == "not_verified"
        assert "tool reported success but no row was written" in verification.get("data").get("problems")
        assert call.get("hash") in verification.get("parents")
        assert not graph.pending()

        # The anchor log holds the graph's newest hash, and the graph checks out against it.
        assert AnchorLog.latest(graph.run_id) == graph.head()
        assert graph.intact(anchor=AnchorLog.latest(graph.run_id))

    def test_without_a_runner_the_first_call_starts_and_saves_the_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        In the studio UI no runner calls ProvenanceGraph.reset(). The first watched call must start a graph itself,
        and save it after verifying, so a separate process can read it.
        """
        monkeypatch.setattr(ProvenanceGraph, "_active", None)  # as in a freshly started server: no graph yet
        tool_call: dict[str, Any] = {"name": "ScheduleLeaveAPI", "args": dict(self.ARGS), "id": "llm-call-1"}
        request = ToolCallRequest(tool_call=tool_call, tool=None, state={}, runtime=None)

        asyncio.run(ProvenanceMiddleware(tools=["ScheduleLeaveAPI"]).awrap_tool_call(request, self.run_tool))

        graph: ProvenanceGraph = ProvenanceGraph.active()  # started by the call: no RuntimeError
        saved: dict[str, Any] = json.loads(ProvenanceMiddleware.LIVE_RECORD.read_text(encoding="utf-8"))
        assert saved.get("head") == graph.head()
        assert saved.get("nodes")[-1].get("data").get("verdict") == "verified"
