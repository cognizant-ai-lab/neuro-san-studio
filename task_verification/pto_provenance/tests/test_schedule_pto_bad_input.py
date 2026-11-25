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
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from task_verification.pto_provenance.coded_tools.schedule_pto import SchedulePto
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.idempotency_context import IdempotencyContext


class TestSchedulePtoBadInput:
    """How the schedule tool handles input it should not accept as given: no key, unknown or messy ids, bad faults."""

    GOOD_ARGS: dict[str, str] = {"employee_id": "E-1042", "start_date": "2026-12-03", "end_date": "2026-12-03"}

    @pytest.fixture(autouse=True)
    def temporary_database(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Runs before each test: point the database at a throwaway file, create its tables, no fault switched on."""
        monkeypatch.setattr(HrDatabase, "PATH", tmp_path / "hr.db")
        monkeypatch.delenv("PTO_FAULT", raising=False)
        HrDatabase.reset()

    @staticmethod
    def schedule(args: dict[str, str], key: str | None = "test-key-1") -> Any:
        """Call the tool with these arguments, under the given idempotency key (None = no key set)."""
        token = IdempotencyContext.KEY.set(key)
        try:
            return asyncio.run(SchedulePto().async_invoke(args, {}))
        finally:
            IdempotencyContext.KEY.reset(token)

    @staticmethod
    def count_requests() -> int:
        """:return: How many PTO requests the database holds in total, whatever their key."""
        with closing(sqlite3.connect(HrDatabase.PATH)) as db:
            return db.execute("SELECT COUNT(*) FROM pto_requests").fetchone()[0]

    def test_refuses_to_run_without_a_key(self) -> None:
        """No idempotency key: the tool raises instead of writing a row nothing could trace back to a call."""
        with pytest.raises(ValueError, match="No idempotency key"):
            self.schedule(self.GOOD_ARGS, key=None)
        assert self.count_requests() == 0

    def test_unknown_employee_gets_an_honest_error(self) -> None:
        """E-9999 is not in the employees table: the tool tells the agent so, and nothing is written."""
        reply = self.schedule({**self.GOOD_ARGS, "employee_id": "E-9999"})
        assert reply == "Error: unknown employee 'E-9999', request not submitted."
        assert self.count_requests() == 0

    def test_messy_employee_id_is_normalized(self) -> None:
        """Stray spaces and lower case (" e-1042 ") are cleaned to E-1042 before writing, so the row is correct."""
        reply = self.schedule({**self.GOOD_ARGS, "employee_id": " e-1042 ", "start_date": " 2026-12-03"})
        assert reply.get("employee_id") == "E-1042"
        assert HrDatabase.requests_with_key("test-key-1")[0].get("employee_id") == "E-1042"
        assert HrDatabase.requests_with_key("test-key-1")[0].get("start_date") == "2026-12-03"

    def test_misspelled_fault_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A misspelled fault ("nowrite") is rejected with an error instead of silently running with no fault."""
        monkeypatch.setenv("PTO_FAULT", "nowrite")
        with pytest.raises(ValueError, match="Unknown PTO_FAULT 'nowrite'"):
            self.schedule(self.GOOD_ARGS)
        assert self.count_requests() == 0
