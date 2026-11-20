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

from openai import OpenAIError

from neuro_san_studio.coded_tools.openai_tool import DEFAULT_OPENAI_MODEL
from neuro_san_studio.coded_tools.openai_tool import OpenAITool

# Patch the name in the module under test, not "langchain_openai.ChatOpenAI".
MODULE = "neuro_san_studio.coded_tools.openai_tool"
SLY_DATA: dict[str, Any] = {"llm_config": {"openai_api_key": "sly-key"}}
CONTENT_BLOCKS: list[dict[str, Any]] = [{"type": "text", "text": "hello"}]


class TestOpenAITool(IsolatedAsyncioTestCase):
    """
    Unit tests for OpenAITool.

    ChatOpenAI is replaced by a stand-in so no network is touched. The tests pin which
    api_key reaches the constructor under each BYOK scenario and that the existing
    tool-spec plumbing (additional kwargs, tool_choice, error string) is unchanged.
    """

    @staticmethod
    def _chat_openai_mock() -> MagicMock:
        """
        Build a stand-in for the ChatOpenAI class whose instances answer ainvoke with fixed content.

        :return: A MagicMock usable as the patched ChatOpenAI class.
        """
        message = MagicMock(name="AIMessage")
        message.content_blocks = CONTENT_BLOCKS
        llm = MagicMock(name="ChatOpenAI instance")
        llm.ainvoke = AsyncMock(return_value=message)
        return MagicMock(name="ChatOpenAI", return_value=llm)

    async def test_sly_data_key_is_passed_to_chat_openai(self) -> None:
        """
        A BYOK key in sly_data reaches ChatOpenAI even when OPENAI_API_KEY is also set.
        """
        chat_cls: MagicMock = self._chat_openai_mock()
        with patch(f"{MODULE}.ChatOpenAI", chat_cls), patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            result: Any = await OpenAITool.arun("q", "web_search_preview", None, sly_data=SLY_DATA)
        self.assertEqual(result, CONTENT_BLOCKS)
        self.assertEqual(chat_cls.call_args.kwargs["api_key"], "sly-key")
        # A None model still resolves to the default, as before.
        self.assertEqual(chat_cls.call_args.kwargs["model"], DEFAULT_OPENAI_MODEL)
        self.assertEqual(chat_cls.call_args.kwargs["output_version"], "responses/v1")

    async def test_env_key_used_without_sly_data(self) -> None:
        """
        Without sly_data the OPENAI_API_KEY environment variable is passed explicitly.
        """
        chat_cls: MagicMock = self._chat_openai_mock()
        with patch(f"{MODULE}.ChatOpenAI", chat_cls), patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            await OpenAITool.arun("q", "web_search_preview")
        self.assertEqual(chat_cls.call_args.kwargs["api_key"], "env-key")

    async def test_none_key_when_no_source(self) -> None:
        """
        With neither source available, None is passed so ChatOpenAI behaves as it always did.
        """
        chat_cls: MagicMock = self._chat_openai_mock()
        with patch(f"{MODULE}.ChatOpenAI", chat_cls), patch.dict(os.environ, {}, clear=True):
            await OpenAITool.arun("q", "web_search_preview", sly_data={})
        self.assertIsNone(chat_cls.call_args.kwargs["api_key"])

    async def test_additional_kwargs_still_reach_tool_spec(self) -> None:
        """
        Inserting the sly_data parameter must not swallow the tool's own keyword arguments.
        """
        chat_cls: MagicMock = self._chat_openai_mock()
        with patch(f"{MODULE}.ChatOpenAI", chat_cls), patch.dict(os.environ, {}, clear=True):
            await OpenAITool.arun("q", "code_interpreter", "gpt-5", sly_data=SLY_DATA, container={"type": "auto"})
        ainvoke: AsyncMock = chat_cls.return_value.ainvoke
        self.assertEqual(ainvoke.call_args.args, ("q",))
        self.assertEqual(
            ainvoke.call_args.kwargs["tools"], [{"type": "code_interpreter", "container": {"type": "auto"}}]
        )
        self.assertEqual(ainvoke.call_args.kwargs["tool_choice"], "required")
        self.assertEqual(chat_cls.call_args.kwargs["model"], "gpt-5")

    async def test_openai_error_is_returned_as_string(self) -> None:
        """
        An OpenAIError raised while building the client is returned as the documented error string.
        """
        chat_cls = MagicMock(name="ChatOpenAI", side_effect=OpenAIError("Missing credentials"))
        with patch(f"{MODULE}.ChatOpenAI", chat_cls), patch.dict(os.environ, {}, clear=True):
            result: Any = await OpenAITool.arun("q", "web_search_preview")
        self.assertEqual(result, "OpenAI Error: Missing credentials")

    def test_get_api_key_prefers_sly_data(self) -> None:
        """
        get_api_key returns the BYOK key when sly_data carries one.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            self.assertEqual(OpenAITool.get_api_key(SLY_DATA), "sly-key")

    def test_get_api_key_falls_back_to_env(self) -> None:
        """
        get_api_key returns OPENAI_API_KEY when sly_data has no usable key.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            self.assertEqual(OpenAITool.get_api_key({}), "env-key")
            self.assertEqual(OpenAITool.get_api_key(None), "env-key")
