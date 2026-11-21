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

import pytest
from task_verification.pto_provenance.pto_verifier import PtoVerifier


class TestPtoVerifier:
    """
    The verifier on its own: made-up tool replies and database rows, no tool or database involved.
    Every case is a request for E-1042 on 2026-12-03.
    """

    REQUEST: dict[str, str] = {"employee_id": "E-1042", "start_date": "2026-12-03", "end_date": "2026-12-03"}
    SUCCESS: str = "{'status': 'submitted', 'employee_id': 'E-1042'}"
    ERROR: str = "Error: HR system unavailable, request not submitted."
    ROW: dict[str, Any] = {"request_id": 1, "idempotency_key": "test-key-1", "status": "submitted", **REQUEST}

    @pytest.mark.parametrize(
        "case, reply, rows, verdict, problem",
        [
            ("written correctly", SUCCESS, [ROW], "verified", None),
            ("no_write", SUCCESS, [], "not_verified", "tool reported success but no row was written"),
            (
                "wrong_dates",
                SUCCESS,
                [{**ROW, "start_date": "2026-12-31", "end_date": "2026-12-31"}],
                "not_verified",
                "start_date: requested '2026-12-03', written '2026-12-31'",
            ),
            (
                "wrong_employee",
                SUCCESS,
                [{**ROW, "employee_id": "E-2077"}],
                "not_verified",
                "employee_id: requested 'E-1042', written 'E-2077'",
            ),
            (
                "wrong end date only",
                SUCCESS,
                [{**ROW, "end_date": "2026-12-04"}],
                "not_verified",
                "end_date: requested '2026-12-03', written '2026-12-04'",
            ),
            (
                "duplicate",
                SUCCESS,
                [ROW, {**ROW, "request_id": 2}],
                "not_verified",
                "2 rows share one idempotency key",
            ),
            ("honest error", ERROR, [], "failure_confirmed", None),
            (
                "error, but a row was written",
                ERROR,
                [ROW],
                "not_verified",
                "tool reported an error but a row was written",
            ),
        ],
    )
    def test_verdicts(
        self, case: str, reply: str, rows: list[dict[str, Any]], verdict: str, problem: str | None
    ) -> None:
        """Each situation gets the expected verdict, and a failed check names its problem."""
        result = PtoVerifier.check(self.REQUEST, reply, rows)
        assert result.get("verdict") == verdict, case
        if problem is None:
            assert result.get("problems") == [], case
        else:
            assert problem in result.get("problems"), (case, result.get("problems"))

    def test_messy_request_matches_cleaned_row(self) -> None:
        """The agent asked for " e-1042 "; the tool wrote E-1042. Same person, so this must not count as a mismatch."""
        messy = {**self.REQUEST, "employee_id": " e-1042 "}
        assert PtoVerifier.check(messy, self.SUCCESS, [self.ROW]).get("verdict") == "verified"
