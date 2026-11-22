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
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from task_verification.pto_provenance.anchor_log import AnchorLog
from task_verification.pto_provenance.coded_tools.schedule_pto import SchedulePto
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph
from task_verification.pto_provenance.provenance_middleware import ProvenanceMiddleware
from task_verification.pto_provenance.turn_check_middleware import TurnCheckMiddleware
from task_verification.pto_provenance.turn_extractor import TurnExtractor


class StubExtractor:
    """Stands in for the LLM: returns fixed fields, and records what it was shown."""

    def __init__(self, intent: dict[str, Any], claim: str) -> None:
        self.fixed_intent: dict[str, Any] = intent
        self.fixed_claim: str = claim
        self.seen_user: list[str] = []
        self.seen_final: str = ""
        self.model: str = "stub-model"
        self.raw: dict[str, str | None] = {
            "intent": '{"action": "schedule_pto"}',
            "claim": '{"claim": "' + claim + '"}',
        }

    async def intent(self, user_messages: list[str]) -> dict[str, Any]:
        """:return: The fixed intent."""
        self.seen_user = user_messages
        return self.fixed_intent

    async def claim(self, final_message: str) -> str:
        """:return: The fixed claim."""
        self.seen_final = final_message
        return self.fixed_claim


class TestTurnCheckMiddleware:
    """A whole turn without an LLM: a real tool call through ProvenanceMiddleware, then the end-of-turn check."""

    ARGS: dict[str, str] = {"employee_id": "E-1042", "start_date": "2026-12-03", "end_date": "2026-12-03"}
    INTENT: dict[str, Any] = {
        "action": "schedule_pto",
        "employee_id": "E-1042",
        "start_date": "2026-12-03",
        "end_date": None,
    }
    USER: str = "I'm employee E-1042. Please schedule PTO for me on December 3, 2026."
    DONE: str = "Your PTO for December 3, 2026 has been scheduled."

    @pytest.fixture(autouse=True)
    def fresh_session(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Throwaway database, anchor log and live record, no fault, and a new graph."""
        monkeypatch.setattr(HrDatabase, "PATH", tmp_path / "hr.db")
        monkeypatch.setattr(AnchorLog, "PATH", tmp_path / "anchors.jsonl")
        monkeypatch.setattr(ProvenanceMiddleware, "LIVE_RECORD", tmp_path / "live_record.json")
        monkeypatch.setattr(TurnCheckMiddleware, "LIVE_RECORD", tmp_path / "live_record.json")
        monkeypatch.delenv("PTO_FAULT", raising=False)
        HrDatabase.reset()
        ProvenanceGraph.reset()

    @staticmethod
    async def run_tool(request: ToolCallRequest) -> ToolMessage:
        """Runs the real tool and wraps its reply the way langchain does."""
        reply: Any = await SchedulePto().async_invoke(request.tool_call.get("args"), {})
        return ToolMessage(content=str(reply), tool_call_id=request.tool_call.get("id"))

    def turn(
        self, extractor: StubExtractor, args: dict[str, str] | None, answer: str, notify_user: bool = True
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """
        Run one turn: before_agent, an optional tool call, after_agent.
        :return: What after_agent returned, and the turn_check node's data.
        """
        middleware = TurnCheckMiddleware(notify_user=notify_user)
        middleware.extractor = extractor  # type: ignore[assignment]
        state: dict[str, Any] = {"messages": [HumanMessage(self.USER)]}

        async def run() -> dict[str, Any] | None:
            await middleware.abefore_agent(state, None)
            if args is not None:
                tool_call: dict[str, Any] = {"name": "ScheduleLeaveAPI", "args": dict(args), "id": "llm-call-1"}
                request = ToolCallRequest(tool_call=tool_call, tool=None, state={}, runtime=None)
                await ProvenanceMiddleware(tools=["ScheduleLeaveAPI"]).awrap_tool_call(request, self.run_tool)
            state["messages"].append(AIMessage(answer))
            return await middleware.aafter_agent(state, None)

        returned: dict[str, Any] | None = asyncio.run(run())
        check: dict[str, Any] = ProvenanceGraph.active().nodes[-1]
        assert check["kind"] == "turn_check"
        return returned, check

    def test_honest_turn_is_consistent_and_answer_is_untouched(self) -> None:
        """Booked as asked, reported as done: verdict consistent, and the answer goes out unchanged."""
        returned, check = self.turn(StubExtractor(self.INTENT, "success"), self.ARGS, self.DONE)
        assert check["data"]["verdict"] == "consistent"
        assert returned is None

    def test_issue_case_is_caught_and_the_user_is_warned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Issue #1574: the tool writes nothing but replies "submitted", and the agent tells the user it is done.
        The turn must be recorded as misreported and the user's answer must carry a notice.
        """
        monkeypatch.setenv("PTO_FAULT", "no_write")
        returned, check = self.turn(StubExtractor(self.INTENT, "success"), self.ARGS, self.DONE)
        assert check["data"]["verdict"] == "misreported"
        assert returned is not None
        warned: str = returned["messages"][0].content
        assert warned.startswith(self.DONE)
        assert "Verification notice" in warned
        assert "no row was written" in warned

    def test_turn_check_links_to_the_verification_it_used_and_is_anchored(self) -> None:
        """The check is evidence too: it points at the verification node and the graph still checks out."""
        _, check = self.turn(StubExtractor(self.INTENT, "success"), self.ARGS, self.DONE)
        graph: ProvenanceGraph = ProvenanceGraph.active()
        verification: dict[str, Any] = next(n for n in graph.nodes if n["kind"] == "verification")
        assert verification["hash"] in check["parents"]
        assert graph.intact(anchor=AnchorLog.latest(graph.run_id))

    def test_wrong_date_from_the_agent_is_caught(self) -> None:
        """The agent asks for Dec 4; the tool and database agree (verified), but the user asked for Dec 3."""
        wrong: dict[str, str] = {**self.ARGS, "start_date": "2026-12-04", "end_date": "2026-12-04"}
        returned, check = self.turn(StubExtractor(self.INTENT, "success"), wrong, self.DONE)
        verification: dict[str, Any] = next(n for n in ProvenanceGraph.active().nodes if n["kind"] == "verification")
        assert verification["data"]["verdict"] == "verified"  # the old check passes
        assert check["data"]["intent_check"] == "mismatch"  # the new one does not
        assert returned is not None

    def test_claimed_success_with_no_tool_call_is_caught(self) -> None:
        """The agent skips the tool entirely and still says it is done."""
        returned, check = self.turn(StubExtractor(self.INTENT, "success"), None, self.DONE)
        assert check["data"]["verdict"] == "misreported"
        assert returned is not None

    def test_only_this_turns_calls_are_checked(self) -> None:
        """A booking from an earlier turn must not make this turn's "done" look backed by evidence."""
        self.turn(StubExtractor(self.INTENT, "success"), self.ARGS, self.DONE)  # turn 1: a real booking
        _, check = self.turn(StubExtractor(self.INTENT, "success"), None, self.DONE)  # turn 2: no call
        assert check["data"]["verdict"] == "misreported"
        assert check["data"]["bookings_confirmed"] == 0

    def test_notice_can_be_switched_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With notify_user off, the verdict is still recorded but the answer is left alone."""
        monkeypatch.setenv("PTO_FAULT", "no_write")
        returned, check = self.turn(StubExtractor(self.INTENT, "success"), self.ARGS, self.DONE, notify_user=False)
        assert check["data"]["verdict"] == "misreported"
        assert returned is None

    def test_turn_check_records_what_the_extraction_saw_and_said(self) -> None:
        """
        A wrong verdict must be traceable from the record alone: the extracted fields sit next to the verdict, with the
        model, the exact text each extraction read and each call's raw reply.
        """
        _, check = self.turn(StubExtractor(self.INTENT, "success"), self.ARGS, self.DONE)
        data: dict[str, Any] = check["data"]
        assert data["intent"] == self.INTENT
        assert data["claim"] == "success"
        assert data["extraction"] == {
            "model": "stub-model",
            "intent_input": [self.USER],
            "intent_raw": '{"action": "schedule_pto"}',
            "claim_input": self.DONE,
            "claim_raw": '{"claim": "success"}',
        }

    def test_extractor_sees_user_messages_and_final_answer_separately(self) -> None:
        """Intent is read from the user's words only; the claim from the final answer only."""
        stub = StubExtractor(self.INTENT, "success")
        self.turn(stub, self.ARGS, self.DONE)
        assert stub.seen_user == [self.USER]
        assert stub.seen_final == self.DONE


class TestTurnExtractor:
    """The LLM wrapper, with a fake model: parsing, cleaning, and failing safe."""

    def test_reads_intent_json(self) -> None:
        """A well-formed reply, wrapped in prose, is parsed."""
        llm = FakeListChatModel(
            responses=[
                'Sure: {"action": "schedule_pto", "employee_id": "E-1042", '
                '"start_date": "2026-12-03", "end_date": null}'
            ]
        )
        intent = asyncio.run(TurnExtractor(llm).intent(["book Dec 3"], today=date(2026, 11, 21)))
        assert intent == {
            "action": "schedule_pto",
            "employee_id": "E-1042",
            "start_date": "2026-12-03",
            "end_date": None,
        }

    def test_badly_formatted_date_becomes_unknown(self) -> None:
        """ "Dec 3" is not compared as text against "2026-12-03"; it is treated as unknown."""
        llm = FakeListChatModel(
            responses=['{"action": "schedule_pto", "employee_id": "E-1042", "start_date": "Dec 3", "end_date": null}']
        )
        intent = asyncio.run(TurnExtractor(llm).intent(["book Dec 3"]))
        assert intent["start_date"] is None

    def test_garbage_reply_is_unknown_not_a_pass(self) -> None:
        """An unreadable reply gives unknown fields and an unknown claim, which TurnChecker flags."""
        llm = FakeListChatModel(responses=["I'm not sure.", "no json here"])
        extractor = TurnExtractor(llm)
        assert asyncio.run(extractor.intent(["book Dec 3"]))["action"] is None
        assert asyncio.run(extractor.claim("Your PTO is booked.")) == "unknown"

    def test_reads_claim(self) -> None:
        """A valid claim value is returned as is."""
        llm = FakeListChatModel(responses=['{"claim": "success"}'])
        assert asyncio.run(TurnExtractor(llm).claim("Your PTO is booked.")) == "success"

    def test_keeps_raw_replies_and_model(self) -> None:
        """The raw text of each reply is kept, even when it cannot be parsed, so a bad extraction can be traced."""
        llm = FakeListChatModel(responses=['Sure: {"action": "other"}', "no json here"])
        extractor = TurnExtractor(llm)
        asyncio.run(extractor.intent(["what is the holiday calendar?"]))
        asyncio.run(extractor.claim("Here is the calendar."))
        assert extractor.raw == {"intent": 'Sure: {"action": "other"}', "claim": "no json here"}
        assert extractor.model == "FakeListChatModel"  # a fake model has no model name, so the class name is used

    def test_failed_call_is_kept_as_an_error_string(self) -> None:
        """A failed call leaves its error in the record instead of nothing, and the claim stays unknown."""

        class FailingModel:  # pylint: disable=too-few-public-methods
            """A chat model whose every call fails, as with a bad API key."""

            model: str = "failing-model"

            async def ainvoke(self, _messages: Any) -> Any:
                """:raises RuntimeError: Always."""
                raise RuntimeError("API key not valid")

        extractor = TurnExtractor(FailingModel())  # type: ignore[arg-type]
        assert asyncio.run(extractor.claim("Your PTO is booked.")) == "unknown"
        assert extractor.raw["claim"] == "call failed: RuntimeError: API key not valid"
        assert extractor.model == "failing-model"
