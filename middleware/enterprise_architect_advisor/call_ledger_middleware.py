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

"""
CallLedgerMiddleware — per-agent timing middleware for Enterprise Architect Advisor.

Records the wall-clock start and end time of each specialist agent's model-call
window and writes the results into sly_data under two keys:

  sly_data["ea_call_ledger"]
      A list of dicts, one entry per agent that ran:
      {
          "agent_name": str,          # matches the HOCON agent name
          "start_time": str,          # ISO-8601 UTC, first model-call start
          "end_time": str             # ISO-8601 UTC, last model-call end
      }

  sly_data["ea_ran_<agent_name>"]
      Boolean flag set to True when an agent completes its first model call.
      Example: sly_data["ea_ran_cloud_strategy_architect"] = True

CONCURRENCY INTERPRETATION
  If two entries in ea_call_ledger have overlapping [start_time, end_time]
  windows, those specialists executed concurrently.
  Concurrency is achieved when decision_router_agent emits all selected
  specialist tool calls as a single batched response turn rather than
  sequentially.  The updated decision_router instructions encourage this
  behaviour; whether a given LLM complies depends on the model.

USAGE IN HOCON
  Add the following middleware block inside any specialist agent definition:

      "middleware": [
          {
              "class": "middleware.enterprise_architect_advisor.call_ledger_middleware.CallLedgerMiddleware",
              "args": {
                  "agent_name": "<exact agent name>",
                  "sly_data": true
              }
          }
      ]

  The framework injects the shared sly_data dict when "sly_data": true is set.
"""

import asyncio
from datetime import datetime
from datetime import timezone
from logging import Logger
from logging import getLogger
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import AgentState

# Key used to store the asyncio lock in sly_data so all middleware instances
# share a single lock for safe concurrent writes to the ledger.
_LEDGER_LOCK_KEY = "ea_ledger_lock"
_LEDGER_KEY = "ea_call_ledger"
_RAN_PREFIX = "ea_ran_"


def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with 'Z' suffix."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


class CallLedgerMiddleware(AgentMiddleware):
    """
    AgentMiddleware that records per-specialist wall-clock execution windows
    in the shared sly_data bulletin board.

    Each instance is bound to exactly one specialist agent via the
    ``agent_name`` constructor argument.  The framework creates one instance
    per agent invocation.

    Thread / async safety:
        Multiple specialists may run concurrently on separate asyncio tasks.
        A single asyncio.Lock is stored in sly_data and shared across all
        instances to protect the ea_call_ledger list from torn writes.
    """

    def __init__(self, agent_name: str, sly_data: dict[str, Any]) -> None:
        """
        :param agent_name: The exact name of the agent whose execution this
                           middleware tracks (e.g. "cloud_strategy_architect").
        :param sly_data:   The shared sly_data dict injected by the framework
                           (HOCON arg ``"sly_data": true``).
        """
        self.agent_name: str = agent_name
        self.sly_data: dict[str, Any] = sly_data
        self.start_time: str | None = None
        self.logger: Logger = getLogger(f"CallLedgerMiddleware.{agent_name}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_lock(self) -> asyncio.Lock:
        """
        Return the shared asyncio.Lock from sly_data, creating it if absent.

        NOTE: This is intentionally NOT thread-safe for the lock-creation
        step itself.  In practice the GIL and the fact that asyncio runs on
        a single event loop make a race here extremely unlikely, and the
        consequence is merely a benign duplicate lock (one will simply be
        overwritten).
        """
        lock = self.sly_data.get(_LEDGER_LOCK_KEY)
        if lock is None:
            lock = asyncio.Lock()
            self.sly_data[_LEDGER_LOCK_KEY] = lock
        return lock

    async def _write_ledger_entry(self, end_time: str) -> None:
        """
        Under the shared lock, upsert an entry in ea_call_ledger for this agent.

        If an entry for self.agent_name already exists it is updated in place
        (updates end_time); otherwise a new entry is appended.
        """
        lock = self._get_or_create_lock()
        async with lock:
            ledger: list[dict[str, Any]] = self.sly_data.setdefault(_LEDGER_KEY, [])

            # Find existing entry for this agent (handles multi-step agents)
            existing = next(
                (e for e in ledger if e.get("agent_name") == self.agent_name),
                None,
            )
            if existing is not None:
                existing["end_time"] = end_time
            else:
                ledger.append(
                    {
                        "agent_name": self.agent_name,
                        "start_time": self.start_time or end_time,
                        "end_time": end_time,
                    }
                )

            # Also set the boolean presence flag for easy sly_data assertions.
            self.sly_data[f"{_RAN_PREFIX}{self.agent_name}"] = True

    # ------------------------------------------------------------------
    # AgentMiddleware hooks
    # ------------------------------------------------------------------

    async def abefore_model(
        self,
        state: AgentState[Any],
        runtime: Any,
    ) -> dict[str, Any] | None:
        """
        Capture the start timestamp on the first model call for this agent.
        Subsequent calls (if the agent iterates) do not reset the start time.
        """
        if self.start_time is None:
            self.start_time = _utcnow_iso()
            self.logger.debug(
                "CallLedger: agent=%s start=%s", self.agent_name, self.start_time
            )
        return None

    async def aafter_model(
        self,
        state: AgentState[Any],
        runtime: Any,
    ) -> dict[str, Any] | None:
        """
        Capture the end timestamp after each model call and upsert the ledger.
        The last call's end_time wins, giving the total agent execution window.
        """
        end_time = _utcnow_iso()
        self.logger.debug(
            "CallLedger: agent=%s end=%s", self.agent_name, end_time
        )
        await self._write_ledger_entry(end_time)
        return None
