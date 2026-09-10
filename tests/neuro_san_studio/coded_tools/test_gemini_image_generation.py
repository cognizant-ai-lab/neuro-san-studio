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

from neuro_san_studio.coded_tools.gemini_image_generation import GeminiImageGeneration

# Patch the name in the module under test, not "google.genai.Client".
MODULE = "neuro_san_studio.coded_tools.gemini_image_generation"
SLY_DATA: dict[str, Any] = {"llm_config": {"google_api_key": "sly-key"}}


class TestGeminiImageGeneration(IsolatedAsyncioTestCase):
    """
    Unit tests for GeminiImageGeneration.

    google.genai.Client is replaced by a stand-in so no network is touched. The tests pin which
    api_key reaches the client constructor under each BYOK scenario and that the request
    plumbing (model, prompt) and text extraction are unchanged.
    """

    @staticmethod
    def _client_mock(parts: list[Any]) -> MagicMock:
        """
        Build a stand-in for the google.genai Client class whose generate_content returns the given parts.

        :param parts: The response parts the fake generate_content call should return.
        :return: A MagicMock usable as the patched Client class.
        """
        response = MagicMock(name="GenerateContentResponse")
        response.parts = parts
        client = MagicMock(name="Client instance")
        client.aio.models.generate_content = AsyncMock(return_value=response)
        return MagicMock(name="Client", return_value=client)

    @staticmethod
    def _text_part(text: str) -> MagicMock:
        """
        Build a text-only response part.

        :param text: The text the part carries.
        :return: A MagicMock part with no inline image data.
        """
        part = MagicMock(name="Part")
        part.text = text
        # Explicitly no image, otherwise the truthy MagicMock would be treated as a Blob.
        part.inline_data = None
        return part

    async def test_sly_data_key_is_passed_to_client(self) -> None:
        """
        A BYOK key in sly_data reaches the Gemini client even when GOOGLE_API_KEY is also set.
        """
        client_cls: MagicMock = self._client_mock([])
        with patch(f"{MODULE}.Client", client_cls), patch.dict(os.environ, {"GOOGLE_API_KEY": "env-key"}):
            result: str = await GeminiImageGeneration().async_invoke({"query": "a cat"}, SLY_DATA)
        self.assertEqual(result, "Image generation completed.")
        self.assertEqual(client_cls.call_args.kwargs["api_key"], "sly-key")
        generate: AsyncMock = client_cls.return_value.aio.models.generate_content
        self.assertEqual(generate.call_args.kwargs["model"], "gemini-2.5-flash-image")
        self.assertEqual(generate.call_args.kwargs["contents"], "a cat")

    async def test_env_key_used_without_sly_data(self) -> None:
        """
        Without sly_data the GOOGLE_API_KEY environment variable is passed explicitly.
        """
        client_cls: MagicMock = self._client_mock([])
        with patch(f"{MODULE}.Client", client_cls), patch.dict(os.environ, {"GOOGLE_API_KEY": "env-key"}):
            await GeminiImageGeneration().async_invoke({"query": "a cat"}, {})
        self.assertEqual(client_cls.call_args.kwargs["api_key"], "env-key")

    async def test_none_key_when_no_source(self) -> None:
        """
        With neither source available, None is passed so google.genai runs its own env lookup.
        """
        client_cls: MagicMock = self._client_mock([])
        with patch(f"{MODULE}.Client", client_cls), patch.dict(os.environ, {}, clear=True):
            await GeminiImageGeneration().async_invoke({"query": "a cat"}, {})
        self.assertIsNone(client_cls.call_args.kwargs["api_key"])

    async def test_text_part_is_returned(self) -> None:
        """
        Text returned alongside (or instead of) an image is surfaced as the tool result.
        """
        client_cls: MagicMock = self._client_mock([self._text_part("Here is your cat.")])
        with patch(f"{MODULE}.Client", client_cls), patch.dict(os.environ, {}, clear=True):
            result: str = await GeminiImageGeneration().async_invoke({"query": "a cat"}, SLY_DATA)
        self.assertEqual(result, "Here is your cat.")
