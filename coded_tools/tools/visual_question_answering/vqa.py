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

import logging
import os
import subprocess
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

logger = logging.getLogger(__name__)

# Adjust these to your repo/paths
working_directory = os.getcwd()
REPO_DIR = os.path.join(working_directory, "..", "ml-fastvlm")
PREDICT = os.path.join(REPO_DIR, "predict.py")
PREDICT_VIDEO = os.path.join(REPO_DIR, "predict_video.py")
MODEL_PATH = os.path.join(REPO_DIR, "checkpoints")
PYTHON_CMD = os.path.join(REPO_DIR, "venv/bin/python")
ACCEPTABLE_MODEL_NAMES = [
    "llava-fastvithd_1.5b_stage2",
    "llava-fastvithd_7b_stage3",
    "llava-fastvithd_0.5b_stage2",
    "llava-fastvithd_1.5b_stage3",
    "llava-fastvithd_0.5b_stage3",
    "llava-fastvithd_7b_stage2",
]
# Listing just the more common image extensions
# More extensions are supported by PIL library
# and can be added to this list if necessary
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"]

# Listing just the more common video extensions
# More extensions are supported by open-cv library
# and can be added to this list if necessary
VIDEO_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv"]

DEFAULT_MODEL_NAME = "llava-fastvithd_0.5b_stage3"
DEFAULT_NUM_OF_FRAMES = 8
DEFAULT_MAX_NUM_OF_TOKENS = 128
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT = 120


class VisualQuestionAnswering(CodedTool):
    """
    A tool that allows you to query an image or a video.
    """

    # pylint: disable=too-many-locals,too-many-return-statements
    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Provide an answer for a query on an image/video
        :param args: An dictionary with the following fields
                     - query: question we want the model to answer (mandatory)
                     - model_name: name of the ml-fastvlm model to use to answer the query (optional)
                     - expected_num_of_frames: number of frames to capture in a video input (optional)
                     - max_new_tokens: maximum number of tokens returned as an answer (optional)
                     - temperature: determines the randomness in the model (optional)
                     - timeout_sec: timeout in seconds when calling the model (optional)


        :param sly_data: A dictionary containing parameters that should be kept out of the chat stream.
                         Keys expected for this implementation are:
                         - "file_path": The path to the image/video file

        :return:
            In case of successful execution:
                A dictionary containing:
                    "answer": the answer to the query about the image/video file.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        tool_name = self.__class__.__name__
        logger.debug("========== Calling %s ==========", tool_name)

        logger.debug("args: %s", args)
        query: str = args.get("query", None)
        if query is None:
            return "Error: No query provided."
        model_name: int = args.get("model_name", DEFAULT_MODEL_NAME)
        if model_name not in ACCEPTABLE_MODEL_NAMES:
            return (
                "Error: model name "
                + model_name
                + " not among valid model names ("
                + ",".join(ACCEPTABLE_MODEL_NAMES)
                + ")"
            )
        expected_num_of_frames: int = int(args.get("expected_num_of_frames", DEFAULT_NUM_OF_FRAMES))
        max_new_tokens: int = int(args.get("max_new_tokens", DEFAULT_MAX_NUM_OF_TOKENS))
        temperature: float = float(args.get("temperature", DEFAULT_TEMPERATURE))
        timeout_sec: int = int(args.get("timeout_sec", DEFAULT_TIMEOUT))

        model = os.path.join(MODEL_PATH, model_name)

        # Parse the sly data
        # NOTE: sly_data may contain secrets - never log it
        # Get the file path.
        file_path: str = str(sly_data.get("file_path", ""))
        if file_path == "":
            return "Error: file_path is empty. Please specify an image/video file path"

        # Convert extension to lowercase as the list of supported extensions are in lowercase
        extension = Path(file_path).suffix.lower()

        #
        # Process image file
        #
        if extension in IMAGE_EXTENSIONS:
            logger.debug("It's an image!")

            # Call predict.py
            cmd = [
                PYTHON_CMD,
                PREDICT,
                "--model-path",
                model,
                "--image-file",
                file_path,
                "--prompt",
                query,
            ]
        #
        # Process video file
        #
        elif extension in VIDEO_EXTENSIONS:
            logger.debug("It's a video!")

            # Call predict.py
            cmd = [
                PYTHON_CMD,
                PREDICT_VIDEO,
                "--model-path",
                model,
                "--video-path",
                file_path,
                "--prompt",
                query,
                "--expected_num_of_frames",
                str(expected_num_of_frames),
                "--max_new_tokens",
                str(max_new_tokens),
                "--temperature",
                str(temperature),
            ]

        #
        # Invalid extension!
        #
        else:
            return (
                "Error: File extension is "
                + extension
                + ". Only "
                + ",".join(IMAGE_EXTENSIONS)
                + " and "
                + ",".join(VIDEO_EXTENSIONS)
                + " are allowed."
            )

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,  # don’t raise automatically; we’ll return stderr if needed
            )
        except subprocess.TimeoutExpired:
            return "Query timed out after " + timeout_sec + " seconds"

        # Parse/return
        payload = {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
        if proc.returncode != 0:
            return (
                "Error: exit_code: "
                + str(payload["exit_code"])
                + " , stdout: "
                + payload["stdout"]
                + ", stderr: "
                + payload["stderr"]
            )

        logger.debug("-----------------------")
        logger.debug("%s response: %s", tool_name, payload["stdout"])
        logger.debug("========== Done with %s ==========", tool_name)
        return payload["stdout"]

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
