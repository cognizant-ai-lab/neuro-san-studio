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
"""Tests for ``JevToolSelectorMiddleware``. No network: the Jev decision is injected through ``decider``."""

import asyncio
from typing import Any
from typing import Self
from unittest import TestCase

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage

from middleware.jev_tool_selector_middleware import JevToolSelectorMiddleware


# One test per path and per enforcement rule.
class TestJevToolSelectorMiddleware(TestCase):  # pylint: disable=too-many-public-methods
    """Every path (jev, same, none, aaosa, ask), the per-turn shaping, enforcement and failure handling."""

    class _FakeTool:  # pylint: disable=too-few-public-methods
        """Minimal ``BaseTool`` stand-in: a name, a description and the declared arguments."""

        def __init__(self, name: str, description: str, args: dict[str, Any] | None = None) -> None:
            self.name = name
            self.description = description
            self.args = args or {"inquiry": {}, "mode": {}}

    class _StubModelRequest:  # pylint: disable=too-few-public-methods
        """Minimal ``ModelRequest`` stand-in recording what ``override`` was called with."""

        def __init__(self, tools: list[Any], messages: list[Any], system_message: SystemMessage | None = None) -> None:
            self.tools = tools
            self.messages = messages
            self.system_message = system_message
            self.tool_choice: Any = None
            self.overrides: dict[str, Any] = {}

        def override(self, **kwargs: Any) -> Self:
            """Record the overrides and apply them to a copy, as ``dataclasses.replace`` would."""
            copy = type(self)(self.tools, self.messages, self.system_message)
            copy.overrides = {**self.overrides, **kwargs}
            copy.tools = kwargs.get("tools", self.tools)
            copy.tool_choice = kwargs.get("tool_choice", self.tool_choice)
            copy.system_message = kwargs.get("system_message", self.system_message)
            return copy

    class _StubToolCallRequest:  # pylint: disable=too-few-public-methods
        """Minimal ``ToolCallRequest`` stand-in."""

        def __init__(self, tool_call: dict[str, Any]) -> None:
            self.tool_call = tool_call

    class _Decider:  # pylint: disable=too-few-public-methods
        """Scripted replacement for the Jev call."""

        # One argument per scripted answer field.
        def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
            self,
            choice: str,
            confidence: float = 1.0,
            ambiguous: float = 0.0,
            error: Exception | None = None,
            probabilities: dict[str, float] | None = None,
        ) -> None:
            self.choice = choice
            self.confidence = confidence
            self.ambiguous = ambiguous
            self.error = error
            self.probabilities = probabilities or {choice: confidence}
            self.calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

        async def __call__(self, state: dict[str, Any], criteria: dict[str, Any]) -> dict[str, Any]:
            self.calls.append((state, criteria))
            if self.error is not None:
                raise self.error
            return {
                "choice": self.choice,
                "confidence": self.confidence,
                "probabilities": self.probabilities,
                "ambiguous": self.ambiguous,
                "model": "jev-test",
                "request_id": "req-1",
            }

    def setUp(self) -> None:
        self.tools = [
            self._FakeTool("HR", "The HR department head (AAOSA)."),
            self._FakeTool("Payroll", "Pay stubs, salary, tax deductions."),
            self._FakeTool("Benefits", "Health insurance, retirement plans."),
            self._FakeTool("URLProvider", "Returns intranet URLs.", {"app_name": {}}),
        ]
        self.messages = [HumanMessage(content="How do I check my pay stub?", id="user-1")]
        self.system_message = SystemMessage(content="AAOSA instructions")
        self.handled: list[Any] = []

    async def _handler(self, request: Any) -> AIMessage:
        """Stand-in for the model call: records the request and answers with a plain AIMessage."""
        self.handled.append(request)
        return AIMessage(content="model answer")

    async def _tool_handler(self, request: Any) -> ToolMessage:
        """Stand-in for tool execution."""
        self.handled.append(request)
        return ToolMessage(content="tool result", tool_call_id=request.tool_call.get("id"))

    def _make(self, decider: Any, **kwargs: Any) -> JevToolSelectorMiddleware:
        """Build a middleware with the scripted decider and the shipped example's shape (HR = fallback)."""
        arguments: dict[str, Any] = {
            "instructions": "Which department handles the latest message?",
            "decider": decider,
            "fallback_tools": ["HR"],
            "always_include": ["URLProvider"],
            "dispatch_args": {"inquiry": "$user_message", "mode": "Fulfill"},
            "followup_args": {"inquiry": "$user_message", "mode": "Follow up"},
            "routed_instructions": "routed instructions",
            "min_confidence": 0.75,
            "origin_str": "test.MyIntranet",
            "sly_data": {},
        }
        arguments.update(kwargs)
        return JevToolSelectorMiddleware(**arguments)

    def _request(self, messages: list[Any] | None = None) -> "_StubModelRequest":
        """A model request over the test tools and messages."""
        return self._StubModelRequest(self.tools, messages or self.messages, self.system_message)

    def _call(self, middleware: JevToolSelectorMiddleware, request: Any) -> Any:
        """Run awrap_model_call synchronously."""
        return asyncio.run(middleware.awrap_model_call(request, self._handler))  # type: ignore[arg-type]

    def _tool_call(self, middleware: JevToolSelectorMiddleware, name: str) -> Any:
        """Run awrap_tool_call synchronously for a call to the named tool."""
        request = self._StubToolCallRequest({"name": name, "id": f"call_{name}", "args": {}})
        return asyncio.run(middleware.awrap_tool_call(request, self._tool_handler))  # type: ignore[arg-type]

    # ---------------------------------------------------------------- jev path
    def test_confident_pick_is_dispatched_without_a_model_call(self) -> None:
        """A confident, unambiguous pick becomes a synthesized Fulfill call; the model is not called."""
        decider = self._Decider("Payroll", confidence=0.98)
        middleware = self._make(decider)

        result = self._call(middleware, self._request())

        self.assertEqual(self.handled, [])
        self.assertIsInstance(result, AIMessage)
        self.assertEqual(result.tool_calls[0].get("name"), "Payroll")
        self.assertEqual(
            result.tool_calls[0].get("args"), {"inquiry": "How do I check my pay stub?", "mode": "Fulfill"}
        )
        record = middleware.sly_data.get("jev_turn")
        self.assertEqual((record.get("path"), record.get("department")), ("jev", "Payroll"))
        self.assertEqual(middleware.sly_data.get("jev_current_department"), "Payroll")
        self.assertEqual(middleware.sly_data.get("jev_tool_selection"), [record])
        self.assertEqual(record.get("llm_tools"), ["Payroll", "URLProvider"])

    def test_criteria_are_candidates_plus_reserved_options(self) -> None:
        """Jev chooses among the candidate tools (not fallback or helper tools) plus same, none and unclear."""
        decider = self._Decider("Payroll")
        middleware = self._make(decider)

        self._call(middleware, self._request())

        state, criteria = decider.calls[0]
        self.assertEqual(sorted(criteria), ["Benefits", "Payroll", "none", "same", "unclear"])
        self.assertEqual(criteria.get("Payroll"), "Pay stubs, salary, tax deductions.")
        self.assertEqual(state.get("conversation"), [{"role": "user", "text": "How do I check my pay stub?"}])
        self.assertEqual(state.get("current_department"), "none")

    def test_later_model_calls_of_the_turn_are_shaped_not_rerouted(self) -> None:
        """After the dispatched tool result, the model sees the department, the helpers and routed_instructions."""
        decider = self._Decider("Payroll")
        middleware = self._make(decider)
        self._call(middleware, self._request())
        messages = self.messages + [
            AIMessage(
                content="", tool_calls=[{"name": "Payroll", "args": {}, "id": "jev_req-1", "type": "tool_call"}]
            ),
            ToolMessage(content="{...}", tool_call_id="jev_req-1"),
        ]

        result = self._call(middleware, self._request(messages))

        self.assertEqual(result.content, "model answer")
        self.assertEqual(len(decider.calls), 1)
        shaped = self.handled[0]
        self.assertEqual([tool.name for tool in shaped.tools], ["Payroll", "URLProvider"])
        self.assertEqual(shaped.system_message.content, "routed instructions")

    def test_narrow_mode_forces_tool_choice(self) -> None:
        """In narrow mode the model is called with the pick plus helpers and tool_choice forced."""
        middleware = self._make(self._Decider("Benefits"), mode="narrow")

        self._call(middleware, self._request())

        narrowed = self.handled[0]
        self.assertEqual([tool.name for tool in narrowed.tools], ["Benefits", "URLProvider"])
        self.assertEqual(narrowed.tool_choice, "Benefits")

    # ---------------------------------------------------------------- same path
    def test_same_follows_up_with_the_current_department(self) -> None:
        """``same`` dispatches a Follow up call to the department kept in sly_data, which Jev also saw."""
        decider = self._Decider("same", confidence=0.9)
        middleware = self._make(decider, sly_data={"jev_current_department": "Payroll"})
        messages = [
            HumanMessage(content="How do I check my pay stub?", id="user-1"),
            AIMessage(content="Open the Payroll app.", id="ai-1"),
            HumanMessage(content="And where is last year's?", id="user-2"),
        ]

        result = self._call(middleware, self._request(messages))

        self.assertEqual(result.tool_calls[0].get("name"), "Payroll")
        self.assertEqual(
            result.tool_calls[0].get("args"), {"inquiry": "And where is last year's?", "mode": "Follow up"}
        )
        state = decider.calls[0][0]
        self.assertEqual(state.get("current_department"), "Payroll")
        self.assertEqual([entry.get("role") for entry in state.get("conversation")], ["user", "assistant", "user"])
        self.assertEqual(middleware.sly_data.get("jev_turn").get("path"), "same")

    def test_current_department_is_read_from_history_when_sly_data_is_empty(self) -> None:
        """Without sly_data carried between turns, the last routed call in the history is the current department."""
        decider = self._Decider("same", confidence=0.9)
        middleware = self._make(decider)
        messages = [
            HumanMessage(content="I need a sick day tomorrow", id="user-1"),
            AIMessage(content="", tool_calls=[{"name": "Benefits", "args": {}, "id": "jev_0", "type": "tool_call"}]),
            ToolMessage(content="{...}", tool_call_id="jev_0"),
            AIMessage(content="Booked.", id="ai-1"),
            HumanMessage(content="Thanks, and the day after?", id="user-2"),
        ]

        result = self._call(middleware, self._request(messages))

        self.assertEqual(result.tool_calls[0].get("name"), "Benefits")
        self.assertEqual(decider.calls[0][0].get("current_department"), "Benefits")
        self.assertEqual(middleware.sly_data.get("jev_turn").get("previous_department"), "Benefits")

    def test_same_department_picked_again_is_a_follow_up(self) -> None:
        """Picking the current department again is a follow-up: followup_args, with the conversation as inquiry."""
        decider = self._Decider("Payroll", confidence=0.95)
        middleware = self._make(
            decider,
            sly_data={"jev_current_department": "Payroll"},
            followup_args={"inquiry": "$conversation", "mode": "Follow up"},
        )
        messages = [
            HumanMessage(content="How do I check my pay stub?", id="user-1"),
            AIMessage(content="Open the Payroll app.", id="ai-1"),
            HumanMessage(content="It says access denied.", id="user-2"),
        ]

        result = self._call(middleware, self._request(messages))

        record = middleware.sly_data.get("jev_turn")
        self.assertEqual((record.get("path"), record.get("reason")), ("same", "jev: same department again"))
        self.assertEqual(
            result.tool_calls[0].get("args"),
            {
                "inquiry": "user: How do I check my pay stub?\nassistant: Open the Payroll app.\n"
                "user: It says access denied.",
                "mode": "Follow up",
            },
        )

    def test_same_without_a_current_department_takes_the_fallback_path(self) -> None:
        """``same`` on a first turn cannot be honored: the turn falls back."""
        middleware = self._make(self._Decider("same", confidence=0.9))

        self._call(middleware, self._request())

        self.assertEqual(middleware.sly_data.get("jev_turn").get("path"), "aaosa")
        self.assertEqual([tool.name for tool in self.handled[0].tools], ["HR", "URLProvider"])

    # ---------------------------------------------------------------- none path
    def test_none_lets_the_model_answer_with_helpers_only(self) -> None:
        """``none`` runs the model with the agent's own instructions and only the helper tools."""
        middleware = self._make(self._Decider("none", confidence=0.8))

        result = self._call(middleware, self._request([HumanMessage(content="Thanks, bye!", id="user-1")]))

        self.assertEqual(result.content, "model answer")
        shaped = self.handled[0]
        self.assertEqual([tool.name for tool in shaped.tools], ["URLProvider"])
        self.assertIs(shaped.system_message, self.system_message)
        self.assertEqual(middleware.sly_data.get("jev_turn").get("path"), "none")
        self.assertIsNone(middleware.sly_data.get("jev_current_department"))

    # ---------------------------------------------------------------- aaosa path
    def test_low_confidence_takes_the_fallback_path_with_the_original_prompt(self) -> None:
        """Below min_confidence the model runs with fallback_tools + helpers and its unmodified instructions."""
        middleware = self._make(self._Decider("Benefits", confidence=0.3))

        result = self._call(middleware, self._request())

        self.assertEqual(result.content, "model answer")
        shaped = self.handled[0]
        self.assertEqual([tool.name for tool in shaped.tools], ["HR", "URLProvider"])
        self.assertIs(shaped.system_message, self.system_message)
        self.assertIsNone(shaped.tool_choice)
        record = middleware.sly_data.get("jev_turn")
        self.assertEqual(record.get("path"), "aaosa")
        self.assertIn("confidence 0.3 < 0.75", record.get("reason"))
        self.assertEqual(record.get("llm_tools"), ["HR", "URLProvider"])

    def test_ambiguous_message_takes_the_fallback_path(self) -> None:
        """A confident pick is still overridden when the ambiguity probability reaches the threshold."""
        middleware = self._make(self._Decider("Benefits", confidence=0.9, ambiguous=0.92))

        self._call(middleware, self._request())

        record = middleware.sly_data.get("jev_turn")
        self.assertEqual(record.get("path"), "aaosa")
        self.assertIn("ambiguous 0.92 >= 0.7", record.get("reason"))

    def test_unclear_takes_the_fallback_path(self) -> None:
        """The reserved ``unclear`` option is the fallback path by default."""
        middleware = self._make(self._Decider("unclear", confidence=0.7))

        self._call(middleware, self._request())

        self.assertEqual(middleware.sly_data.get("jev_turn").get("path"), "aaosa")
        self.assertEqual([tool.name for tool in self.handled[0].tools], ["HR", "URLProvider"])

    def test_fallback_path_without_fallback_tools_keeps_every_tool(self) -> None:
        """With no fallback_tools (flat network), the fallback path is the agent's full tool list, unmodified."""
        middleware = self._make(self._Decider("unclear"), fallback_tools=None)

        self._call(middleware, self._request())

        self.assertEqual([tool.name for tool in self.handled[0].tools], ["HR", "Payroll", "Benefits", "URLProvider"])

    # ---------------------------------------------------------------- ask and else_tool
    def test_on_unclear_ask_appends_a_clarifying_instruction(self) -> None:
        """``on_unclear: ask`` keeps the helpers only and names the most likely candidates in the system prompt."""
        decider = self._Decider(
            "unclear", confidence=0.6, probabilities={"Benefits": 0.4, "Payroll": 0.3, "unclear": 0.3}
        )
        middleware = self._make(decider, on_unclear="ask")

        self._call(middleware, self._request())

        shaped = self.handled[0]
        self.assertEqual([tool.name for tool in shaped.tools], ["URLProvider"])
        self.assertTrue(shaped.system_message.content.startswith("AAOSA instructions"))
        self.assertIn("Benefits, Payroll", shaped.system_message.content)
        self.assertEqual(middleware.sly_data.get("jev_turn").get("path"), "ask")

    def test_on_unclear_else_tool_routes_to_it(self) -> None:
        """``on_unclear: else_tool`` dispatches to the configured candidate instead of falling back."""
        middleware = self._make(self._Decider("unclear"), on_unclear="else_tool", else_tool="Benefits")

        result = self._call(middleware, self._request())

        self.assertEqual(result.tool_calls[0].get("name"), "Benefits")
        self.assertIn("else_tool", middleware.sly_data.get("jev_turn").get("reason"))

    # ---------------------------------------------------------------- enforcement
    def test_tools_outside_the_jev_path_are_denied(self) -> None:
        """On a routed turn only the department and the helpers execute."""
        middleware = self._make(self._Decider("Payroll"))
        self._call(middleware, self._request())

        self.assertEqual(self._tool_call(middleware, "Benefits").status, "error")
        self.assertEqual(self._tool_call(middleware, "HR").status, "error")
        self.assertEqual(self._tool_call(middleware, "Payroll").content, "tool result")
        self.assertEqual(self._tool_call(middleware, "URLProvider").content, "tool result")

    def test_tools_outside_the_fallback_path_are_denied(self) -> None:
        """On a fallback turn only fallback_tools and the helpers execute."""
        middleware = self._make(self._Decider("unclear"))
        self._call(middleware, self._request())

        self.assertEqual(self._tool_call(middleware, "HR").content, "tool result")
        self.assertEqual(self._tool_call(middleware, "Payroll").status, "error")

    # ---------------------------------------------------------------- failures
    def test_transient_error_fails_open_to_the_fallback_path(self) -> None:
        """When Jev is unreachable the turn runs exactly as the agent would without the middleware."""
        middleware = self._make(self._Decider("Payroll", error=ConnectionError("jev down")))

        result = self._call(middleware, self._request())

        self.assertEqual(result.content, "model answer")
        self.assertEqual([tool.name for tool in self.handled[0].tools], ["HR", "URLProvider"])
        record = middleware.sly_data.get("jev_turn")
        self.assertEqual(record.get("path"), "aaosa")
        self.assertEqual(record.get("error"), "jev down")

    def test_transient_error_propagates_when_fail_closed(self) -> None:
        """With fail_open disabled the transient failure ends the turn."""
        middleware = self._make(self._Decider("Payroll", error=ConnectionError("jev down")), fail_open=False)

        with self.assertRaises(ConnectionError):
            self._call(middleware, self._request())

    def test_invalid_settings_are_rejected(self) -> None:
        """Unknown mode or on_unclear values are configuration errors."""
        with self.assertRaises(ValueError):
            self._make(self._Decider("Payroll"), mode="sometimes")
        with self.assertRaises(ValueError):
            self._make(self._Decider("Payroll"), on_unclear="guess")
