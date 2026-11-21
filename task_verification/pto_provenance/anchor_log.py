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

import json
from datetime import datetime
from datetime import timezone
from pathlib import Path


class AnchorLog:
    """
    A log of graph heads, kept outside the graph, so that a rewritten graph can be caught.

    The graph's hash chain shows edits only to someone holding a hash from before the edit. After each verification,
    the middleware writes the graph's newest hash (head) here, one JSON line per entry. Later, intact(anchor=latest())
    fails if the graph no longer contains that hash where it was: nodes cut from the end, or nodes rewritten with
    every later hash recomputed.

    MVP assumption: this is a plain file on the same machine as the graph, and nothing stops a process with file
    access from rewriting it. In deployment it must live where the agent's process cannot write (another server,
    write-once storage), so that one compromised process cannot change both the graph and its anchors.
    """

    PATH: Path = Path(__file__).parent / "runs" / "anchors.jsonl"

    @classmethod
    def record(cls, run_id: str, head: str) -> None:
        """Add one line: when, which session, and the graph's newest hash at that moment."""
        cls.PATH.parent.mkdir(exist_ok=True)
        entry = {"time": datetime.now(timezone.utc).isoformat(), "run_id": run_id, "head": head}
        with cls.PATH.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry) + "\n")

    @classmethod
    def latest(cls, run_id: str) -> str | None:
        """:return: The last head recorded for this session, or None if there is none."""
        if not cls.PATH.exists():
            return None
        entries = [json.loads(line) for line in cls.PATH.read_text(encoding="utf-8").splitlines()]
        heads = [entry.get("head") for entry in entries if entry.get("run_id") == run_id]
        return heads[-1] if heads else None
