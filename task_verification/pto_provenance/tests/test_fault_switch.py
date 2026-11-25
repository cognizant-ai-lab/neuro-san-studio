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

from pathlib import Path

import pytest
from task_verification.pto_provenance.fault_switch import FaultSwitch
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph


class TestFaultSwitch:
    """Where the tool's fault comes from, and that a saved record can be read back and checked by another process."""

    @pytest.fixture(autouse=True)
    def temporary_folder(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Runs before each test: the database (and so the fault file) in a throwaway folder, no PTO_FAULT set."""
        monkeypatch.setattr(HrDatabase, "PATH", tmp_path / "hr.db")
        monkeypatch.delenv("PTO_FAULT", raising=False)

    def test_environment_beats_file_beats_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Nothing set: none. The verifier's file: its fault. PTO_FAULT (the runner) always wins over the file."""
        assert FaultSwitch.current() == "none"
        FaultSwitch.set("no_write")
        assert FaultSwitch.current() == "no_write"
        monkeypatch.setenv("PTO_FAULT", "duplicate")
        assert FaultSwitch.current() == "duplicate"

    def test_unknown_fault_is_refused(self) -> None:
        """A typo cannot be written to the file, so the demo cannot silently run with a fault that does not exist."""
        with pytest.raises(ValueError, match="Unknown fault 'nowrite'"):
            FaultSwitch.set("nowrite")
        assert not FaultSwitch.path().exists()

    def test_saved_record_loads_and_checks(self, tmp_path: Path) -> None:
        """What the terminal verifier does: load the graph the middleware saved and run the integrity check on it."""
        graph = ProvenanceGraph()
        graph.extend("E-1042", "ScheduleLeaveAPI", "tool_call", {"idempotency_key": "k"})
        graph.save(tmp_path / "record.json")

        loaded = ProvenanceGraph.load(tmp_path / "record.json")
        assert loaded.run_id == graph.run_id
        assert loaded.head() == graph.head()
        assert loaded.intact(anchor=graph.head())
