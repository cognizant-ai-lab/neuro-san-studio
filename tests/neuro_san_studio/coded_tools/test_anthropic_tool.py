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
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from anthropic import AnthropicError

from neuro_san_studio.coded_tools.anthropic_tool import DEFAULT_ANTHROPIC_MODEL
from neuro_san_studio.coded_tools.anthropic_tool import AnthropicTool

# Patch the name in the module under test, not "langchain_anthropic.ChatAnthropic".
MODULE = "neuro_san_studio.coded_tools.anthropic_tool"
SLY_DATA: dict[str, Any] = {"llm_config": {"anthropic_api_key": "sly-key"}}
CONTENT: list[dict[str, Any]] = [{"type": "text", "text": "hello"}]


class TestAnthropicTool(IsolatedAsyncioTestCase):
    """
    Unit tests for AnthropicTool.

    ChatAnthropic is replaced by a stand-in so no network is touched. The tests pin which
    api_key reaches the constructor under each BYOK scenario and that the existing
    tool-spec plumbing (betas, additional kwargs, tool_choice, error string) is unchanged.
    """

    @staticmethod
    def _chat_anthropic_mock() -> MagicMock:
        """
        Build a stand-in for the ChatAnthropic class whose instances answer ainvoke with fixed content.

        :return: A MagicMock usable as the patched ChatAnthropic class.
        """
        message = MagicMock(name="AIMessage")
        message.content = CONTENT
        llm = MagicMock(name="ChatAnthropic instance")
        llm.ainvoke = AsyncMock(return_value=message)
        return MagicMock(name="ChatAnthropic", return_value=llm)

    async def test_sly_data_key_is_passed_to_chat_anthropic(self) -> None:
        """
        A BYOK key in sly_data reaches ChatAnthropic even when ANTHROPIC_API_KEY is also set.
        """
        chat_cls: MagicMock = self._chat_anthropic_mock()
        with patch(f"{MODULE}.ChatAnthropic", chat_cls), patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            result: Any = await AnthropicTool.arun(
                query="q", tool_type="web_search_20250305", tool_name="web_search", sly_data=SLY_DATA
            )
        self.assertEqual(result, CONTENT)
        self.assertEqual(chat_cls.call_args.kwargs["api_key"], "sly-key")
        self.assertEqual(chat_cls.call_args.kwargs["model"], DEFAULT_ANTHROPIC_MODEL)

    async def test_env_key_used_without_sly_data(self) -> None:
        """
        Without sly_data the ANTHROPIC_API_KEY environment variable is passed explicitly.
        """
        chat_cls: MagicMock = self._chat_anthropic_mock()
        with patch(f"{MODULE}.ChatAnthropic", chat_cls), patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            await AnthropicTool.arun(query="q", tool_type="web_search_20250305", tool_name="web_search")
        self.assertEqual(chat_cls.call_args.kwargs["api_key"], "env-key")

    async def test_none_key_when_no_source(self) -> None:
        """
        With neither source available, None is passed so ChatAnthropic behaves as it always did.
        """
        chat_cls: MagicMock = self._chat_anthropic_mock()
        with patch(f"{MODULE}.ChatAnthropic", chat_cls), patch.dict(os.environ, {}, clear=True):
            await AnthropicTool.arun(query="q", tool_type="web_search_20250305", tool_name="web_search", sly_data={})
        self.assertIsNone(chat_cls.call_args.kwargs["api_key"])

    async def test_betas_and_additional_kwargs_still_reach_invoke(self) -> None:
        """
        Inserting the sly_data parameter must not disturb betas, tool kwargs or tool_choice.
        """
        chat_cls: MagicMock = self._chat_anthropic_mock()
        with patch(f"{MODULE}.ChatAnthropic", chat_cls), patch.dict(os.environ, {}, clear=True):
            await AnthropicTool.arun(
                query="q",
                tool_type="code_execution_20250522",
                tool_name="code_execution",
                anthropic_model="claude-opus-4-1-20250805",
                betas=["code-execution-2025-05-22"],
                sly_data=SLY_DATA,
                max_uses=3,
            )
        ainvoke: AsyncMock = chat_cls.return_value.ainvoke
        self.assertEqual(ainvoke.call_args.args, ("q",))
        self.assertEqual(ainvoke.call_args.kwargs["betas"], ["code-execution-2025-05-22"])
        self.assertEqual(
            ainvoke.call_args.kwargs["tools"],
            [{"type": "code_execution_20250522", "name": "code_execution", "max_uses": 3}],
        )
        self.assertEqual(ainvoke.call_args.kwargs["tool_choice"], {"type": "any"})
        self.assertEqual(chat_cls.call_args.kwargs["model"], "claude-opus-4-1-20250805")

    async def test_anthropic_error_is_returned_as_string(self) -> None:
        """
        An AnthropicError raised while building the client is returned as the documented error string.
        """
        chat_cls = MagicMock(name="ChatAnthropic", side_effect=AnthropicError("invalid x-api-key"))
        with patch(f"{MODULE}.ChatAnthropic", chat_cls), patch.dict(os.environ, {}, clear=True):
            result: Any = await AnthropicTool.arun(query="q", tool_type="web_search_20250305", tool_name="web_search")
        self.assertEqual(result, "Anthropic Error: invalid x-api-key")

    def test_get_api_key_prefers_sly_data(self) -> None:
        """
        get_api_key returns the BYOK key when sly_data carries one.
        """
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            self.assertEqual(AnthropicTool.get_api_key(SLY_DATA), "sly-key")

    def test_get_api_key_falls_back_to_env(self) -> None:
        """
        get_api_key returns ANTHROPIC_API_KEY when sly_data has no usable key.
        """
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            self.assertEqual(AnthropicTool.get_api_key({}), "env-key")
            self.assertEqual(AnthropicTool.get_api_key(None), "env-key")
