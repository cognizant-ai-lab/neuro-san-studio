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

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from task_verification.pto_provenance.hr_database import HrDatabase


class TestHrDatabaseReset:  # pylint: disable=too-few-public-methods
    """Every experiment starts from reset(), so it must leave exactly the seed state, whatever was there before."""

    def test_reset_clears_requests_keeps_employees(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Write a request, reset: no requests left, and the two seed employees are back."""
        monkeypatch.setattr(HrDatabase, "PATH", tmp_path / "hr.db")
        HrDatabase.reset()
        HrDatabase.add_request("test-key-1", "E-1042", "2026-12-03", "2026-12-03")

        HrDatabase.reset()

        with closing(sqlite3.connect(HrDatabase.PATH)) as db:
            requests = db.execute("SELECT COUNT(*) FROM pto_requests").fetchone()[0]
            employees = db.execute("SELECT employee_id FROM employees ORDER BY employee_id").fetchall()
        assert requests == 0
        assert employees == [("E-1042",), ("E-2077",)]
