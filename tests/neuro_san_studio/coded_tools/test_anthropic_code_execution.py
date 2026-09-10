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

from neuro_san_studio.coded_tools.anthropic_code_execution import CODE_EXECUTION_BETA
from neuro_san_studio.coded_tools.anthropic_code_execution import CODE_EXECUTION_TOOL_TYPE
from neuro_san_studio.coded_tools.anthropic_code_execution import AnthropicCodeExecution
from neuro_san_studio.coded_tools.anthropic_tool import AnthropicTool

# Patch the names in the module under test.
MODULE = "neuro_san_studio.coded_tools.anthropic_code_execution"
SLY_DATA: dict[str, Any] = {"llm_config": {"anthropic_api_key": "sly-key"}}
TEXT_CONTENT: list[dict[str, Any]] = [{"type": "text", "text": "done"}]
FILE_CONTENT: list[dict[str, Any]] = [
    {"type": "code_execution_tool_result", "content": {"content": [{"file_id": "file_1"}]}},
]


class TestAnthropicCodeExecution(IsolatedAsyncioTestCase):
    """
    Unit tests for AnthropicCodeExecution.

    AnthropicTool.arun and the raw Anthropic client are replaced by stand-ins so no network is
    touched. The tests pin that sly_data is forwarded to the tool call and that the file download
    authenticates with the same resolved key instead of silently reading the environment.
    """

    async def test_sly_data_is_forwarded_to_anthropic_tool(self) -> None:
        """
        async_invoke passes the caller's sly_data through to AnthropicTool.arun unchanged.
        """
        arun = AsyncMock(return_value=TEXT_CONTENT)
        with patch.object(AnthropicTool, "arun", new=arun):
            result: Any = await AnthropicCodeExecution().async_invoke({"query": "print(1)"}, SLY_DATA)
        self.assertEqual(result, TEXT_CONTENT)
        arun.assert_awaited_once_with(
            query="print(1)",
            tool_type=CODE_EXECUTION_TOOL_TYPE,
            tool_name="code_execution",
            anthropic_model=None,
            betas=[CODE_EXECUTION_BETA],
            sly_data=SLY_DATA,
        )

    async def test_save_file_receives_resolved_key(self) -> None:
        """
        When files were generated and save_file is requested, the BYOK key is handed to save_file.
        """
        arun = AsyncMock(return_value=FILE_CONTENT)
        with (
            patch.object(AnthropicTool, "arun", new=arun),
            patch.object(AnthropicCodeExecution, "save_file") as save_file,
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}),
        ):
            await AnthropicCodeExecution().async_invoke({"query": "plot", "save_file": True}, SLY_DATA)
        # save_file is patched on the class, so the call is unbound: (file_ids, api_key).
        save_file.assert_called_once_with(["file_1"], "sly-key")

    async def test_save_file_receives_env_key_without_sly_data(self) -> None:
        """
        Without a BYOK key in sly_data, save_file is handed the ANTHROPIC_API_KEY environment value.
        """
        arun = AsyncMock(return_value=FILE_CONTENT)
        with (
            patch.object(AnthropicTool, "arun", new=arun),
            patch.object(AnthropicCodeExecution, "save_file") as save_file,
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}),
        ):
            await AnthropicCodeExecution().async_invoke({"query": "plot", "save_file": True}, {})
        save_file.assert_called_once_with(["file_1"], "env-key")

    async def test_save_file_not_called_without_flag(self) -> None:
        """
        Generated files are left in the container when save_file was not requested.
        """
        arun = AsyncMock(return_value=FILE_CONTENT)
        with patch.object(AnthropicTool, "arun", new=arun), patch.object(AnthropicCodeExecution, "save_file") as save:
            await AnthropicCodeExecution().async_invoke({"query": "plot"}, SLY_DATA)
        save.assert_not_called()

    def test_save_file_builds_client_with_key(self) -> None:
        """
        save_file constructs the Anthropic client with the resolved key and downloads each file.
        """
        anthropic_cls = MagicMock(name="Anthropic")
        client: MagicMock = anthropic_cls.return_value
        client.beta.files.retrieve_metadata.return_value.filename = "output.png"
        with patch(f"{MODULE}.Anthropic", anthropic_cls), patch(f"{MODULE}.webbrowser.open") as browser_open:
            AnthropicCodeExecution().save_file(["file_1"], "sly-key")
        self.assertEqual(anthropic_cls.call_args.kwargs["api_key"], "sly-key")
        client.beta.files.retrieve_metadata.assert_called_once_with("file_1")
        client.beta.files.download.assert_called_once_with("file_1")
        client.beta.files.download.return_value.write_to_file.assert_called_once_with("output.png")
        browser_open.assert_called_once()
