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

from typing import Any

from task_verification.pto_provenance.turn_checker import TurnChecker


class TestTurnChecker:
    """The deterministic end-of-turn comparison, one case per way a turn can go right or wrong."""

    INTENT: dict[str, Any] = {
        "action": "schedule_pto",
        "employee_id": "E-1042",
        "start_date": "2026-12-03",
        "end_date": None,
    }
    ARGS: dict[str, str] = {"employee_id": "E-1042", "start_date": "2026-12-03", "end_date": "2026-12-03"}

    @staticmethod
    def record(args: dict[str, str], verdict: str, problems: list[str] | None = None) -> dict[str, Any]:
        """One verification record, as TurnCheckMiddleware builds it from the graph."""
        return {"args": args, "verdict": verdict, "problems": problems or []}

    def test_booked_as_asked_and_reported_is_consistent(self) -> None:
        """The happy path: the database has the right booking and the agent says so."""
        result = TurnChecker.check(self.INTENT, "success", [self.record(self.ARGS, "verified")])
        assert result["verdict"] == "consistent"
        assert result["intent_check"] == "match"
        assert result["report_check"] == "honest"
        assert result["problems"] == []

    def test_claimed_success_after_tool_lied_is_misreported(self) -> None:
        """The issue's case: the tool wrote nothing, the agent tells the user it is done."""
        failed = self.record(self.ARGS, "not_verified", ["tool reported success but no row was written"])
        result = TurnChecker.check(self.INTENT, "success", [failed])
        assert result["verdict"] == "misreported"
        assert "no row was written" in result["problems"][0]

    def test_claimed_success_without_any_tool_call_is_misreported(self) -> None:
        """The agent never called the tool but still says it is done."""
        result = TurnChecker.check(self.INTENT, "success", [])
        assert result["verdict"] == "misreported"
        assert "no booking was attempted" in result["problems"][0]

    def test_agent_asking_for_the_wrong_date_is_intent_mismatch(self) -> None:
        """
        The gap PtoVerifier cannot see: the agent asked for Dec 4, the tool booked Dec 4, the database agrees with the
        tool (verified), but the user asked for Dec 3.
        """
        wrong: dict[str, str] = {**self.ARGS, "start_date": "2026-12-04", "end_date": "2026-12-04"}
        result = TurnChecker.check(self.INTENT, "success", [self.record(wrong, "verified")])
        assert result["intent_check"] == "mismatch"
        # The agent's "done" is false too: what was done is not what was asked.
        assert result["report_check"] == "misreported"
        assert result["verdict"] == "misreported"
        assert any("start_date" in problem for problem in result["problems"])

    def test_wrong_booking_reported_as_failure_is_intent_mismatch(self) -> None:
        """A wrong booking exists while the agent says it failed: the report is fine, the booking is not."""
        wrong: dict[str, str] = {**self.ARGS, "employee_id": "E-2077"}
        result = TurnChecker.check(self.INTENT, "failure", [self.record(wrong, "verified")])
        assert result["verdict"] == "intent_mismatch"
        assert result["report_check"] == "honest"

    def test_two_bookings_for_one_request_is_intent_mismatch(self) -> None:
        """The agent called the tool twice; each call was honest, but the user now has two bookings."""
        result = TurnChecker.check(
            self.INTENT, "success", [self.record(self.ARGS, "verified"), self.record(self.ARGS, "verified")]
        )
        assert result["intent_check"] == "mismatch"
        assert "2 separate bookings" in result["problems"][0]

    def test_honest_failure_is_consistent(self) -> None:
        """The tool reported an error and the agent passed that on: nothing is wrong with the turn."""
        result = TurnChecker.check(self.INTENT, "failure", [self.record(self.ARGS, "failure_confirmed")])
        assert result["verdict"] == "consistent"

    def test_saying_failed_when_it_worked_is_misreported(self) -> None:
        """Under-reporting counts: the user would book again and get a duplicate."""
        result = TurnChecker.check(self.INTENT, "failure", [self.record(self.ARGS, "verified")])
        assert result["verdict"] == "misreported"

    def test_question_before_any_booking_is_consistent(self) -> None:
        """The agent asks for the employee ID first and books nothing yet."""
        intent: dict[str, Any] = {**self.INTENT, "employee_id": None}
        result = TurnChecker.check(intent, "question", [])
        assert result["verdict"] == "consistent"

    def test_unrelated_chat_is_not_applicable(self) -> None:
        """A question about the holiday calendar: no PTO asked for, none booked, nothing to check."""
        intent: dict[str, Any] = {"action": "other", "employee_id": None, "start_date": None, "end_date": None}
        result = TurnChecker.check(intent, "none", [])
        assert result["verdict"] == "not_applicable"

    def test_booking_nobody_asked_for_is_intent_mismatch(self) -> None:
        """The user only asked a question, yet a booking was made."""
        intent: dict[str, Any] = {"action": "other", "employee_id": None, "start_date": None, "end_date": None}
        result = TurnChecker.check(intent, "none", [self.record(self.ARGS, "verified")])
        assert result["verdict"] == "intent_mismatch"

    def test_unreadable_claim_is_never_consistent(self) -> None:
        """If the extractor could not read the final message, the turn is unclear, not passed."""
        result = TurnChecker.check(self.INTENT, "unknown", [self.record(self.ARGS, "verified")])
        assert result["verdict"] == "unclear"

    def test_unknown_intent_fields_make_the_turn_unclear(self) -> None:
        """The user's dates could not be read: the booking cannot be confirmed as what they wanted."""
        intent: dict[str, Any] = {**self.INTENT, "start_date": None}
        result = TurnChecker.check(intent, "success", [self.record(self.ARGS, "verified")])
        assert result["intent_check"] == "unclear"
        assert result["verdict"] == "unclear"

    def test_user_fields_are_cleaned_like_the_tool_cleans_them(self) -> None:
        """ " e-1042 " from the user and "E-1042" in the database are the same employee."""
        intent: dict[str, Any] = {**self.INTENT, "employee_id": " e-1042 "}
        result = TurnChecker.check(intent, "success", [self.record(self.ARGS, "verified")])
        assert result["verdict"] == "consistent"
