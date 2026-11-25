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
import uuid
from logging import Logger
from logging import getLogger
from pathlib import Path
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command
from task_verification.pto_provenance.anchor_log import AnchorLog
from task_verification.pto_provenance.coded_tools.schedule_pto import SchedulePto
from task_verification.pto_provenance.hr_database import HrDatabase
from task_verification.pto_provenance.idempotency_context import IdempotencyContext
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph
from task_verification.pto_provenance.pto_verifier import PtoVerifier


class ProvenanceMiddleware(AgentMiddleware):
    """
    Wraps each schedule-PTO call: gives it an idempotency key, records it in the provenance graph, checks the
    database afterwards and anchors the graph's newest hash in the anchor log.

    For each watched call, three nodes go on the employee's branch, all carrying the same key:
      tool_call     what the agent asked for
      tool_reply    what the tool told the agent
      verification  what the database shows (PtoVerifier), also linked to its tool_call
    The verdict is not given to the agent: the tool's reply goes back unchanged.
    If the tool raises, no reply or verification is written; the call stays in graph.pending().
    Assumption (not yet checked in a real neuro-san run): the key set here reaches the tool through the ContextVar.
    If it does not, the tool raises "No idempotency key", so the failure is loud, not silent.
    """

    LIVE_RECORD: Path = Path(__file__).parent / "runs" / "live_record.json"  # the newest graph, rewritten each call

    def __init__(self, tools: list[str] | None = None) -> None:
        """:param tools: Names of the tools to watch (from the network's HOCON). Other calls pass straight through."""
        self.logger: Logger = getLogger(__name__)
        # Not "self.tools": langchain's AgentMiddleware uses that name for extra tools a middleware adds to the agent.
        self.watched_tools: set[str] = set(tools or [])

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """
        Called by langchain for every tool call the agent makes.

        :param request: The agent's tool call.
        :param handler: Runs the tool.
        :return: The tool's result, unchanged.
        """
        # 1. Not a tool we watch: run it and record nothing.
        name: str = request.tool_call.get("name", "")
        if name not in self.watched_tools:
            return await handler(request)

        # 2. Work out where this call goes in the graph, and give it a key the agent never sees.
        # This session's graph. A runner starts one per session; in the studio UI nothing does, so the first
        # watched call starts it (one graph per server start).
        try:
            graph: ProvenanceGraph = ProvenanceGraph.active()
        except RuntimeError:
            graph = ProvenanceGraph.reset()
        args: dict[str, Any] = request.tool_call.get("args", {})  # what the agent asked for
        user: str = SchedulePto.normalize(args).get("employee_id", "")  # the branch, cleaned like the tool cleans it
        key: str = str(uuid.uuid4())  # random, made here, so the agent cannot choose or reuse one

        # 3. Record the request before running anything, so a crash still leaves a trace that a call was made.
        call_data: dict[str, Any] = {"idempotency_key": key, "args": args, "llm_call_id": request.tool_call.get("id")}
        call: str = graph.extend(user, name, "tool_call", call_data)

        # 4. Hand the key to the tool and run it. "finally" clears the key even if the tool raises,
        #    so it cannot leak into the next call.
        token = IdempotencyContext.KEY.set(key)
        try:
            result: ToolMessage | Command[Any] = await handler(request)
        finally:
            IdempotencyContext.KEY.reset(token)

        # 5. Record what the tool told the agent, as text.
        #    isinstance because langchain returns one of two unrelated types here (as in tool_policy_guard.py).
        reply: str = str(result.content) if isinstance(result, ToolMessage) else str(result)
        graph.extend(user, name, "tool_reply", {"idempotency_key": key, "reply": reply})

        # 6. Check the database: read the rows under this key (read-only connection), compare with the request.
        rows: list[dict[str, Any]] = await asyncio.to_thread(HrDatabase.requests_with_key, key)
        verdict: dict[str, Any] = PtoVerifier.check(args, reply, rows)

        # 7. Record the verdict, linked back to the call it checked, then anchor the graph's newest hash outside it.
        graph.extend(user, name, "verification", {"idempotency_key": key, **verdict, "rows": rows}, also=[call])
        AnchorLog.record(graph.run_id, graph.head())
        # Save the whole graph after every verification, so a separate process (the terminal verifier) can read it.
        self.LIVE_RECORD.parent.mkdir(exist_ok=True)
        graph.save(self.LIVE_RECORD)
        self.logger.info("PTO call %s: %s %s", key, verdict.get("verdict"), verdict.get("problems"))

        # 8. Give the agent the tool's result untouched: the verdict is for the record, not for the agent.
        return result
