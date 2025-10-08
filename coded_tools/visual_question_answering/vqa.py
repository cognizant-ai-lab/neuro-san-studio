# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Union

from neuro_san.interfaces.coded_tool import CodedTool

# Adjust these to your repo/paths
working_directory = os.getcwd()
REPO_DIR = os.path.join(working_directory, "..", "ml-fastvlm")
PREDICT = os.path.join(REPO_DIR, "predict.py")
PREDICT_VIDEO = os.path.join(REPO_DIR, "predict_video.py")
MODEL_PATH = os.path.join(REPO_DIR, "checkpoints")
DEFAULT_MODEL = os.path.join(MODEL_PATH, "llava-fastvithd_0.5b_stage3")
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


class VisualQuestionAnswering(CodedTool):
    """
    A tool that updates a running cost each time it is called.
    """

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Updates the passed running cost each time it's called.
        :param args: An empty dictionary (not used)

        :param sly_data: A dictionary containing parameters that should be kept out of the chat stream.
                         Keys expected for this implementation are:
                         - "file_path": The path to the image/video file

        :return:
            In case of successful execution:
                A dictionary containing:
                    "answer": the answer to the query about the image/video file.
                    "file_path": The path to the image/video file
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        tool_name = self.__class__.__name__
        print(f"========== Calling {tool_name} ==========")

        print(f"args: {args}")
        query: str = args.get("query", None)
        if query is None:
            return "Error: No query provided."
        timeout_sec: str = int(args.get("timeout_sec", "120"))

        # Parse the sly data
        print(f"sly_data: {sly_data}")
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
            print("It's an image!")

            # Call predict.py
            cmd = [
                PYTHON_CMD,
                PREDICT,
                "--model-path",
                DEFAULT_MODEL,
                "--image-file",
                file_path,
                "--prompt",
                query,
            ]
        #
        # Process video file
        #
        elif extension in VIDEO_EXTENSIONS:
            print("It's a video!")

            # Call predict.py
            cmd = [
                PYTHON_CMD,
                PREDICT_VIDEO,
                "--model-path",
                DEFAULT_MODEL,
                "--video-path",
                file_path,
                "--prompt",
                query,
                "--expected_num_of_frames",
                # str(expected_num_of_frames),
                str(8),
                "--max_new_tokens",
                # str(max_new_tokens),
                str(128),
                "--temperature",
                # str(temperature),
                str(0.8),
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

        print("-----------------------")
        print(f"{tool_name} response: ", payload["stdout"])
        print(f"========== Done with {tool_name} ==========")
        return payload["stdout"]

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Delegates to the synchronous invoke method because it's quick, non-blocking.
        """
        return self.invoke(args, sly_data)
