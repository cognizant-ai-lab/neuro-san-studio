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

import os
from pathlib import Path

from task_verification.pto_provenance.hr_database import HrDatabase


class FaultSwitch:
    """
    Which failure the schedule tool fakes, so the verifier can be shown catching it.

    Where the fault comes from, first match wins:
      1. the environment variable PTO_FAULT (the runner sets it per session);
      2. the file fault.txt next to the HR database (the terminal verifier writes it, so the fault can change while
         the agent server keeps running);
      3. otherwise "none".
    The file sits next to the database, so tests that move the database to a temporary folder move it too.
    """

    DESCRIPTIONS: dict[str, str] = {
        "none": "the tool works: writes the booking as asked and says 'submitted'",
        "no_write": "the tool writes nothing, but tells the agent 'submitted'",
        "wrong_dates": "the tool writes Dec 31 instead of the requested dates, but reports the requested ones",
        "wrong_employee": "the tool books employee E-2077 instead, but reports the requested employee",
        "duplicate": "the tool writes the booking twice, and says 'submitted' once",
        "error": "the tool honestly reports an error and writes nothing",
    }

    @classmethod
    def path(cls) -> Path:
        """:return: The fault file, next to the HR database."""
        return HrDatabase.PATH.with_name("fault.txt")

    @classmethod
    def current(cls) -> str:
        """:return: The fault in force right now (not checked against DESCRIPTIONS; the tool does that)."""
        if os.environ.get("PTO_FAULT"):
            return os.environ.get("PTO_FAULT")
        if cls.path().exists():
            return cls.path().read_text(encoding="utf-8").strip()
        return "none"

    @classmethod
    def set(cls, fault: str) -> None:
        """:param fault: One of DESCRIPTIONS. :raises ValueError: For an unknown fault."""
        if fault not in cls.DESCRIPTIONS:
            raise ValueError(f"Unknown fault {fault!r}; expected one of {sorted(cls.DESCRIPTIONS)}.")
        cls.path().parent.mkdir(exist_ok=True)
        cls.path().write_text(fault, encoding="utf-8")
