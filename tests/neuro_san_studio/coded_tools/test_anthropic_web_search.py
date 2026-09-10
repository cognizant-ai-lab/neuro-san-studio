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

from neuro_san_studio.coded_tools.anthropic_tool import AnthropicTool
from neuro_san_studio.coded_tools.anthropic_web_search import WEB_SEARCH_TOOL_TYPE
from neuro_san_studio.coded_tools.anthropic_web_search import AnthropicWebSearch

SLY_DATA: dict[str, Any] = {"llm_config": {"anthropic_api_key": "sly-key"}}
CONTENT: list[dict[str, Any]] = [{"type": "text", "text": "found"}]


class TestAnthropicWebSearch(IsolatedAsyncioTestCase):
    """
    Unit tests for AnthropicWebSearch.

    AnthropicTool.arun is replaced by a stand-in so no network is touched. The tests pin that
    the caller's sly_data is forwarded (the BYOK regression) along with the existing arguments.
    """

    async def test_sly_data_is_forwarded_to_anthropic_tool(self) -> None:
        """
        async_invoke passes sly_data, the model and the tool kwargs through to AnthropicTool.arun.
        """
        arun = AsyncMock(return_value=CONTENT)
        args: dict[str, Any] = {
            "query": "news",
            "anthropic_model": "claude-sonnet-4-5",
            "additional_kwargs": {"max_uses": 3},
        }
        with patch.object(AnthropicTool, "arun", new=arun):
            result: Any = await AnthropicWebSearch().async_invoke(args, SLY_DATA)
        self.assertEqual(result, CONTENT)
        arun.assert_awaited_once_with(
            query="news",
            tool_type=WEB_SEARCH_TOOL_TYPE,
            tool_name="web_search",
            anthropic_model="claude-sonnet-4-5",
            betas=None,
            sly_data=SLY_DATA,
            max_uses=3,
        )

    async def test_missing_query_returns_error_without_calling_tool(self) -> None:
        """
        An empty query short-circuits with the documented error string.
        """
        arun = AsyncMock(return_value=CONTENT)
        with patch.object(AnthropicTool, "arun", new=arun):
            result: Any = await AnthropicWebSearch().async_invoke({}, SLY_DATA)
        self.assertEqual(result, "Error: No query provided.")
        arun.assert_not_awaited()
