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

from importlib import import_module
from logging import Logger
from logging import getLogger
from pathlib import Path
from typing import Any
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from neuro_san.message.utils.content_utils import ContentUtils
from task_verification.pto_provenance.anchor_log import AnchorLog
from task_verification.pto_provenance.provenance_graph import ProvenanceGraph
from task_verification.pto_provenance.turn_checker import TurnChecker
from task_verification.pto_provenance.turn_extractor import TurnExtractor


class TurnCheckMiddleware(AgentMiddleware):
    """
    Runs once at the end of every user turn, on the front-man agent, and checks the turn as a whole:
      - does what was booked match what the user asked for?   (intent_check)
      - does the agent's final message match what the database shows?   (report_check)

    It is middleware, not a tool, so the agent cannot skip it: the agent never decides whether it runs.

    Evidence comes from the provenance graph, which ProvenanceMiddleware fills from the database, not from anything
    the agents said. TurnExtractor (an LLM) only turns the user's messages and the final message into structured
    fields; TurnChecker compares those fields with the evidence deterministically.

    The result goes into the graph as a "turn_check" node, linked to the verifications it used, and is anchored like
    every other node. Next to the verdict it keeps the extracted fields (intent, claim) and an "extraction" block
    with the model and each call's raw reply. A wrong verdict can then be traced to the extraction (the fields are
    wrong) or to the graph (the fields are right, the evidence disagrees) without re-running the turn. The chat text
    itself is not copied into the graph, which is permanent; it stays in the conversation.

    When the verdict is misreported or intent_mismatch, and notify_user is on, a short notice is added to the end of
    the agent's answer, so the user sees the risk instead of a false "done".

    Relies on two behaviours of neuro-san, confirmed in live pto_runner runs (no_write and none, with Gemini):
      - the front man's state holds the user's messages as HumanMessages and its answer as the last AIMessage;
      - a message returned from aafter_agent becomes the answer the user sees (neuro-san's NetworkCopyMiddleware
        relies on the same behaviour).
    Like ProvenanceMiddleware, this keeps per-session state on the instance and in the shared ProvenanceGraph, so it
    is for one session at a time (the runner and the demo), not for concurrent users.
    """

    LIVE_RECORD: Path = Path(__file__).parent / "runs" / "live_record.json"
    FLAGGED: tuple[str, ...] = ("misreported", "intent_mismatch")

    def __init__(
        self,
        model_name: str = "claude-haiku-4-5",
        llm_class: str = "langchain_anthropic.ChatAnthropic",
        notify_user: bool = True,
    ) -> None:
        """
        :param model_name: The model TurnExtractor uses (from the network's HOCON).
        :param llm_class: Dotted path of the langchain chat model class for that model, e.g.
                          "langchain_google_genai.ChatGoogleGenerativeAI" for Gemini (key from GOOGLE_API_KEY).
        :param notify_user: Add a notice to the answer when the turn is misreported or does not match the request.
        """
        self.logger: Logger = getLogger(__name__)
        self.model_name: str = model_name
        self.llm_class: str = llm_class
        self.notify_user: bool = notify_user
        self.extractor: TurnExtractor | None = None  # made on first use; tests set it directly
        self.turn_start: tuple[str | None, int] = (None, 0)  # (graph run id, node count) when the turn began

    @override
    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        """Remember where the graph ends now, so the check afterwards looks only at this turn's tool calls."""
        try:
            graph: ProvenanceGraph = ProvenanceGraph.active()
            self.turn_start = (graph.run_id, len(graph.nodes))
        except RuntimeError:
            self.turn_start = (None, 0)  # no graph yet: the first watched call will start one
        return None

    @override
    async def aafter_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        """Check the finished turn, record the result, and warn the user if the answer is not backed by the record."""
        messages: list[BaseMessage] = list(state.get("messages") or [])
        user_messages: list[str] = [ContentUtils.flatten_to_text(m) for m in messages if isinstance(m, HumanMessage)]
        answers: list[BaseMessage] = [m for m in messages if isinstance(m, AIMessage)]
        final: str = ContentUtils.flatten_to_text(answers[-1]) if answers else ""

        try:
            graph: ProvenanceGraph = ProvenanceGraph.active()
        except RuntimeError:
            graph = ProvenanceGraph.reset()  # no tool call this turn; a graph is still needed to record the check
        verifications, parents = self.turn_verifications(graph)

        extractor: TurnExtractor = self.extractor or self._make_extractor()
        intent: dict[str, Any] = await extractor.intent(user_messages)
        claim: str = await extractor.claim(final)
        result: dict[str, Any] = TurnChecker.check(intent, claim, verifications)
        result["extraction"] = self.extraction_record(extractor)

        branch: str = (intent.get("employee_id") or "unknown").upper()
        graph.extend(branch, "turn", "turn_check", result, also=parents)
        AnchorLog.record(graph.run_id, graph.head())
        self.LIVE_RECORD.parent.mkdir(exist_ok=True)
        graph.save(self.LIVE_RECORD)
        self.logger.info("Turn check: %s %s", result["verdict"], result["problems"])

        if self.notify_user and result["verdict"] in self.FLAGGED:
            return {"messages": [AIMessage(final.rstrip() + "\n\n" + self.notice(result))]}
        return None

    def turn_verifications(self, graph: ProvenanceGraph) -> tuple[list[dict[str, Any]], list[str]]:
        """
        :return: This turn's verification records ({"args", "verdict", "problems"}, args taken from the tool_call
                 node with the same idempotency key) and the hashes of those verification nodes.
        """
        run_id, start = self.turn_start
        nodes: list[dict[str, Any]] = graph.nodes[start:] if run_id == graph.run_id else graph.nodes
        calls: dict[str, dict[str, Any]] = {
            node["data"].get("idempotency_key"): node["data"].get("args", {})
            for node in graph.nodes
            if node.get("kind") == "tool_call"
        }
        records: list[dict[str, Any]] = []
        hashes: list[str] = []
        for node in nodes:
            if node.get("kind") != "verification":
                continue
            data: dict[str, Any] = node["data"]
            records.append(
                {
                    "args": calls.get(data.get("idempotency_key"), {}),
                    "verdict": data.get("verdict"),
                    "problems": data.get("problems", []),
                }
            )
            hashes.append(node["hash"])
        return records, hashes

    @staticmethod
    def extraction_record(extractor: Any) -> dict[str, Any]:
        """
        :return: What the extraction said: the model and each call's raw reply (None if the call was never made, an
                 error string if it failed). The chat text it read is deliberately left out of the permanent graph.
        """
        raw: dict[str, str | None] = getattr(extractor, "raw", {}) or {}
        return {
            "model": getattr(extractor, "model", None),
            "intent_raw": raw.get("intent"),
            "claim_raw": raw.get("claim"),
        }

    @staticmethod
    def notice(result: dict[str, Any]) -> str:
        """The warning added to the answer, in plain words."""
        if result["verdict"] == "misreported":
            headline: str = "Our records do not confirm the answer above."
        else:
            headline = "What was booked does not match what you asked for."
        details: str = "; ".join(result["problems"])
        return (
            f"⚠️ Verification notice: {headline} ({details}) "
            "Please check your leave in the HR system before relying on it."
        )

    def _make_extractor(self) -> TurnExtractor:
        """Build the extractor's model on first use, so importing this module needs no API key or provider package."""
        module_name, class_name = self.llm_class.rsplit(".", 1)
        chat_class: type[BaseChatModel] = getattr(import_module(module_name), class_name)
        # "model" is accepted by both ChatAnthropic and ChatGoogleGenerativeAI; temperature 0 for repeatable fields.
        self.extractor = TurnExtractor(chat_class(model=self.model_name, temperature=0))
        return self.extractor
