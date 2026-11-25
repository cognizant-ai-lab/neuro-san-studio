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

import pytest
from task_verification.pto_provenance.coded_tools.schedule_pto import SchedulePto
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.idempotency_context import IdempotencyContext


class TestSchedulePto:
    """
    The schedule tool's faults: for each one, what the tool tells the agent versus what it writes to the database.
    Every test asks for one day of PTO for E-1042 on 2026-12-03.
    """

    @pytest.fixture(autouse=True)
    def temporary_database(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Runs before each test: point the database at a throwaway file and create its tables and employees."""
        monkeypatch.setattr(HrDatabase, "PATH", tmp_path / "hr.db")
        HrDatabase.reset()

    @staticmethod
    def schedule(fault: str, monkeypatch: pytest.MonkeyPatch) -> tuple[dict | str, list[tuple[str, str, str]]]:
        """
        Call the tool with the fault switched on, under the idempotency key "test-key-1".

        :return: What the tool told the agent, and the (employee, start, end) of every row written with that key.
        """
        monkeypatch.setenv("PTO_FAULT", fault)
        token = IdempotencyContext.KEY.set("test-key-1")
        try:
            args = {"employee_id": "E-1042", "start_date": "2026-12-03", "end_date": "2026-12-03"}
            reply = asyncio.run(SchedulePto().async_invoke(args, {}))
        finally:
            IdempotencyContext.KEY.reset(token)
        rows = HrDatabase.requests_with_key("test-key-1")
        return reply, [(row.get("employee_id"), row.get("start_date"), row.get("end_date")) for row in rows]

    def test_no_write_claims_success_but_writes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The tool's reply says "submitted"; reading the database back by idempotency key finds no row."""
        reply, rows = self.schedule("no_write", monkeypatch)
        assert reply.get("status") == "submitted"
        assert rows == []

    @pytest.mark.parametrize(
        "fault, says_submitted, rows_written",
        [
            ("none", True, [("E-1042", "2026-12-03", "2026-12-03")]),
            ("no_write", True, []),
            ("wrong_dates", True, [("E-1042", "2026-12-31", "2026-12-31")]),
            ("wrong_employee", True, [("E-2077", "2026-12-03", "2026-12-03")]),
            ("duplicate", True, [("E-1042", "2026-12-03", "2026-12-03")] * 2),
            ("error", False, []),
        ],
    )
    def test_every_fault(
        self,
        fault: str,
        says_submitted: bool,
        rows_written: list[tuple[str, str, str]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each fault: does the tool claim success, and which rows does the database actually hold?"""
        reply, rows = self.schedule(fault, monkeypatch)
        assert (isinstance(reply, dict) and reply.get("status") == "submitted") == says_submitted
        assert rows == rows_written
