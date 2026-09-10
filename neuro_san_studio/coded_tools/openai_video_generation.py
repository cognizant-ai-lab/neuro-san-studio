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

import asyncio
import logging
import webbrowser
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import aiohttp
from neuro_san.interfaces.coded_tool import CodedTool

from neuro_san_studio.coded_tools.openai_tool import OpenAITool

URL_ENDPOINT = "https://api.openai.com/v1/videos"
POLL_INTERVAL = 5  # seconds between status checks
TIMEOUT = 600  # maximum wait time in seconds


class OpenAIVideoGeneration(CodedTool):
    """
    A CodedTool implementation for invoking OpenAI video generation using OpenAI API.

    See https://platform.openai.com/docs/guides/video-generation
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent or user. This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                - from calling agent
                    - "query" (str): Request from the user prompt.
                - from user
                    - "openai_model" (str): OpenAI model to call the tool. Default to sora-2.
                    - "additional_kwargs" (dict): Any additional arguments for the tool.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    - "llm_config" (dict, optional): BYOK keys sent by the client. When it holds
                        "openai_api_key", that key is used instead of the OPENAI_API_KEY env var.

        :return:
            In case of successful execution:
                Text string indicating video generation is completed.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """

        # Get query from args
        query: str = args.get("query")
        if not query:
            raise ValueError("Error: No query provided.")

        # Get video id to remix if provided
        video_id: str = args.get("video_id")

        # User-defined arguments
        openai_model: str = args.get("openai_model", "sora-2")
        size: str = args.get("size", "720x1280")
        seconds: str = args.get("seconds", "4")
        save_video_file: bool = args.get("save_video_file", False)
        open_in_browser: bool = args.get("open_in_browser", False)

        # Build the auth headers per call so a BYOK key in sly_data is honored. Reading
        # OPENAI_API_KEY into module constants at import time (the previous behavior) froze
        # the server's key and could never see a per-request key.
        headers: dict[str, str] = self.build_headers(OpenAITool.get_api_key(sly_data))

        async with aiohttp.ClientSession() as session:
            if video_id:
                # Remix existing video
                self.logger.info("Starting video remix for ID: %s", video_id)
                video_id = await self._remix_video(session, headers, video_id, query)
            else:
                self.logger.info("Starting new video generation.")
                # Start video generation job
                video_id = await self._create_video(session, headers, query, openai_model, size, seconds)

            if not video_id:
                # pylint: disable=broad-exception-raised
                raise Exception("Failed to create video rendering job.")
            self.logger.info("Video generation started with ID: %s", video_id)

            # Poll for completion
            status_data = await self._poll_status(session, headers, video_id)

            if status_data.get("status") != "completed":
                error_msg = status_data.get("error", "Unknown error")
                return f"Error: Video generation failed - {error_msg}"

            # Download and display video
            video_path = await self._display_video(session, headers, video_id, save_video_file, open_in_browser)

            if video_path:
                return f"Video generation completed with id {video_id}. Saved to: {video_path}"

            # pylint: disable=broad-exception-raised
            raise Exception("Failed to download generated video.")

    @staticmethod
    def build_headers(api_key: str | None) -> dict[str, str]:
        """
        Build the HTTP headers for the OpenAI videos endpoint.

        :param api_key: The OpenAI API key to send as a bearer token, already resolved from
                sly_data or the environment. None produces an unusable token and the API
                rejects the request, exactly as it did before when OPENAI_API_KEY was unset.
        :return: Headers carrying the bearer token and the JSON content type.
        """
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    async def _create_video(
        self,
        session: aiohttp.ClientSession,
        headers: dict[str, str],
        query: str,
        model: str,
        size: str,
        seconds: str,
    ) -> str | None:
        """
        Create a video generation job.

        :param session: aiohttp session
        :param headers: Request headers carrying the resolved bearer token
        :param query: The prompt for video generation
        :param model: The OpenAI video model, e.g. "sora-2"
        :param size: Video resolution, e.g. "720x1280"
        :param seconds: Video duration in seconds
        :return: Video ID if successful, None otherwise
        """
        payload = {"prompt": query, "model": model, "size": size, "seconds": str(seconds)}

        try:
            async with session.post(URL_ENDPOINT, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                self.logger.info("Video creation response: %s", data)
                return data.get("id")
        # pylint: disable=broad-exception-caught
        except Exception as exception:
            self.logger.error("Error creating video: %s", exception)
            self.logger.error("Exception details: %s", data)
            return None

    async def _remix_video(
        self,
        session: aiohttp.ClientSession,
        headers: dict[str, str],
        video_id: str,
        query: str,
    ) -> str | None:
        """
        Create a video remix job.

        :param session: aiohttp session
        :param headers: Request headers carrying the resolved bearer token
        :param video_id: The ID of the existing video to remix
        :param query: The prompt describing the remix
        :return: Video ID if successful, None otherwise
        """
        payload = {
            "prompt": query,
        }

        try:
            async with session.post(f"{URL_ENDPOINT}/{video_id}/remix", headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                self.logger.info("Video remix response: %s", data)
                return data.get("id")
        # pylint: disable=broad-exception-caught
        except Exception as exception:
            self.logger.error("Error remixing video: %s", exception)
            self.logger.error("Exception details: %s", data)
            return None

    async def _get_status(
        self, session: aiohttp.ClientSession, headers: dict[str, str], video_id: str
    ) -> dict[str, Any]:
        """
        Get the current status of a video generation job.

        :param session: aiohttp session
        :param headers: Request headers carrying the resolved bearer token
        :param video_id: The ID of the video to check
        :return: The status payload returned by the API
        """
        async with session.get(f"{URL_ENDPOINT}/{video_id}", headers=headers) as response:
            response.raise_for_status()
            return await response.json()

    async def _poll_status(
        self, session: aiohttp.ClientSession, headers: dict[str, str], video_id: str
    ) -> dict[str, Any]:
        """
        Poll the status of video generation until it is complete or times out.

        :param session: aiohttp session
        :param headers: Request headers carrying the resolved bearer token
        :param video_id: The ID of the video to poll
        :return: The final status response
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > TIMEOUT:
                raise asyncio.TimeoutError(f"Video generation exceeded timeout of {TIMEOUT}s")

            status_data = await self._get_status(session, headers, video_id)
            status = status_data.get("status")
            progress = status_data.get("progress")

            self.logger.info("Video status: %s, progress: %s", status, progress)

            if status == "completed":
                self.logger.info("Video generation completed successfully.")
                return status_data
            if status == "failed":
                self.logger.error("Video generation failed.")
                return status_data

            await asyncio.sleep(POLL_INTERVAL)

    async def _display_video(
        self,
        session: aiohttp.ClientSession,
        headers: dict[str, str],
        video_id: str,
        save_video_file: bool = False,
        open_in_browser: bool = True,
    ) -> str | None:
        """
        Download video from OpenAI, save it, and optionally open in browser.

        :param session: aiohttp session
        :param headers: Request headers carrying the resolved bearer token
        :param video_id: The ID of the video to download
        :param save_video_file: Whether to save as permanent file
        :param open_in_browser: Whether to open video in browser
        :return: Path to saved video file, or None on error
        """
        try:
            async with session.get(f"{URL_ENDPOINT}/{video_id}/content", headers=headers) as response:
                response.raise_for_status()
                video_data = await response.read()

            if not video_data:
                self.logger.error("No video data received")
                return None

            # Determine file path
            if save_video_file:
                path = Path(f"{video_id}.mp4")
            else:
                with NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    path = Path(tmp.name)

            # Write file
            path.write_bytes(video_data)

            file_uri = path.absolute().as_uri()
            self.logger.info("Saved video to: %s", file_uri)

            if open_in_browser:
                webbrowser.open(file_uri)

            return file_uri
        # pylint: disable=broad-exception-caught
        except Exception as exception:
            self.logger.error("Error downloading/displaying video: %s", exception)
            return None
