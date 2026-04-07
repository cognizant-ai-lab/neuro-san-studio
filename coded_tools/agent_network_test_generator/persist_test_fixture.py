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

import json
import logging
import os
import re
from typing import Any
from typing import Union

import aiofiles
from neuro_san.interfaces.coded_tool import CodedTool

_REFERENCE_COMMENT: str = """\

# This file defines everything necessary for a data-driven test.
# The schema specifications for this file are documented here:
# https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md
"""


class PersistTestFixture(CodedTool):
    """
    CodedTool implementation that persists a generated test fixture
    as a HOCON file under ``tests/fixtures/``.

    The tool expects a JSON-serialisable dictionary that conforms to the
    neuro-san data-driven test case schema (agent, success_ratio,
    interactions with per-interaction timeout_in_seconds, etc.) and writes it to disk in
    human-readable JSON (which is valid HOCON).
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        :param args: A dictionary with the following keys:
                "test_fixture": a dictionary representing the test fixture
                    following the neuro-san test case HOCON schema.
                "file_name": the output file name (without directory prefix),
                    e.g. "coffee_where_8am.hocon".

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys used by this implementation:
                    "target_agent_name": the agent network name used to derive
                        the output subdirectory (e.g. "basic/coffee_finder_advanced").

        :return:
            In case of successful execution:
                A confirmation string with the path of the written file.
            otherwise:
                A text string error message.
        """
        logger = logging.getLogger(self.__class__.__name__)

        test_fixture: dict[str, Any] = args.get("test_fixture")
        if not test_fixture:
            return "Error: No 'test_fixture' provided."

        file_name: str = args.get("file_name", "")
        if not file_name:
            return "Error: No 'file_name' provided."

        # Ensure the file name ends with .hocon
        if not file_name.endswith(".hocon"):
            file_name += ".hocon"

        # Sanitise the file name
        file_name = re.sub(r"[^\w.\-]", "_", file_name)

        # Derive the output directory from the target agent name
        target_agent_name: str = sly_data.get("target_agent_name", "")
        if not target_agent_name:
            target_agent_name = test_fixture.get("agent", "unknown")

        output_dir: str = os.path.join("tests", "fixtures", target_agent_name)
        os.makedirs(output_dir, exist_ok=True)

        output_path: str = os.path.join(output_dir, file_name)

        logger.info(">>>>>>>>>>>>>>>>>>>Persisting Test Fixture>>>>>>>>>>>>>>>>>>")
        logger.info("Output path: %s", output_path)

        # Build the file content
        fixture_json: str = json.dumps(test_fixture, indent=4, ensure_ascii=False)
        content: str = _REFERENCE_COMMENT.lstrip("\n") + "\n" + fixture_json + "\n"

        try:
            async with aiofiles.open(output_path, "w", encoding="utf-8") as fout:
                await fout.write(content)
        except OSError as exc:
            error_msg = f"Error: Could not write file '{output_path}': {exc}"
            logger.error(error_msg)
            return error_msg

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return f"Test fixture successfully saved to: {output_path}"
