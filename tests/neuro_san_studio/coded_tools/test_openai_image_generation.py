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

from neuro_san_studio.coded_tools.openai_image_generation import OpenAIImageGeneration
from neuro_san_studio.coded_tools.openai_tool import OpenAITool

SLY_DATA: dict[str, Any] = {"llm_config": {"openai_api_key": "sly-key"}}


class TestOpenAIImageGeneration(IsolatedAsyncioTestCase):
    """
    Unit tests for OpenAIImageGeneration.

    OpenAITool.arun is replaced by a stand-in so no network is touched and no image is
    written or opened. The tests pin that the caller's sly_data is forwarded (the BYOK
    regression) and that text and error results are surfaced as before.
    """

    async def test_sly_data_is_forwarded_and_text_returned(self) -> None:
        """
        async_invoke forwards sly_data and the tool kwargs, and returns the text block's text.
        """
        arun = AsyncMock(return_value=[{"type": "text", "text": "Here is your cat."}])
        args: dict[str, Any] = {
            "query": "a cat",
            "openai_model": "gpt-5",
            "additional_kwargs": {"quality": "medium"},
        }
        with patch.object(OpenAITool, "arun", new=arun):
            result: str = await OpenAIImageGeneration().async_invoke(args, SLY_DATA)
        self.assertEqual(result, "Here is your cat.")
        arun.assert_awaited_once_with("a cat", "image_generation", "gpt-5", sly_data=SLY_DATA, quality="medium")

    async def test_error_string_is_passed_through(self) -> None:
        """
        An error string from OpenAITool (e.g. missing credentials) is returned to the agent verbatim.
        """
        arun = AsyncMock(return_value="OpenAI Error: Missing credentials")
        with patch.object(OpenAITool, "arun", new=arun):
            result: str = await OpenAIImageGeneration().async_invoke({"query": "a cat"}, SLY_DATA)
        self.assertEqual(result, "OpenAI Error: Missing credentials")

    async def test_missing_query_returns_error_without_calling_tool(self) -> None:
        """
        An empty query short-circuits with the documented error string.
        """
        arun = AsyncMock(return_value=[])
        with patch.object(OpenAITool, "arun", new=arun):
            result: str = await OpenAIImageGeneration().async_invoke({}, SLY_DATA)
        self.assertEqual(result, "Error: No query provided.")
        arun.assert_not_awaited()
