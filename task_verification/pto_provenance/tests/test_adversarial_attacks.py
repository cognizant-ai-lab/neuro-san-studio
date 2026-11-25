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
from pathlib import Path
from typing import Any

import pytest
from task_verification.pto_provenance.coded_tools.schedule_pto import SchedulePto
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.idempotency_context import IdempotencyContext
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph
from task_verification.pto_provenance.pto_verifier import PtoVerifier


class TestAdversarialAttacks:
    """Attacks we expect from agents or the code around them: borrowed evidence, racing calls, rewritten records."""

    GOOD_ARGS: dict[str, str] = {"employee_id": "E-1042", "start_date": "2026-12-03", "end_date": "2026-12-03"}

    @pytest.fixture(autouse=True)
    def temporary_database(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Runs before each test: point the database at a throwaway file, create its tables, no fault switched on."""
        monkeypatch.setattr(HrDatabase, "PATH", tmp_path / "hr.db")
        monkeypatch.delenv("PTO_FAULT", raising=False)
        HrDatabase.reset()

    @staticmethod
    async def call_tool(key: str, args: dict[str, Any]) -> Any:
        """Do what the middleware will do: set this call's key, let other work run, then run the tool."""
        IdempotencyContext.KEY.set(key)
        await asyncio.sleep(0)  # hand control to the other calls, as real framework code between the two would
        return await SchedulePto().async_invoke(args, {})

    def test_failed_call_cannot_borrow_an_earlier_calls_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Borrowed evidence: call 1 really writes a row. Call 2 writes nothing but reports success, and the agent puts
        call 1's key in its arguments, hoping the verifier finds call 1's identical row and passes call 2.
        """
        asyncio.run(self.call_tool("key-call-1", self.GOOD_ARGS))
        monkeypatch.setenv("PTO_FAULT", "no_write")
        smuggled: dict[str, str] = {**self.GOOD_ARGS, "idempotency_key": "key-call-1"}
        reply = asyncio.run(self.call_tool("key-call-2", smuggled))

        verdict = PtoVerifier.check(smuggled, str(reply), HrDatabase.requests_with_key("key-call-2"))
        assert verdict.get("verdict") == "not_verified"
        assert "tool reported success but no row was written" in verdict.get("problems")
        assert len(HrDatabase.requests_with_key("key-call-1")) == 1

    def test_parallel_calls_keep_their_own_evidence(self) -> None:
        """
        Racing calls: the agent fires 20 calls at once for two employees. Each call's row must carry its own key,
        so no call is verified by, or blamed for, another call's row.
        """
        calls: list[tuple[str, dict[str, str]]] = [
            (
                f"key-{i}",
                {
                    "employee_id": ("E-1042", "E-2077")[i % 2],
                    "start_date": f"2026-12-{i + 1:02d}",
                    "end_date": f"2026-12-{i + 1:02d}",
                },
            )
            for i in range(20)
        ]

        # Nested because asyncio.run needs one coroutine that starts all 20 calls together, and it uses `calls`.
        async def all_at_once() -> list[Any]:
            return await asyncio.gather(*(self.call_tool(key, args) for key, args in calls))

        replies: list[Any] = asyncio.run(all_at_once())
        for (key, args), reply in zip(calls, replies):
            verdict = PtoVerifier.check(args, str(reply), HrDatabase.requests_with_key(key))
            assert verdict.get("verdict") == "verified", (key, verdict)

    def test_recorded_request_cannot_be_changed_afterwards(self) -> None:
        """
        Rewriting through a shared reference: the graph records the agent's arguments. Afterwards, code that still
        holds the same dict (the framework, a retry, another middleware) edits it. The record must not change.
        """
        graph = ProvenanceGraph()
        args: dict[str, str] = dict(self.GOOD_ARGS)
        call: str = graph.extend("E-1042", "ScheduleLeaveAPI", "tool_call", {"idempotency_key": "k", "args": args})
        args["start_date"] = "2026-12-24"

        recorded: dict[str, Any] = next(node for node in graph.nodes if node.get("hash") == call)
        assert recorded.get("data").get("args").get("start_date") == "2026-12-03"
        assert graph.intact()
