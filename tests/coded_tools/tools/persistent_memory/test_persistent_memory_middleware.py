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
Tests for PersistentMemoryMiddleware — the wrapper that exposes PersistentMemoryTool
as a LangChain ``AgentMiddleware`` / ``StructuredTool``.
"""

import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from middleware.persistent_memory import MemorySummariser
from middleware.persistent_memory import PersistentMemoryMiddleware
from middleware.persistent_memory.persistent_memory_middleware import MEMORY_TOOL_NAME

from tests.coded_tools.tools.persistent_memory._base import MemoryTestBase


class TestPersistentMemoryMiddlewareRegistration(MemoryTestBase):
    """The middleware registers exactly one tool, named ``persistent_memory``."""

    def test_registers_single_named_tool(self):
        """One dispatcher tool, named as MEMORY_TOOL_NAME, tagged for journalling."""
        mw = self.make_middleware()
        self.assertEqual(len(mw.tools), 1)
        self.assertEqual(mw.tools[0].name, MEMORY_TOOL_NAME)
        self.assertIn("langchain_tool", mw.tools[0].tags or [])

    def test_schema_enum_reflects_enabled_operations(self):
        """The tool's arg schema constrains 'operation' to the enabled ops — the LLM cannot pick a disabled one."""
        mw = self.make_middleware(enabled_operations=["read", "search"])
        schema = mw.tools[0].args_schema
        enum_values = schema["properties"]["operation"]["enum"]
        self.assertCountEqual(enum_values, ["read", "search"])


class TestPersistentMemoryMiddlewareDispatch(MemoryTestBase):
    """The tool forwards to PersistentMemoryTool.async_invoke with the right args + sly_data."""

    def test_end_to_end_create_then_search(self):
        """A create via the middleware's tool is searchable via the same tool."""
        mw = self.make_middleware()
        tool_fn = mw.tools[0]

        create_result = asyncio.run(tool_fn.coroutine(operation="create", key="k1", content="loves dark coffee"))
        self.assertEqual(create_result["result"]["status"], "created")

        search_result = asyncio.run(tool_fn.coroutine(operation="search", query="coffee"))
        keys = [r["key"] for r in search_result["result"]["results"]]
        self.assertIn("k1", keys)

    def test_forwarding_passes_sly_data_to_underlying_tool(self):
        """Middleware's sly_data reaches PersistentMemoryTool.async_invoke."""
        mw = self.make_middleware(sly_data={"user_id": "alice"})
        mock_invoke = AsyncMock(return_value={"result": {"ok": True}})
        with patch.object(mw.persistent_memory_tool, "async_invoke", mock_invoke):
            asyncio.run(mw.tools[0].coroutine(operation="list"))

        # Called once with ({"operation": "list"}, {"user_id": "alice"}).
        mock_invoke.assert_awaited_once()
        args, kwargs = mock_invoke.call_args
        called_args = args[0] if args else kwargs.get("args")
        called_sly = args[1] if len(args) > 1 else kwargs.get("sly_data")
        self.assertEqual(called_args, {"operation": "list"})
        self.assertEqual(called_sly, {"user_id": "alice"})


class TestPersistentMemoryMiddlewarePreamble(MemoryTestBase):
    """``PersistentMemoryMiddleware.build_preamble`` yields a short, operation-aware string."""

    def test_preamble_mentions_tool_name_and_ops(self):
        """The system-prompt preamble mentions the tool name and each enabled op."""
        mw = self.make_middleware(enabled_operations=["read", "search"])
        text = PersistentMemoryMiddleware.build_preamble(mw.persistent_memory_tool.enabled_operations)
        self.assertIn(MEMORY_TOOL_NAME, text)
        self.assertIn("read", text)
        self.assertIn("search", text)


class TestPersistentMemoryMiddlewareClose(MemoryTestBase):
    """``aafter_agent`` closes the underlying tool and swallows errors."""

    def test_aafter_agent_calls_tool_close(self):
        """Lifecycle hook delegates cleanup to PersistentMemoryTool.close."""
        mw = self.make_middleware()
        mock_close = AsyncMock()
        with patch.object(mw.persistent_memory_tool, "close", mock_close):
            asyncio.run(mw.aafter_agent(state=None, runtime=None))
        mock_close.assert_awaited_once()


class TestPersistentMemoryMiddlewareAutoCompact(MemoryTestBase):
    """After a write, if the file has grown past ``compact_threshold``,
    the middleware rewrites it in-place with a summarised version."""

    def _mw_with_summariser(self, *, compact_on_write: bool, threshold: int):
        """Build a middleware with a stubbed summariser so we can drive compaction without hitting a real LLM.

        :param compact_on_write: Value to set on the stub summariser.
        :param threshold: Compact threshold to set on the stub.
        :return: ``(middleware, stub_summariser)`` tuple.
        """
        mw = self.make_middleware()
        # Replace the real MemorySummariser instance with a stub that does not need
        # an API key. We only care about the public surface _maybe_compact uses.
        stub = MemorySummariser.__new__(MemorySummariser)
        stub.compact_on_write = compact_on_write
        stub.compact_threshold = threshold
        stub.summarise = AsyncMock(return_value="SUMMARISED")
        stub.post_process = AsyncMock(side_effect=lambda _op, result: result)
        # pylint: disable=protected-access
        mw._summariser = stub
        return mw, stub

    def test_write_past_threshold_triggers_compact(self):
        """A create that pushes the file past the threshold is rewritten with the summary."""
        mw, stub = self._mw_with_summariser(compact_on_write=True, threshold=20)
        tool_fn = mw.tools[0]

        # Long content → crosses threshold of 20 chars.
        long_content = "x" * 50
        asyncio.run(tool_fn.coroutine(operation="create", key="k1", content=long_content))

        stub.summarise.assert_awaited_once_with(long_content)

        read = asyncio.run(
            mw.persistent_memory_tool.async_invoke({"operation": "read", "key": "k1"}, {"user_id": "alice"})
        )
        self.assertEqual(read["result"]["content"], "SUMMARISED")

    def test_write_under_threshold_skips_compact(self):
        """A short write does not trigger the summariser — avoid unnecessary LLM calls."""
        mw, stub = self._mw_with_summariser(compact_on_write=True, threshold=200)
        tool_fn = mw.tools[0]

        asyncio.run(tool_fn.coroutine(operation="create", key="k1", content="short"))

        stub.summarise.assert_not_awaited()
        read = asyncio.run(
            mw.persistent_memory_tool.async_invoke({"operation": "read", "key": "k1"}, {"user_id": "alice"})
        )
        self.assertEqual(read["result"]["content"], "short")

    def test_compact_disabled_skips_even_when_over_threshold(self):
        """With compact_on_write=False the file is kept verbatim regardless of size."""
        mw, stub = self._mw_with_summariser(compact_on_write=False, threshold=10)
        tool_fn = mw.tools[0]

        long_content = "y" * 100
        asyncio.run(tool_fn.coroutine(operation="create", key="k1", content=long_content))

        stub.summarise.assert_not_awaited()
        read = asyncio.run(
            mw.persistent_memory_tool.async_invoke({"operation": "read", "key": "k1"}, {"user_id": "alice"})
        )
        self.assertEqual(read["result"]["content"], long_content)

    def test_compact_works_when_update_not_in_enabled_operations(self):
        """Compaction is an internal rewrite and must not be gated by the LLM-facing whitelist.

        The coffee_finder network enables ['read', 'append', 'delete', 'search']
        only — 'update' is deliberately hidden from the LLM. The middleware's
        auto-compact still needs to rewrite the file, so it uses the tool's
        internal backdoor which bypasses the whitelist.
        """
        mw = self.make_middleware(enabled_operations=["read", "append", "delete", "search"])
        stub = MemorySummariser.__new__(MemorySummariser)
        stub.compact_on_write = True
        stub.compact_threshold = 20
        stub.summarise = AsyncMock(return_value="SUMMARISED")
        stub.post_process = AsyncMock(side_effect=lambda _op, result: result)
        # pylint: disable=protected-access
        mw._summariser = stub

        tool_fn = mw.tools[0]
        long_content = "x" * 50
        result = asyncio.run(tool_fn.coroutine(operation="append", key="k1", content=long_content))
        self.assertNotIn("error", result)

        stub.summarise.assert_awaited_once_with(long_content)

        read = asyncio.run(
            mw.persistent_memory_tool.async_invoke_internal({"operation": "read", "key": "k1"}, {"user_id": "alice"})
        )
        self.assertEqual(read["result"]["content"], "SUMMARISED")

    def test_compact_failure_does_not_break_write(self):
        """If the summariser errors, the original write is still visible — compaction is best-effort."""
        mw, stub = self._mw_with_summariser(compact_on_write=True, threshold=10)
        stub.summarise = AsyncMock(side_effect=RuntimeError("LLM exploded"))
        tool_fn = mw.tools[0]

        long_content = "z" * 100
        result = asyncio.run(tool_fn.coroutine(operation="create", key="k1", content=long_content))
        self.assertNotIn("error", result)

        read = asyncio.run(
            mw.persistent_memory_tool.async_invoke({"operation": "read", "key": "k1"}, {"user_id": "alice"})
        )
        self.assertEqual(read["result"]["content"], long_content)


class TestMemorySummariserPersonalization(TestCase):
    """Optional HOCON 'personalization' field is appended to the base instructions at call time."""

    def test_personalization_from_config_is_appended_to_system_prompt(self):
        """from_config reads 'personalization' and summarise() passes it to the LLM."""
        with patch("middleware.persistent_memory.memory_summariser.ChatOpenAI") as fake_chat_cls:
            fake_llm = AsyncMock()
            fake_response = AsyncMock()
            fake_response.content = "ok"
            fake_llm.ainvoke = AsyncMock(return_value=fake_response)
            fake_chat_cls.return_value = fake_llm

            summariser = MemorySummariser.from_config(
                {
                    "enabled": True,
                    "instructions": "Base instructions.",
                    "personalization": "Always mention the user's favourite colour is teal.",
                }
            )
            self.assertIsNotNone(summariser)
            asyncio.run(summariser.summarise("x" * 400))

        fake_llm.ainvoke.assert_awaited_once()
        messages = fake_llm.ainvoke.call_args[0][0]
        system_content = messages[0].content
        self.assertIn("Base instructions.", system_content)
        self.assertIn("Always mention the user's favourite colour is teal.", system_content)
