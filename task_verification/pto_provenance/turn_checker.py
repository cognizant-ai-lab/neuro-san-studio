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

from task_verification.pto_provenance.coded_tools.schedule_pto import SchedulePto


class TurnChecker:  # pylint: disable=too-few-public-methods
    """
    Deterministic end-of-turn check. No LLM.

    PtoVerifier checks one tool call against the database: did the tool do what the agent asked? It cannot tell
    whether the agent asked for the right thing, or whether the agent then told the user the truth. This class
    covers those two gaps, once per user turn, from three inputs:

      intent         what the user asked for, as structured fields (from TurnExtractor, which reads only the user's
                     messages, never the agent's answer)
      claim          what the agent's final message tells the user (from TurnExtractor, which reads only that message,
                     never the evidence)
      verifications  this turn's PtoVerifier results, each with the arguments of the call it checked

    An LLM turns free text into those small structured fields; every judgement below is a plain comparison, so the
    same inputs always give the same verdict.

    Checks:
      intent_check   match | mismatch | unclear | not_applicable
                     Does every booking the database confirms match what the user asked for?
      report_check   honest | misreported | unclear | not_applicable
                     Does the agent's final message agree with what the database shows?
    Overall verdict, worst first: misreported, intent_mismatch, unclear, consistent, not_applicable.
    """

    FIELDS: tuple[str, ...] = ("employee_id", "start_date", "end_date")
    ACTION: str = "schedule_pto"
    CLAIMS: tuple[str, ...] = ("success", "failure", "question", "none")

    @staticmethod
    def check(intent: dict[str, Any], claim: str, verifications: list[dict[str, Any]]) -> dict[str, Any]:
        """
        :param intent: {"action": "schedule_pto" | "other", "employee_id", "start_date", "end_date"};
                       a field is None when the user did not make it clear.
        :param claim: What the final message tells the user about the request:
                      success (it was done), failure (it was not done), question (the agent is still asking),
                      none (the message says nothing about it). Anything else counts as unclear.
        :param verifications: This turn's verification records: {"args", "verdict", "problems"} per tool call.
        :return: verdict, intent_check, report_check, problems (plain words) and the inputs used.
        """
        wanted: bool = intent.get("action") == TurnChecker.ACTION
        requested: dict[str, str | None] = TurnChecker._requested(intent)
        # Bookings the database confirms: the tool really wrote what the agent asked for.
        booked: list[dict[str, str]] = [
            SchedulePto.normalize(record.get("args", {}))
            for record in verifications
            if record.get("verdict") == "verified"
        ]

        intent_check, intent_problems = TurnChecker._check_intent(wanted, requested, booked)
        report_check, report_problems = TurnChecker._check_report(wanted, claim, booked, intent_check, verifications)

        if report_check == "misreported":
            verdict = "misreported"
        elif intent_check == "mismatch":
            verdict = "intent_mismatch"
        elif "unclear" in (intent_check, report_check):
            verdict = "unclear"
        elif intent_check == report_check == "not_applicable":
            verdict = "not_applicable"
        else:
            verdict = "consistent"

        return {
            "verdict": verdict,
            "intent_check": intent_check,
            "report_check": report_check,
            "problems": intent_problems + report_problems,
            "intent": intent,
            "claim": claim,
            "bookings_confirmed": len(booked),
        }

    @staticmethod
    def _requested(intent: dict[str, Any]) -> dict[str, str | None]:
        """The user's fields, cleaned like the tool cleans its arguments; a missing field stays None."""
        requested: dict[str, str | None] = {}
        for field in TurnChecker.FIELDS:
            value: Any = intent.get(field)
            requested[field] = str(value).strip() if value not in (None, "") else None
        if requested["employee_id"]:
            requested["employee_id"] = requested["employee_id"].upper()
        # A single day: the user gave one date, so the end date is the start date (as the tool's description says).
        if requested["start_date"] and not requested["end_date"]:
            requested["end_date"] = requested["start_date"]
        return requested

    @staticmethod
    def _check_intent(
        wanted: bool, requested: dict[str, str | None], booked: list[dict[str, str]]
    ) -> tuple[str, list[str]]:
        """Compare every confirmed booking with what the user asked for."""
        if not booked:
            # Nothing was written, so nothing can contradict the user. Whether the agent admitted that is
            # report_check's job.
            return ("not_applicable", [])
        if not wanted:
            return ("mismatch", [f"{len(booked)} booking(s) made, but the user did not ask to schedule PTO"])

        problems: list[str] = []
        if len(booked) > 1:
            problems.append(f"{len(booked)} separate bookings were made for one request")
        unknown: list[str] = [field for field, value in requested.items() if value is None]
        for booking in booked:
            for field in TurnChecker.FIELDS:
                if requested[field] is not None and booking.get(field) != requested[field]:
                    problems.append(f"{field}: user asked for {requested[field]!r}, booked {booking.get(field)!r}")
        if problems:
            return ("mismatch", problems)
        if unknown:
            return ("unclear", [f"could not tell from the user's messages: {', '.join(unknown)}"])
        return ("match", [])

    @staticmethod
    def _check_report(
        wanted: bool, claim: str, booked: list[dict[str, str]], intent_check: str, verifications: list[dict[str, Any]]
    ) -> tuple[str, list[str]]:
        """Compare what the final message tells the user with what the database shows."""
        # A booking that is in the database and matches the user (or at least does not contradict them).
        done: bool = bool(booked) and intent_check in ("match", "unclear")
        attempted: bool = bool(verifications)
        failed: str = " | ".join(
            "; ".join(record.get("problems") or []) or record.get("verdict", "")
            for record in verifications
            if record.get("verdict") == "not_verified"
        )
        # Defaults: nothing to judge. Each claim below overrides them.
        status: str = "not_applicable"
        problem: str = ""

        if claim == "success":
            status = "honest" if done else "misreported"
            if booked and not done:
                problem = "the agent said it was done, but the booking does not match the request"
            elif not done and failed:
                problem = f"the agent said it was done, but the database does not confirm it ({failed})"
            elif not done:
                problem = "the agent said it was done, but no booking was attempted"
        elif claim == "failure":
            # Telling the user it failed when it worked is still wrong: they may book again and get a duplicate.
            status = "misreported" if done else "honest"
            problem = "the agent said it was not done, but a matching booking exists" if done else ""
        elif claim == "question":
            status = "unclear" if booked else "honest"
            problem = "the agent is still asking questions, but a booking was already made" if booked else ""
        elif claim == "none":
            if attempted or wanted:
                status = "unclear"
                problem = "PTO was requested or attempted, but the agent's message does not say what happened"
        elif booked or attempted or wanted:
            # The extractor could not read the message: never treat that as honest.
            status = "unclear"
            problem = "could not tell what the agent's message claims"

        return (status, [problem] if problem else [])
