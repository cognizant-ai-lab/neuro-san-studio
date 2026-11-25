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
import select
import sys
import termios
import tty
from typing import Any

from task_verification.pto_provenance.anchor_log import AnchorLog
from task_verification.pto_provenance.fault_switch import FaultSwitch
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph
from task_verification.pto_provenance.provenance_middleware import ProvenanceMiddleware
from task_verification.pto_provenance.pto_verifier import PtoVerifier


class VerifierConsole:
    """
    The demo's verifier screen: a terminal next to the studio UI that shows every PTO booking as it is verified.

    It is a separate process from the agents. It reads only the record the middleware saves, the anchor log and the
    HR database (read-only), and writes only the fault file. For each call it shows what was asked, what the tool
    told the agent, what the database holds and the verdict; it re-checks the verdict against the database and the
    record against the anchor itself. Keys 1-6 switch the fault the tool fakes, q quits.

    Usage, from the repo root (macOS or Linux terminal; it reads single key presses):
        python -m task_verification.pto_provenance.verifier_console
    Starting it resets the HR database and the fault to "none". The record lives in the agent server's memory, so
    restart the server for a fresh record.
    """

    KEYS: dict[str, str] = {str(number): fault for number, fault in enumerate(FaultSwitch.DESCRIPTIONS, start=1)}
    REFRESH_SECONDS: float = 0.5
    GREEN, RED, BOLD, DIM, RESET = "\033[32m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"

    def __init__(self) -> None:
        """Nothing drawn yet."""
        self.drawn: tuple[str | None, str] | None = None  # (record head, fault) on screen, to redraw only on change

    def start(self) -> None:
        """A clean slate for the demo: an empty database, no fault, and no old record on screen."""
        HrDatabase.reset()
        FaultSwitch.set("none")
        ProvenanceMiddleware.LIVE_RECORD.unlink(missing_ok=True)

    def run(self) -> None:
        """Redraw whenever the record or the fault changes, and react to key presses, until q."""
        saved_terminal: list[Any] = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())  # deliver each key press at once, without waiting for Enter
        try:
            while True:
                key: str | None = self.read_key()
                if key == "q":
                    break
                if key in self.KEYS:
                    FaultSwitch.set(self.KEYS.get(key))
                self.refresh()
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, saved_terminal)  # give the terminal back as it was

    def read_key(self) -> str | None:
        """:return: The key pressed within the next REFRESH_SECONDS, or None."""
        ready, _, _ = select.select([sys.stdin], [], [], self.REFRESH_SECONDS)
        return sys.stdin.read(1) if ready else None

    def refresh(self) -> None:
        """Read the saved record and redraw the screen if anything changed."""
        graph: ProvenanceGraph | None = None
        if ProvenanceMiddleware.LIVE_RECORD.exists():
            try:
                graph = ProvenanceGraph.load(ProvenanceMiddleware.LIVE_RECORD)
            except json.JSONDecodeError:
                return  # caught while the middleware was writing it; the next refresh reads it whole
        state: tuple[str | None, str] = (graph.head() if graph else None, FaultSwitch.current())
        if state != self.drawn:
            self.drawn = state
            print("\033[2J\033[H" + self.render(graph), end="", flush=True)  # clear the screen, then draw

    def render(self, graph: ProvenanceGraph | None) -> str:
        """:return: The whole screen as text: the fault legend, the record check, then one block per call."""
        lines: list[str] = [
            f"{self.BOLD}PTO VERIFIER{self.RESET}  {self.DIM}separate process: reads the saved record"
            f" and the HR database, never talks to the agent{self.RESET}",
            "",
            f"{self.BOLD}Fault the tool fakes{self.RESET}  (press 1-6 to switch, q to quit)",
        ]
        for key, fault in self.KEYS.items():
            on: bool = fault == FaultSwitch.current()
            mark: str = f"{self.BOLD}> " if on else "  "
            lines.append(
                f"{mark}{key} {fault:<15}{self.RESET}{self.DIM}{FaultSwitch.DESCRIPTIONS.get(fault)}{self.RESET}"
            )
        lines.append("")
        if graph is None:
            lines.append("Waiting for the first ScheduleLeaveAPI call...")
            return "\n".join(lines) + "\n"

        intact: bool = graph.intact(anchor=AnchorLog.latest(graph.run_id))
        check: str = f"{self.GREEN}intact against the anchor" if intact else f"{self.RED}TAMPERED or out of step"
        lines.append(f"{self.BOLD}Record{self.RESET} {len(graph.nodes)} nodes, {check}{self.RESET}")
        verifications: list[dict[str, Any]] = [n for n in graph.nodes if n.get("kind") == "verification"]
        for number, verification in enumerate(verifications, start=1):
            lines += [""] + self.describe(graph, verification, number)
        return "\n".join(lines) + "\n"

    def describe(self, graph: ProvenanceGraph, verification: dict[str, Any], number: int) -> list[str]:
        """:return: The lines for one call: asked, tool said, database, verdict, and the re-check."""
        data: dict[str, Any] = verification.get("data", {})
        key: str = data.get("idempotency_key")
        # A verification's last parent is the tool_call it checked; its tool_reply carries the same key.
        call: dict[str, Any] = next(n for n in graph.nodes if n.get("hash") == verification.get("parents")[-1])
        reply: str = next(
            n.get("data").get("reply")
            for n in graph.nodes
            if n.get("kind") == "tool_reply" and n.get("data").get("idempotency_key") == key
        )
        args: dict[str, Any] = call.get("data").get("args")
        rows: str = (
            "; ".join(f"{r.get('employee_id')} {r.get('start_date')} to {r.get('end_date')}" for r in data.get("rows"))
            or "no row"
        )
        verdict: str = data.get("verdict")
        color: str = self.GREEN if verdict in ("verified", "failure_confirmed") else self.RED
        # Independent re-check: look the key up in the database again now, and judge it again.
        again: str = PtoVerifier.check(args, reply, HrDatabase.requests_with_key(key)).get("verdict")
        agrees: str = (
            "agrees" if again == verdict else f"{self.RED}now says {again} (database changed since){self.RESET}"
        )
        return [
            f"{self.BOLD}Call {number}{self.RESET}  {verification.get('time', '')[11:19]} UTC",
            f"  asked      {args.get('employee_id')} {args.get('start_date')} to {args.get('end_date')}",
            f"  tool said  {reply[:90]}",
            f"  database   {rows}",
            f"  verdict    {color}{self.BOLD}{verdict.upper().replace('_', ' ')}{self.RESET}"
            + "".join(f"\n             {color}{problem}{self.RESET}" for problem in data.get("problems")),
            f"  re-check   {agrees}",
        ]

    @staticmethod
    def main() -> None:
        """Reset the demo state, then show the screen until q."""
        console = VerifierConsole()
        console.start()
        console.run()


if __name__ == "__main__":
    VerifierConsole.main()
