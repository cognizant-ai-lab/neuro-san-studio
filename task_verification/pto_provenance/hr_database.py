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
from typing import Any


class HrDatabase:
    """
    Spoof HR system of record: employees and their PTO requests in one SQLite file.

    Only the schedule_pto tool writes (add_request). The verifier reads through requests_with_key(), which opens
    a separate read-only connection, so the verifier cannot change what it is checking.
    """

    PATH: Path = Path(__file__).parent / "runs" / "hr.db"
    SCHEMA: str = """
        CREATE TABLE employees (employee_id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE pto_requests (
            request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT NOT NULL,
            employee_id     TEXT NOT NULL REFERENCES employees(employee_id),
            start_date      TEXT NOT NULL,
            end_date        TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'submitted',
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        );
    """
    EMPLOYEES: list[tuple[str, str]] = [("E-1042", "Jane Doe"), ("E-2077", "Sam Lee")]

    @classmethod
    def reset(cls) -> None:
        """Delete and re-seed the database, so every run starts from the same state."""
        cls.PATH.parent.mkdir(exist_ok=True)
        cls.PATH.unlink(missing_ok=True)
        # closing() closes the connection; the inner "with db" commits (or rolls back on error).
        with closing(sqlite3.connect(cls.PATH)) as db:
            with db:
                db.executescript(cls.SCHEMA)
                db.executemany("INSERT INTO employees VALUES (?, ?)", cls.EMPLOYEES)

    @classmethod
    def add_request(cls, key: str, employee_id: str, start_date: str, end_date: str) -> int:
        """Write one PTO request tagged with the idempotency key. :return: its request_id."""
        with closing(sqlite3.connect(cls.PATH)) as db:
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                cursor = db.execute(
                    "INSERT INTO pto_requests (idempotency_key, employee_id, start_date, end_date)"
                    " VALUES (?, ?, ?, ?)",
                    (key, employee_id, start_date, end_date),
                )
            return cursor.lastrowid

    @classmethod
    def requests_with_key(cls, key: str) -> list[dict[str, Any]]:
        """Read-only: every row tagged with this key. A correct write leaves exactly one."""
        with closing(sqlite3.connect(f"file:{cls.PATH}?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM pto_requests WHERE idempotency_key = ?", (key,))
            return [dict(row) for row in rows]
