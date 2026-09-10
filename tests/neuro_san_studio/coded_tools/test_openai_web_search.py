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

from neuro_san_studio.coded_tools.openai_tool import OpenAITool
from neuro_san_studio.coded_tools.openai_web_search import OpenAIWebSearch

SLY_DATA: dict[str, Any] = {"llm_config": {"openai_api_key": "sly-key"}}
CONTENT: list[dict[str, Any]] = [{"type": "text", "text": "found"}]


class TestOpenAIWebSearch(IsolatedAsyncioTestCase):
    """
    Unit tests for OpenAIWebSearch.

    OpenAITool.arun is replaced by a stand-in so no network is touched. The tests pin that
    the caller's sly_data is forwarded (the BYOK regression) along with the existing arguments.
    """

    async def test_sly_data_is_forwarded_to_openai_tool(self) -> None:
        """
        async_invoke passes sly_data, the model and the tool kwargs through to OpenAITool.arun.
        """
        arun = AsyncMock(return_value=CONTENT)
        args: dict[str, Any] = {
            "query": "news",
            "openai_model": "gpt-5",
            "additional_kwargs": {"search_context_size": "low"},
        }
        with patch.object(OpenAITool, "arun", new=arun):
            result: Any = await OpenAIWebSearch().async_invoke(args, SLY_DATA)
        self.assertEqual(result, CONTENT)
        arun.assert_awaited_once_with(
            "news", "web_search_preview", "gpt-5", sly_data=SLY_DATA, search_context_size="low"
        )

    async def test_missing_query_returns_error_without_calling_tool(self) -> None:
        """
        An empty query short-circuits with the documented error string.
        """
        arun = AsyncMock(return_value=CONTENT)
        with patch.object(OpenAITool, "arun", new=arun):
            result: Any = await OpenAIWebSearch().async_invoke({}, SLY_DATA)
        self.assertEqual(result, "Error: No query provided.")
        arun.assert_not_awaited()
