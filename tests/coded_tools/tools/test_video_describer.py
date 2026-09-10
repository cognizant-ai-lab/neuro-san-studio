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
import sys
from importlib.util import find_spec
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

# opencv is not a declared dependency of the studio (the tool itself disables import-error for
# it), so CI has no cv2. Skipping the module there would leave the BYOK regression permanently
# unexecuted in CI, so instead stand in a stub module when the real one is absent. The tests
# patch cv2.VideoCapture explicitly, so the stub is never asked to decode anything.
if find_spec("cv2") is None:
    sys.modules["cv2"] = MagicMock(name="cv2")

# The import must stay below the stub so environments without cv2 can load the tool.
from coded_tools.tools.video_describer import VideoDescriber  # pylint: disable=wrong-import-position

# Patch the names in the module under test.
MODULE = "coded_tools.tools.video_describer"
SLY_DATA: dict[str, Any] = {"llm_config": {"openai_api_key": "sly-key"}}


class TestVideoDescriber(IsolatedAsyncioTestCase):
    """
    Unit tests for VideoDescriber.

    cv2.VideoCapture and ChatOpenAI are replaced by stand-ins so no file is read and no network
    is touched. The tests pin which api_key reaches ChatOpenAI under each BYOK scenario.
    """

    @staticmethod
    def _chat_openai_mock(text: str) -> MagicMock:
        """
        Build a stand-in for the ChatOpenAI class whose instances answer ainvoke with the given text.

        :param text: The description the fake model should return.
        :return: A MagicMock usable as the patched ChatOpenAI class.
        """
        message = MagicMock(name="AIMessage")
        message.text = text
        llm = MagicMock(name="ChatOpenAI instance")
        llm.ainvoke = AsyncMock(return_value=message)
        return MagicMock(name="ChatOpenAI", return_value=llm)

    @staticmethod
    def _closed_capture() -> MagicMock:
        """
        Build a stand-in VideoCapture that reports no frames.

        :return: A MagicMock whose isOpened() is False so the frame loop exits at once.
        """
        capture = MagicMock(name="VideoCapture instance")
        capture.isOpened.return_value = False
        return capture

    async def test_sly_data_key_is_passed_to_chat_openai(self) -> None:
        """
        A BYOK key in sly_data reaches ChatOpenAI even when OPENAI_API_KEY is also set.
        """
        chat_cls: MagicMock = self._chat_openai_mock("A cat video.")
        with (
            patch(f"{MODULE}.cv2.VideoCapture", return_value=self._closed_capture()),
            patch(f"{MODULE}.ChatOpenAI", chat_cls),
            patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}),
        ):
            result: str = await VideoDescriber().async_invoke({"file_path": "/path/to/video.mp4"}, SLY_DATA)
        self.assertEqual(result, "A cat video.")
        self.assertEqual(chat_cls.call_args.kwargs["api_key"], "sly-key")
        self.assertEqual(chat_cls.call_args.kwargs["model"], "gpt-4o")

    async def test_env_key_used_without_sly_data(self) -> None:
        """
        Without sly_data the OPENAI_API_KEY environment variable is passed explicitly.
        """
        chat_cls: MagicMock = self._chat_openai_mock("A cat video.")
        with (
            patch(f"{MODULE}.cv2.VideoCapture", return_value=self._closed_capture()),
            patch(f"{MODULE}.ChatOpenAI", chat_cls),
            patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}),
        ):
            await VideoDescriber().async_invoke({"file_path": "/path/to/video.mp4", "openai_model": "gpt-5"}, {})
        self.assertEqual(chat_cls.call_args.kwargs["api_key"], "env-key")
        self.assertEqual(chat_cls.call_args.kwargs["model"], "gpt-5")
