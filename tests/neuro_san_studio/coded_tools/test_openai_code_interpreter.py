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
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from neuro_san_studio.coded_tools.openai_code_interpreter import OpenAICodeInterpreter
from neuro_san_studio.coded_tools.openai_tool import OpenAITool

SLY_DATA: dict[str, Any] = {"llm_config": {"openai_api_key": "sly-key"}}
CONTENT: list[dict[str, Any]] = [{"type": "text", "text": "42"}]


class TestOpenAICodeInterpreter(IsolatedAsyncioTestCase):
    """
    Unit tests for OpenAICodeInterpreter.

    OpenAITool.arun is replaced by a stand-in so no network is touched. The tests pin that
    the caller's sly_data is forwarded (the BYOK regression) and that the container default
    is still injected without mutating the caller's additional_kwargs.
    """

    async def test_sly_data_is_forwarded_with_default_container(self) -> None:
        """
        Without a container in additional_kwargs, an auto container is added and sly_data is forwarded.
        """
        arun = AsyncMock(return_value=CONTENT)
        additional_kwargs: dict[str, Any] = {}
        args: dict[str, Any] = {"query": "6 * 7", "additional_kwargs": additional_kwargs}
        with patch.object(OpenAITool, "arun", new=arun):
            result: Any = await OpenAICodeInterpreter().async_invoke(args, SLY_DATA)
        self.assertEqual(result, CONTENT)
        arun.assert_awaited_once_with("6 * 7", "code_interpreter", None, sly_data=SLY_DATA, container={"type": "auto"})
        # The caller's dict must stay untouched; the default goes into a copy.
        self.assertEqual(additional_kwargs, {})

    async def test_explicit_container_is_kept(self) -> None:
        """
        A container supplied by the user is passed through unchanged.
        """
        arun = AsyncMock(return_value=CONTENT)
        args: dict[str, Any] = {
            "query": "6 * 7",
            "openai_model": "gpt-5",
            "additional_kwargs": {"container": "cntr_123"},
        }
        with patch.object(OpenAITool, "arun", new=arun):
            await OpenAICodeInterpreter().async_invoke(args, SLY_DATA)
        arun.assert_awaited_once_with("6 * 7", "code_interpreter", "gpt-5", sly_data=SLY_DATA, container="cntr_123")

    async def test_missing_query_returns_error_without_calling_tool(self) -> None:
        """
        An empty query short-circuits with the documented error string.
        """
        arun = AsyncMock(return_value=CONTENT)
        with patch.object(OpenAITool, "arun", new=arun):
            result: Any = await OpenAICodeInterpreter().async_invoke({}, SLY_DATA)
        self.assertEqual(result, "Error: No query provided.")
        arun.assert_not_awaited()
