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
Middleware that lets Jev (TypeSafe AI's typed-decision model) route each turn of an LLM agent: either straight
to one down-chain agent (the fast path) or to the agent's normal, LLM-driven tool use such as AAOSA (the
fallback path) when Jev is not confident, finds the message ambiguous, or sees no routing decision at all.

See docs/examples/industry/intranet_agents_with_jev_routing.md for the motivation and the measured comparison
with AAOSA routing, and docs/user_guide.md#middleware for how middleware is declared.
"""

import time
from logging import Logger
from logging import getLogger
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from typing import override

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from neuro_san.message.types.agent_message import AgentMessage


class JevToolSelectorMiddleware(AgentMiddleware):  # pylint: disable=too-many-instance-attributes
    """
    Jev decides, once per user turn, how the hosting LLM agent handles the turn.

    One Jev call asks a ``choice`` question over the agent's candidate tools plus three reserved options, and a
    yes/no question about ambiguity. The answer selects a *path*, and the middleware then shapes every model
    call of the turn accordingly, so the paths cannot bleed into each other:

    * ``jev`` - a candidate with enough confidence: the middleware dispatches the tool call itself (``mode``
      ``"dispatch"``: synthesized call, no LLM call for routing) or narrows the tool list and forces
      ``tool_choice`` (``mode`` ``"narrow"``). Later model calls of the turn see only that tool (plus
      ``always_include``) and, if given, ``routed_instructions`` as system prompt.
    * ``same`` - the message continues the exchange with the department of the previous turn (Jev picked
      ``same``, or picked that department again): the same dispatch, with ``followup_args`` (for AAOSA agents,
      ``mode: "Follow up"`` and, since down-chain agents keep no history between turns, ``"$conversation"`` as
      the inquiry so the department sees the recent exchange).
    * ``none`` - no routing decision (greetings, thanks, off-topic): the LLM answers from the conversation
      with only ``always_include`` tools available.
    * ``aaosa`` - the fallback: Jev picked ``unclear``, or its confidence is below ``min_confidence``, or the
      ambiguity probability is at least ``ambiguous_threshold``. The LLM runs with ``fallback_tools`` and its
      own (unmodified) instructions, i.e. exactly the agent's behavior without this middleware. The name is
      what the fallback is in the shipped example; any LLM-driven tool use works the same way.
    * ``ask`` - alternative to ``aaosa`` for unclear turns (``on_unclear: "ask"``): the LLM is told to ask the
      user which of the most likely candidates they mean.

    Tool calls outside the path's allowed set are rejected at execution time with an error ``ToolMessage``,
    the same enforcement neuro-san's ``LlmConfigToolSelectorMiddleware`` applies.

    The Jev state is the last ``history_turns`` messages of the conversation and the current department, so
    follow-ups and clarification answers are routed in context. If Jev cannot be reached (connection, rate
    limit, server error) the middleware fails open by default and the turn takes the ``aaosa`` path;
    authentication and validation errors propagate because they are configuration mistakes. Every decision is
    journaled and appended to ``sly_data["jev_tool_selection"]``, with ``llm_tools``, the tool names the LLM is
    given on that path; the per-turn path is kept in ``sly_data["jev_turn"]``.

    Requires ``pip install typesafe-sdk`` and the ``TYPESAFE_API_KEY`` environment variable, unless a
    ``decider`` is injected (tests).
    """

    SELECTION_KEY: str = "jev_tool_selection"
    TURN_KEY: str = "jev_turn"
    CURRENT_DEPARTMENT_KEY: str = "jev_current_department"
    USER_MESSAGE_PLACEHOLDER: str = "$user_message"
    CONVERSATION_PLACEHOLDER: str = "$conversation"
    MODES: tuple[str, ...] = ("narrow", "dispatch")
    ON_UNCLEAR: tuple[str, ...] = ("aaosa", "ask", "else_tool")
    PATHS: tuple[str, ...] = ("jev", "same", "none", "aaosa", "ask")
    RESERVED: tuple[str, ...] = ("same", "none", "unclear")
    DEFAULT_RESERVED_CRITERIA: Dict[str, str] = {
        "same": "The latest message continues the exchange with `current_department`: a follow-up, a clarification, "
        "or an answer to a question that department asked.",
        "none": "The latest message needs no department: a greeting, thanks, small talk, or something unrelated to "
        "the company.",
        "unclear": "The latest message is too vague to route, or it needs more than one department.",
    }
    DEFAULT_AMBIGUOUS_INSTRUCTIONS: str = (
        "Does the latest user message in `conversation` concern more than one department, or is it too vague to route "
        "to a single department?"
    )
    DEFAULT_ASK_INSTRUCTIONS: str = (
        "The request could belong to several departments: {options}. Ask the user a single clarifying question to "
        "find out which one applies before doing anything else."
    )

    # The constructor mirrors the hocon "args" one-to-one, hence the many arguments and locals.
    # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
    def __init__(
        self,
        instructions: str,
        criteria: Optional[Dict[str, Any]] = None,
        candidates: Optional[List[str]] = None,
        fallback_tools: Optional[List[str]] = None,
        always_include: Optional[List[str]] = None,
        reserved_criteria: Optional[Dict[str, Optional[str]]] = None,
        ambiguous_instructions: Optional[str] = DEFAULT_AMBIGUOUS_INSTRUCTIONS,
        ambiguous_threshold: float = 0.7,
        min_confidence: float = 0.0,
        on_unclear: str = "aaosa",
        else_tool: Optional[str] = None,
        mode: str = "dispatch",
        dispatch_args: Optional[Dict[str, Any]] = None,
        followup_args: Optional[Dict[str, Any]] = None,
        routed_instructions: Optional[str] = None,
        ask_instructions: str = DEFAULT_ASK_INSTRUCTIONS,
        history_turns: int = 6,
        model: Optional[str] = None,
        timeout_seconds: float = 3.0,
        fail_open: bool = True,
        sly_data: Optional[Dict[str, Any]] = None,
        journal: Any = None,
        origin_str: Optional[str] = None,
        decider: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    ) -> None:
        """
        Constructor.

        :param instructions: The Jev choice question, e.g. "Given `conversation`, which department handles the
                             latest user message?". With ``history_turns`` 0 the state key is ``message``.
        :param criteria: Optional mapping of candidate name to the description Jev chooses by. When omitted,
                         each candidate tool's description (its ``function.description``) is used.
        :param candidates: Tools Jev may route to. Defaults to every tool of the agent that is neither in
                           ``fallback_tools`` nor in ``always_include``.
        :param fallback_tools: Tools the LLM gets on the ``aaosa`` path (plus ``always_include``). Empty means
                               the agent's full tool list.
        :param always_include: Tools available on every path and never Jev candidates (helpers like a URL lookup).
        :param reserved_criteria: Descriptions of the reserved options ``same``, ``none`` and ``unclear``.
                                  Map one to null to disable it. Defaults to DEFAULT_RESERVED_CRITERIA.
        :param ambiguous_instructions: The yes/no ambiguity question, or None to skip it.
        :param ambiguous_threshold: Ambiguity probability at or above which the turn is treated as unclear.
        :param min_confidence: Choice confidence below which the turn is treated as unclear.
        :param on_unclear: What an unclear turn does: "aaosa" (fallback path), "ask" (the LLM asks which
                           candidate the user means) or "else_tool" (route to ``else_tool``).
        :param else_tool: Candidate used when ``on_unclear`` is "else_tool".
        :param mode: "dispatch" (synthesize the tool call, no LLM) or "narrow" (narrow + force tool_choice).
        :param dispatch_args: Arguments of the synthesized call on the ``jev`` path; "$user_message" is replaced
                              by the user's message and "$conversation" by the recent conversation (the last
                              ``history_turns`` messages, latest last). Keys the tool does not declare are dropped.
        :param followup_args: Arguments of the synthesized call on the ``same`` path (default: dispatch_args).
        :param routed_instructions: Optional system prompt for the model calls that follow a dispatch (the
                                    agent's own instructions are used when omitted).
        :param ask_instructions: Text appended to the system prompt on the ``ask`` path; ``{options}`` is
                                 replaced by the most likely candidates.
        :param history_turns: Number of recent conversation messages sent to Jev as state (0 = latest only).
        :param model: Jev model id, e.g. "jev-1.13.0". Defaults to the SDK's TYPESAFE_DEFAULT_MODEL.
        :param timeout_seconds: Budget for the Jev call (no retries).
        :param fail_open: When True, a transient Jev failure takes the ``aaosa`` path; when False the turn fails.
        :param sly_data: Injected by neuro-san when the key is present in the hocon args. Holds the audit trail,
                         the per-turn path and the current department.
        :param journal: Injected by neuro-san. Each decision is journaled as an AgentMessage.
        :param origin_str: Injected by neuro-san. Used in log messages.
        :param decider: Optional async callable ``(state, criteria) -> decision dict`` replacing the Jev SDK
                        call. Intended for tests. The dict has the keys ``choice``, ``confidence``,
                        ``probabilities``, ``ambiguous``, ``model`` and ``request_id``.
        """
        super().__init__()
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {self.MODES}, got '{mode}'")
        if on_unclear not in self.ON_UNCLEAR:
            raise ValueError(f"on_unclear must be one of {self.ON_UNCLEAR}, got '{on_unclear}'")
        self.instructions: str = instructions
        self.criteria: Optional[Dict[str, Any]] = criteria
        self.candidates: List[str] = list(candidates or [])
        self.fallback_tools: List[str] = list(fallback_tools or [])
        self.always_include: List[str] = list(always_include or [])
        reserved: Dict[str, Optional[str]] = dict(self.DEFAULT_RESERVED_CRITERIA)
        reserved.update(reserved_criteria or {})
        self.reserved_criteria: Dict[str, str] = {
            name: text for name, text in reserved.items() if name in self.RESERVED and text
        }
        self.ambiguous_instructions: Optional[str] = ambiguous_instructions
        self.ambiguous_threshold: float = float(ambiguous_threshold)
        self.min_confidence: float = float(min_confidence)
        self.on_unclear: str = on_unclear
        self.else_tool: Optional[str] = else_tool
        self.mode: str = mode
        self.dispatch_args: Dict[str, Any] = dispatch_args or {"text": self.USER_MESSAGE_PLACEHOLDER}
        self.followup_args: Dict[str, Any] = followup_args or dict(self.dispatch_args)
        self.routed_instructions: Optional[str] = routed_instructions
        self.ask_instructions: str = ask_instructions
        self.history_turns: int = int(history_turns)
        self.model: Optional[str] = model
        self.timeout_seconds: float = float(timeout_seconds)
        self.fail_open: bool = bool(fail_open)
        self.sly_data: Dict[str, Any] = sly_data if sly_data is not None else {}
        self.journal: Any = journal
        self.origin_str: str = origin_str or ""
        self.logger: Logger = getLogger(self.__class__.__name__)
        self.decider: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Awaitable[Dict[str, Any]]]] = decider
        # Transient errors are the only ones that may fail open. With an injected decider, generic network
        # errors stand in for the SDK's; with the SDK, its own connection/rate-limit/server errors are added.
        self.transient_errors: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)
        self.sdk: Dict[str, Any] = {}
        if self.decider is None:
            self.sdk = self._import_sdk()
            self.transient_errors = self.transient_errors + self.sdk.get("transient_errors", ())

    @staticmethod
    def _import_sdk() -> Dict[str, Any]:
        """
        Import the optional typesafe-sdk lazily so the studio can be imported without it.

        :return: The SDK classes used by this middleware.
        """
        try:
            # pylint: disable=import-outside-toplevel
            from typesafe_sdk import AsyncTypeSafeClient
            from typesafe_sdk import Choice
            from typesafe_sdk import Noul
            from typesafe_sdk import RetryPolicy
            from typesafe_sdk import TypeSafeAPIConnectionError
            from typesafe_sdk import TypeSafeInternalServerError
            from typesafe_sdk import TypeSafeRateLimitError
        except ImportError as exception:
            raise ValueError(
                "JevToolSelectorMiddleware needs the typesafe-sdk package: pip install typesafe-sdk "
                "(and set TYPESAFE_API_KEY)."
            ) from exception
        return {
            "client_class": AsyncTypeSafeClient,
            "choice_class": Choice,
            "noul_class": Noul,
            "retry_class": RetryPolicy,
            "transient_errors": (TypeSafeAPIConnectionError, TypeSafeRateLimitError, TypeSafeInternalServerError),
        }

    # ------------------------------------------------------------------ conversation helpers
    @staticmethod
    def _text_of(message: Any) -> str:
        """
        :param message: A LangChain message.
        :return: Its text content as a string.
        """
        content: Any = getattr(message, "content", "")
        return content if isinstance(content, str) else str(content)

    @staticmethod
    def _last_user_message(messages: List[Any]) -> Optional[HumanMessage]:
        """
        :param messages: The messages of the model request.
        :return: The latest user message, or None when there is none.
        """
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message
        return None

    @staticmethod
    def _is_first_model_call_of_turn(messages: List[Any]) -> bool:
        """
        :param messages: The messages of the model request.
        :return: True when no tool result has been produced since the latest user message.
        """
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return True
            if isinstance(message, ToolMessage):
                return False
        return True

    def _turn_id(self, messages: List[Any]) -> str:
        """
        :param messages: The messages of the model request.
        :return: An identifier of the current user turn (the latest user message).
        """
        user_message: Optional[HumanMessage] = self._last_user_message(messages)
        if user_message is None:
            return "no-user-message"
        if user_message.id:
            return str(user_message.id)
        # Without ids, the number of user messages so far plus the text is stable across the model calls of a turn.
        count: int = sum(1 for message in messages if isinstance(message, HumanMessage))
        return f"{count}:{self._text_of(user_message)[:80]}"

    def _current_department(self, messages: List[Any], candidates: Dict[str, Any]) -> Optional[str]:
        """
        The department that handled the previous turn: from sly_data when the client carries it between turns,
        otherwise from the agent's own history (the last candidate call before the latest user message).

        :param messages: The messages of the model request.
        :param candidates: The candidate tools by name.
        :return: The department name, or None on a first turn.
        """
        current: Optional[str] = self.sly_data.get(self.CURRENT_DEPARTMENT_KEY)
        if current in candidates:
            return current
        user_message: Optional[HumanMessage] = self._last_user_message(messages)
        for message in reversed(messages):
            if message is user_message:
                continue
            if isinstance(message, AIMessage):
                for tool_call in message.tool_calls or []:
                    if tool_call.get("name") in candidates:
                        return tool_call.get("name")
        return None

    def _state(self, messages: List[Any], current_department: Optional[str]) -> Dict[str, Any]:
        """
        Build the Jev state: the recent conversation (user and assistant text) and the current department.

        :param messages: The messages of the model request.
        :param current_department: The department that handled the previous turn, if any.
        :return: The state dict sent to Jev.
        """
        user_message: Optional[HumanMessage] = self._last_user_message(messages)
        if self.history_turns <= 0:
            return {"message": self._text_of(user_message) if user_message is not None else ""}
        conversation: List[Dict[str, str]] = []
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation.append({"role": "user", "text": self._text_of(message)})
            elif isinstance(message, AIMessage) and self._text_of(message).strip() and not message.tool_calls:
                conversation.append({"role": "assistant", "text": self._text_of(message)})
        return {
            "conversation": conversation[-self.history_turns :],
            "current_department": current_department or "none",
        }

    # ------------------------------------------------------------------ decision
    async def _decide(self, state: Dict[str, Any], criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ask Jev (or the injected decider) for the routing decision.

        :param state: The Jev state (conversation and current department).
        :param criteria: Option name -> description for the choice question.
        :return: A dict with ``choice``, ``confidence``, ``probabilities``, ``ambiguous``, ``model``, ``request_id``.
        """
        if self.decider is not None:
            return await self.decider(state, criteria)
        retry = self.sdk.get("retry_class")(max_retries=0, timeout=self.timeout_seconds)
        questions: Dict[str, Any] = {
            "route": self.sdk.get("choice_class")(instructions=self.instructions, criteria=criteria),
        }
        if self.ambiguous_instructions:
            questions["ambiguous"] = self.sdk.get("noul_class")(instructions=self.ambiguous_instructions)
        async with self.sdk.get("client_class")(model=self.model, retry=retry, timeout=self.timeout_seconds) as client:
            response = await client.system_one(state=state, questions=questions)
        answer = response.choices.get("route")
        ambiguous = response.nouls.get("ambiguous")
        return {
            "choice": answer.choice,
            "confidence": answer.confidence,
            "probabilities": dict(answer.probabilities),
            "ambiguous": ambiguous.noul if ambiguous is not None else None,
            "model": response.model,
            "request_id": response.request_id,
        }

    def _resolve_path(
        self, decision: Dict[str, Any], candidates: Dict[str, Any], current: Optional[str]
    ) -> Dict[str, Any]:
        """
        Turn a Jev decision into a path and (for routed paths) a department.

        :param decision: The Jev decision.
        :param candidates: The candidate tools by name.
        :param current: The department that handled the previous turn, if any.
        :return: A dict with ``path``, ``department`` (may be None) and ``reason``.
        """
        choice: Any = decision.get("choice")
        confidence: float = float(decision.get("confidence") or 0.0)
        ambiguous: Optional[float] = decision.get("ambiguous")
        if choice == "none":
            return {"path": "none", "department": None, "reason": "jev: none"}
        if choice == "same" and current in candidates:
            return {"path": "same", "department": current, "reason": "jev: same"}
        unclear_reason: Optional[str] = None
        if choice == "same":
            unclear_reason = "jev: same but no current department"
        elif choice == "unclear" or choice not in candidates:
            unclear_reason = f"jev: {choice}"
        elif confidence < self.min_confidence:
            unclear_reason = f"confidence {confidence} < {self.min_confidence}"
        elif ambiguous is not None and ambiguous >= self.ambiguous_threshold:
            unclear_reason = f"ambiguous {ambiguous} >= {self.ambiguous_threshold}"
        if unclear_reason is not None:
            return self._unclear(candidates, decision, unclear_reason)
        if choice == current:
            return {"path": "same", "department": choice, "reason": "jev: same department again"}
        return {"path": "jev", "department": choice, "reason": "jev"}

    def _unclear(self, candidates: Dict[str, Any], decision: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """
        :param candidates: The candidate tools by name.
        :param decision: The Jev decision (for the most likely candidates on the ask path).
        :param reason: Why the turn is unclear.
        :return: The path dict for an unclear turn, according to ``on_unclear``.
        """
        if self.on_unclear == "else_tool" and self.else_tool in candidates:
            return {"path": "jev", "department": self.else_tool, "reason": f"{reason} -> else_tool"}
        if self.on_unclear == "ask":
            probabilities: Dict[str, float] = decision.get("probabilities") or {}
            likely: List[str] = [
                name for name, _ in sorted(probabilities.items(), key=lambda item: -item[1]) if name in candidates
            ][:3]
            return {"path": "ask", "department": None, "reason": f"{reason} -> ask", "options": likely}
        return {"path": "aaosa", "department": None, "reason": f"{reason} -> aaosa"}

    async def _route_turn(self, request: ModelRequest, candidates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make the routing decision for a new user turn, journal it and store it for the rest of the turn.

        :param request: The model request of the first model call of the turn.
        :param candidates: The candidate tools by name.
        :return: The turn record (path, department, decision, reason).
        """
        criteria: Dict[str, Any] = self.criteria or {
            name: tool.description or None for name, tool in candidates.items()
        }
        criteria = {name: description for name, description in criteria.items() if name in candidates}
        criteria.update(self.reserved_criteria)
        current: Optional[str] = self._current_department(request.messages, candidates)
        state: Dict[str, Any] = self._state(request.messages, current)
        started: float = time.perf_counter()
        decision: Dict[str, Any]
        try:
            decision = await self._decide(state, criteria)
            resolved: Dict[str, Any] = self._resolve_path(decision, candidates, current)
        except self.transient_errors as exception:
            if not self.fail_open:
                raise
            self.logger.warning(
                "%s: Jev routing unavailable, taking the fallback path: %s", self.origin_str, exception
            )
            decision = {"error": str(exception)}
            resolved = {"path": "aaosa", "department": None, "reason": "jev unavailable -> aaosa"}
        record: Dict[str, Any] = {
            "turn_id": self._turn_id(request.messages),
            "path": resolved.get("path"),
            "department": resolved.get("department"),
            "reason": resolved.get("reason"),
            "options": resolved.get("options"),
            "previous_department": current,
            "mode": self.mode,
            "choice": decision.get("choice"),
            "confidence": decision.get("confidence"),
            "ambiguous": decision.get("ambiguous"),
            "probabilities": decision.get("probabilities"),
            "model": decision.get("model"),
            "request_id": decision.get("request_id"),
            "error": decision.get("error"),
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
        # The tools the LLM is given on this path (evidence that a fallback turn sees only fallback_tools + helpers).
        allowed: Optional[set[str]] = self._allowed_tools(record)
        record["llm_tools"] = (
            sorted(candidates.keys() | set(self.fallback_tools) | set(self.always_include))
            if allowed is None
            else sorted(allowed)
        )
        self.sly_data[self.TURN_KEY] = record
        self.sly_data.setdefault(self.SELECTION_KEY, []).append(record)
        if record.get("department"):
            self.sly_data[self.CURRENT_DEPARTMENT_KEY] = record.get("department")
        if self.journal is not None:
            summary: str = f"Jev routing: path={record.get('path')}"
            if record.get("department"):
                summary += f" -> `{record.get('department')}`"
            summary += f" ({record.get('reason')})"
            await self.journal.write_message(AgentMessage(content=summary, structure=record))
        return record

    def _current_turn(self, messages: List[Any]) -> Optional[Dict[str, Any]]:
        """
        :param messages: The messages of the model request.
        :return: The stored turn record when it belongs to the current user turn, else None.
        """
        record: Optional[Dict[str, Any]] = self.sly_data.get(self.TURN_KEY)
        if record and record.get("turn_id") == self._turn_id(messages):
            return record
        return None

    # ------------------------------------------------------------------ shaping
    def _is_candidate(self, name: str) -> bool:
        """
        :param name: A tool name of the hosting agent.
        :return: True when Jev may route to it.
        """
        if self.candidates:
            return name in self.candidates
        return name not in self.fallback_tools and name not in self.always_include

    def _conversation_text(self, messages: List[Any]) -> str:
        """
        :param messages: The messages of the model request.
        :return: The recent conversation as "user: ... / assistant: ..." lines, latest user message last.
        """
        entries: List[Dict[str, str]] = self._state(messages, None).get("conversation") or []
        return "\n".join(f"{entry.get('role')}: {entry.get('text')}" for entry in entries)

    def _dispatch_arguments(
        self, tool: Any, user_text: str, conversation_text: str, template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        :param tool: The tool to call.
        :param user_text: The user's message.
        :param conversation_text: The recent conversation, for the "$conversation" placeholder.
        :param template: The argument template (dispatch_args or followup_args).
        :return: The arguments of the synthesized tool call, restricted to the tool's declared parameters.
        """
        placeholders: Dict[str, str] = {
            self.USER_MESSAGE_PLACEHOLDER: user_text,
            self.CONVERSATION_PLACEHOLDER: conversation_text or user_text,
        }
        arguments: Dict[str, Any] = {
            key: placeholders.get(value, value) if isinstance(value, str) else value for key, value in template.items()
        }
        declared: Dict[str, Any] = getattr(tool, "args", None) or {}
        if not declared:
            return arguments
        return {key: value for key, value in arguments.items() if key in declared}

    def _allowed_tools(self, record: Dict[str, Any]) -> Optional[set[str]]:
        """
        :param record: The turn record.
        :return: Tool names the turn may execute, or None for "no restriction".
        """
        path: str = record.get("path")
        if path in ("jev", "same"):
            return {record.get("department"), *self.always_include}
        if path == "aaosa":
            return set(self.fallback_tools) | set(self.always_include) if self.fallback_tools else None
        return set(self.always_include)

    def _shape(
        self, request: ModelRequest, record: Dict[str, Any], base_tools: List[Any], provider_tools: List[Any]
    ) -> ModelRequest:
        """
        Restrict the tools (and optionally the system prompt) of a model call to the turn's path.

        :param request: The model request.
        :param record: The turn record.
        :param base_tools: The request's BaseTool tools.
        :param provider_tools: The request's provider-native tool dicts (always kept).
        :return: The shaped model request.
        """
        allowed: Optional[set[str]] = self._allowed_tools(record)
        tools: List[Any] = base_tools if allowed is None else [tool for tool in base_tools if tool.name in allowed]
        overrides: Dict[str, Any] = {"tools": [*tools, *provider_tools]}
        original: str = request.system_message.content if request.system_message is not None else ""
        if record.get("path") in ("jev", "same") and self.routed_instructions:
            overrides["system_message"] = SystemMessage(content=self.routed_instructions)
        elif record.get("path") == "ask":
            options: str = ", ".join(record.get("options") or []) or "the departments"
            text: str = self.ask_instructions.format(options=options)
            overrides["system_message"] = SystemMessage(content=f"{original}\n\n{text}" if original else text)
        return request.override(**overrides)

    # ------------------------------------------------------------------ hooks
    @override
    async def awrap_model_call(  # pylint: disable=too-many-locals
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> Union[ModelResponse, AIMessage]:
        """
        Decide the path on the first model call of a user turn; shape every model call of the turn.

        :param request: The model request.
        :param handler: Executes the (possibly modified) model request.
        :return: The model response, or a synthesized AIMessage carrying the tool call in "dispatch" mode.
        """
        base_tools: List[Any] = [tool for tool in (request.tools or []) if not isinstance(tool, dict)]
        provider_tools: List[Any] = [tool for tool in (request.tools or []) if isinstance(tool, dict)]
        candidates: Dict[str, Any] = {tool.name: tool for tool in base_tools if self._is_candidate(tool.name)}
        user_message: Optional[HumanMessage] = self._last_user_message(request.messages)
        if not candidates or user_message is None:
            return await handler(request)

        record: Optional[Dict[str, Any]] = self._current_turn(request.messages)
        first_call: bool = self._is_first_model_call_of_turn(request.messages)
        if record is None:
            if not first_call:
                return await handler(request)  # a turn that started before this middleware existed
            record = await self._route_turn(request, candidates)

        path: str = record.get("path")
        if path in ("jev", "same") and first_call:
            chosen: Any = candidates.get(record.get("department"))
            template: Dict[str, Any] = self.followup_args if path == "same" else self.dispatch_args
            user_text: str = self._text_of(user_message)
            if self.mode == "dispatch":
                call_id: str = f"jev_{record.get('request_id') or int(time.time() * 1000)}"
                tool_call: Dict[str, Any] = {
                    "name": chosen.name,
                    "args": self._dispatch_arguments(
                        chosen, user_text, self._conversation_text(request.messages), template
                    ),
                    "id": call_id,
                    "type": "tool_call",
                }
                # Returned without calling the handler: the agent loop executes it as if the model had asked.
                return AIMessage(content="", tool_calls=[tool_call])
            shaped: ModelRequest = self._shape(request, record, base_tools, provider_tools)
            return await handler(shaped.override(tool_choice=chosen.name))
        return await handler(self._shape(request, record, base_tools, provider_tools))

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Union[ToolMessage, Command]]],
    ) -> Union[ToolMessage, Command]:
        """
        Enforce the path: a tool call outside the turn's allowed set does not execute.

        :param request: The tool call request.
        :param handler: Executes the tool call.
        :return: The tool result, or an error ToolMessage when the tool is not allowed on this path.
        """
        name: Optional[str] = request.tool_call.get("name")
        record: Optional[Dict[str, Any]] = self.sly_data.get(self.TURN_KEY)
        allowed: Optional[set[str]] = self._allowed_tools(record) if record else None
        if allowed is not None and name not in allowed:
            self.logger.warning(
                "%s: tool call for %s is outside the %s path; denying it.", self.origin_str, name, record.get("path")
            )
            return ToolMessage(
                content=f"Error: tool '{name}' is not available on this turn; use one of {sorted(allowed)}.",
                tool_call_id=request.tool_call.get("id"),
                name=name,
                status="error",
            )
        return await handler(request)
