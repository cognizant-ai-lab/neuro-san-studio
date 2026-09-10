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
from unittest.mock import patch

from neuro_san_studio.coded_tools.openai_video_generation import OpenAIVideoGeneration

SLY_DATA: dict[str, Any] = {"llm_config": {"openai_api_key": "sly-key"}}
SLY_HEADERS: dict[str, str] = {"Authorization": "Bearer sly-key", "Content-Type": "application/json"}
ENV_HEADERS: dict[str, str] = {"Authorization": "Bearer env-key", "Content-Type": "application/json"}
# What the pre-fix module-level constant produced when OPENAI_API_KEY was unset; the API rejects it.
NONE_HEADERS: dict[str, str] = {"Authorization": "Bearer None", "Content-Type": "application/json"}
# Prefix is in .lycheeignore so the link checker never tries to open it.
VIDEO_URI = "file:///path/to/vid_1.mp4"


class TestOpenAIVideoGeneration(IsolatedAsyncioTestCase):
    """
    Unit tests for OpenAIVideoGeneration.

    The HTTP helpers are replaced by stand-ins so no network is touched. The tests pin that the
    bearer token is built per call from the BYOK key (or the environment) and that the same
    headers reach every request of the create/remix, poll and download sequence.
    """

    def test_build_headers_uses_bearer_token(self) -> None:
        """
        build_headers wraps the key as a bearer token with a JSON content type.
        """
        self.assertEqual(
            OpenAIVideoGeneration.build_headers("abc"),
            {
                "Authorization": "Bearer abc",
                "Content-Type": "application/json",
            },
        )

    async def test_sly_data_key_reaches_every_request(self) -> None:
        """
        A BYOK key in sly_data is used for create, poll and download even when OPENAI_API_KEY is set.
        """
        with (
            patch.object(OpenAIVideoGeneration, "_create_video", new=AsyncMock(return_value="vid_1")) as create,
            patch.object(
                OpenAIVideoGeneration, "_poll_status", new=AsyncMock(return_value={"status": "completed"})
            ) as poll,
            patch.object(OpenAIVideoGeneration, "_display_video", new=AsyncMock(return_value=VIDEO_URI)) as display,
            patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}),
        ):
            result: str = await OpenAIVideoGeneration().async_invoke({"query": "a cat"}, SLY_DATA)
        self.assertEqual(result, f"Video generation completed with id vid_1. Saved to: {VIDEO_URI}")
        # The helpers are patched on the class, so the calls are unbound: (session, headers, ...).
        self.assertEqual(create.call_args.args[1], SLY_HEADERS)
        self.assertEqual(create.call_args.args[2:], ("a cat", "sora-2", "720x1280", "4"))
        self.assertEqual(poll.call_args.args[1:], (SLY_HEADERS, "vid_1"))
        self.assertEqual(display.call_args.args[1:], (SLY_HEADERS, "vid_1", False, False))

    async def test_env_key_used_without_sly_data(self) -> None:
        """
        Without sly_data the bearer token comes from OPENAI_API_KEY, resolved at call time.
        """
        with (
            patch.object(OpenAIVideoGeneration, "_create_video", new=AsyncMock(return_value="vid_1")) as create,
            patch.object(OpenAIVideoGeneration, "_poll_status", new=AsyncMock(return_value={"status": "completed"})),
            patch.object(OpenAIVideoGeneration, "_display_video", new=AsyncMock(return_value=VIDEO_URI)),
            patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}),
        ):
            await OpenAIVideoGeneration().async_invoke({"query": "a cat"}, {})
        self.assertEqual(create.call_args.args[1], ENV_HEADERS)

    async def test_remix_path_uses_same_headers(self) -> None:
        """
        The remix request carries the same per-call headers as a fresh generation.
        """
        with (
            patch.object(OpenAIVideoGeneration, "_remix_video", new=AsyncMock(return_value="vid_2")) as remix,
            patch.object(OpenAIVideoGeneration, "_poll_status", new=AsyncMock(return_value={"status": "completed"})),
            patch.object(OpenAIVideoGeneration, "_display_video", new=AsyncMock(return_value=VIDEO_URI)),
            patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}),
        ):
            await OpenAIVideoGeneration().async_invoke({"query": "make it night", "video_id": "vid_1"}, SLY_DATA)
        self.assertEqual(remix.call_args.args[1:], (SLY_HEADERS, "vid_1", "make it night"))

    async def test_none_key_when_no_source(self) -> None:
        """
        With neither source available the token is literally "Bearer None", matching the pre-fix behavior
        when OPENAI_API_KEY was unset, so the API rejects the request exactly as it always did.
        """
        with (
            patch.object(OpenAIVideoGeneration, "_create_video", new=AsyncMock(return_value="vid_1")) as create,
            patch.object(OpenAIVideoGeneration, "_poll_status", new=AsyncMock(return_value={"status": "completed"})),
            patch.object(OpenAIVideoGeneration, "_display_video", new=AsyncMock(return_value=VIDEO_URI)),
            patch.dict(os.environ, {}, clear=True),
        ):
            await OpenAIVideoGeneration().async_invoke({"query": "a cat"}, {})
        self.assertEqual(create.call_args.args[1], NONE_HEADERS)
        self.assertEqual(OpenAIVideoGeneration.build_headers(None), NONE_HEADERS)

    async def test_status_request_receives_headers(self) -> None:
        """
        The per-request headers reach the status request inside the polling loop, not only the loop's entry point.
        """
        with (
            patch.object(OpenAIVideoGeneration, "_create_video", new=AsyncMock(return_value="vid_1")),
            patch.object(
                OpenAIVideoGeneration, "_get_status", new=AsyncMock(return_value={"status": "completed"})
            ) as get_status,
            patch.object(OpenAIVideoGeneration, "_display_video", new=AsyncMock(return_value=VIDEO_URI)),
            patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}),
        ):
            await OpenAIVideoGeneration().async_invoke({"query": "a cat"}, SLY_DATA)
        # "completed" on the first poll returns before any sleep, so exactly one status call is made.
        get_status.assert_awaited_once()
        self.assertEqual(get_status.call_args.args[1:], (SLY_HEADERS, "vid_1"))
