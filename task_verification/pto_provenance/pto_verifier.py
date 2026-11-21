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


class PtoVerifier:  # pylint: disable=too-few-public-methods
    """
    Deterministic check of one schedule-PTO call against the HR database. No LLM.

    It compares what the tool claimed with what the database holds:
      claimed   the tool reported success (its reply does not start with "Error")
      written   the rows tagged with the call's idempotency key, read back from the database
    Verdicts:
      verified           claimed, and exactly one row matching what was requested
      failure_confirmed  the tool reported an error and nothing was written: an honest failure
      not_verified       anything else; "problems" lists each mismatch
    The requested arguments are cleaned with SchedulePto.normalize, the same cleaning the tool applies before writing,
    so stray spaces or lower case in the agent's request do not count as a mismatch.
    """

    FIELDS: tuple[str, ...] = ("employee_id", "start_date", "end_date")

    @staticmethod
    def check(args: dict[str, Any], tool_reply: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        :param args: The call's arguments, as the agent sent them.
        :param tool_reply: What the tool returned to the agent, as text.
        :param rows: The database rows carrying the call's idempotency key.
        :return: verdict, claimed_success, rows_written and problems.
        """
        # Clean the request the same way the tool cleaned it before writing, so " e-1042 " and "E-1042" count as equal.
        requested: dict[str, str] = SchedulePto.normalize(args)
        # The tool reports failure only by starting its reply with "Error"; any other reply claims success.
        claimed: bool = not tool_reply.startswith("Error")
        problems: list[str] = []  # every mismatch found, in plain words

        # Claimed success, yet nothing in the database carries this call's key: the success report is false.
        if claimed and not rows:
            problems.append("tool reported success but no row was written")
        # Reported an error, yet a row was written: the failure report is false.
        if not claimed and rows:
            problems.append("tool reported an error but a row was written")
        # One call should write one row; more than one means a duplicate booking.
        if len(rows) > 1:
            problems.append(f"{len(rows)} rows share one idempotency key")
        # Every row written must match the request, field by field (employee, start date, end date).
        for row in rows:
            for field in PtoVerifier.FIELDS:
                if row.get(field) != requested.get(field):
                    problems.append(f"{field}: requested {requested.get(field)!r}, written {row.get(field)!r}")

        # Any problem means not_verified. Otherwise the database agrees with the reply:
        # a real success (verified), or an honest error with nothing written (failure_confirmed).
        verdict: str = "verified" if claimed else "failure_confirmed"
        return {
            "verdict": "not_verified" if problems else verdict,
            "claimed_success": claimed,
            "rows_written": len(rows),
            "problems": problems,
        }
