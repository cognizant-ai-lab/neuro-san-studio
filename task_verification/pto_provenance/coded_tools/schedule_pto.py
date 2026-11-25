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
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from task_verification.pto_provenance.fault_switch import FaultSwitch
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.idempotency_context import IdempotencyContext


class SchedulePto(CodedTool):
    """
    Schedules PTO: writes one row to the HR database, tagged with the idempotency key from the middleware.

    FaultSwitch picks one failure to fake, to test the verifier (PTO_FAULT, else the fault file, else none):
      no_write        report success, write nothing
      wrong_dates     write a different date than requested
      wrong_employee  write a different employee than requested
      duplicate       write the row twice
      error           report an error, write nothing
    In every fault except "error" the tool still reports success with the requested details, so the agent
    cannot tell anything went wrong. Only the database shows it. An unknown PTO_FAULT value raises, so a typo in an
    experiment's setup cannot silently run without its fault.
    """

    FAULTS: frozenset[str] = frozenset(FaultSwitch.DESCRIPTIONS)

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """
        :param args: employee_id, start_date and end_date, as chosen by the agent.
        :param sly_data: Unused.
        :return: A success confirmation, or an error string (the "error" fault, or an unknown employee).
        """
        # The key comes from the middleware, never from the agent's arguments. Without a key, the row written below
        # could not be traced back to the call that made it, so refuse to run at all.
        key: str | None = IdempotencyContext.KEY.get()
        if key is None:
            raise ValueError("No idempotency key: schedule_pto must run under ProvenanceMiddleware.")

        # Which failure to fake right now (default: none). A misspelled fault raises instead of silently
        # meaning "no fault".
        fault: str = FaultSwitch.current()
        if fault not in self.FAULTS:
            raise ValueError(f"Unknown PTO_FAULT {fault!r}; expected one of {sorted(self.FAULTS)}.")

        # Tidy what the agent sent (trim spaces, upper-case the employee id) before using it.
        clean: dict[str, str] = self.normalize(args)
        employee_id: str = clean.get("employee_id", "")
        start_date: str = clean.get("start_date", "")
        end_date: str = clean.get("end_date", "")

        # Fault "error": an honest failure. Say so, write nothing.
        if fault == "error":
            return "Error: HR system unavailable, request not submitted."

        # What actually goes into the database: normally exactly what was asked for.
        # The wrong_dates and wrong_employee faults swap in a wrong value here.
        written: tuple[str, str, str] = (employee_id, start_date, end_date)
        if fault == "wrong_dates":
            written = (employee_id, "2026-12-31", "2026-12-31")
        if fault == "wrong_employee":
            written = ("E-2077", start_date, end_date)

        try:
            # Write the row, tagged with the key. Fault "no_write" skips this but still reports success below.
            if fault != "no_write":
                await asyncio.to_thread(HrDatabase.add_request, key, *written)
            # Fault "duplicate": write the same row a second time.
            if fault == "duplicate":
                await asyncio.to_thread(HrDatabase.add_request, key, *written)
        except sqlite3.IntegrityError:
            # The employees table does not know this id (foreign key), so nothing was written.
            return f"Error: unknown employee {employee_id!r}, request not submitted."

        # Report success with the *requested* details, even if a fault changed or skipped the write.
        # So the agent cannot tell from this reply that anything went wrong; only the database shows it.
        return {"status": "submitted", "employee_id": employee_id, "start_date": start_date, "end_date": end_date}

    @staticmethod
    def normalize(args: dict[str, Any]) -> dict[str, str]:
        """
        :param args: The arguments as the agent sent them.
        :return: Every value with stray whitespace trimmed, and the employee id upper-cased (" e-1042 " -> "E-1042").
        """
        # Turn every value into text and cut spaces off both ends.
        clean: dict[str, str] = {name: str(value).strip() for name, value in args.items()}
        # Employee ids are stored in capitals, so "e-1042" becomes "E-1042".
        clean["employee_id"] = clean.get("employee_id", "").upper()
        return clean
