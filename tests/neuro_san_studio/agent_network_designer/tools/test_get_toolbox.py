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
"""
Tests for GetToolbox's process-wide toolbox info cache: what it returns for a file with tools, a file that defines
no tools and a missing file, and when it reads the file again.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest import mock

from neuro_san_studio.agent_network_designer.tools.get_toolbox import GetToolbox

TOOLBOX_INFO_ENV_VAR: str = "AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE"

TWO_TOOLS: str = """
{
    "alpha": {
        "class": "alpha_module.Alpha",
        "description": "Does alpha."
    },
    "beta": {
        "class": "beta_module.Beta",
        "description": "Does beta."
    }
}
"""

ONE_TOOL: str = """
{
    "gamma": {
        "class": "gamma_module.Gamma",
        "description": "Does gamma."
    }
}
"""

# The same text with another tool name of the same length, so the two files have the same size.
ONE_OTHER_TOOL: str = ONE_TOOL.replace("gamma", "delta").replace("Gamma", "Delta")

NO_TOOLS: str = """
# No tools yet.
{
}
"""

# NO_TOOLS padded with spaces to ONE_TOOL's size, so a rewrite from one to the other keeps the size.
NO_TOOLS_SIZED_LIKE_ONE_TOOL: str = NO_TOOLS.ljust(len(ONE_TOOL))

# Two modification times far apart, so a rewrite between them is a change the fingerprint can see.
FIRST_MODIFICATION_TIME_NS: int = 1_700_000_000_000_000_000
SECOND_MODIFICATION_TIME_NS: int = 1_700_000_100_000_000_000


class TestGetToolbox(IsolatedAsyncioTestCase):
    """
    Behavior tests for GetToolbox.get_toolbox_info() and its process-wide cache.
    """

    def setUp(self) -> None:
        """
        Start from an empty cache, with the toolbox info variable pointing into a temporary folder.
        """
        GetToolbox.clear_shared_toolbox_info_for_testing()
        self.folder: Path = Path(tempfile.mkdtemp())
        self.toolbox_file: Path = self.folder / "toolbox_info.hocon"
        self.enterContext(mock.patch.dict(os.environ, {TOOLBOX_INFO_ENV_VAR: str(self.toolbox_file)}))

    def tearDown(self) -> None:
        """
        Remove the temporary folder and clear the cache so nothing loaded here reaches a later test.
        """
        shutil.rmtree(self.folder)
        GetToolbox.clear_shared_toolbox_info_for_testing()

    @staticmethod
    def _write_file(path: Path, text: str, modification_time_ns: int) -> None:
        """
        Write a file and set its modification time.

        :param path: The file to write.
        :param text: The HOCON text to write.
        :param modification_time_ns: The modification time to give the file, in nanoseconds.
        """
        # Bytes, so no platform newline translation changes the file's size.
        path.write_bytes(text.encode("utf-8"))
        os.utime(path, ns=(modification_time_ns, modification_time_ns))

    def _write_toolbox_file(self, text: str, modification_time_ns: int) -> None:
        """
        Write the toolbox info file that the variable points at and set its modification time.

        :param text: The HOCON text to write.
        :param modification_time_ns: The modification time to give the file, in nanoseconds.
        """
        self._write_file(self.toolbox_file, text, modification_time_ns)

    async def test_returns_each_tools_description(self) -> None:
        """
        A file with tools gives a mapping of each tool name to its description.
        """
        self._write_toolbox_file(TWO_TOOLS, FIRST_MODIFICATION_TIME_NS)

        tools: dict[str, str] = await GetToolbox.get_toolbox_info()

        expected: dict[str, str] = {
            "alpha": "Does alpha.",
            "beta": "Does beta.",
        }
        self.assertEqual(tools, expected)

    async def test_file_with_no_tools_is_cached_as_empty(self) -> None:
        """
        A file that defines no tools is a valid result, served from the cache until the file changes.
        """
        self._write_toolbox_file(NO_TOOLS_SIZED_LIKE_ONE_TOOL, FIRST_MODIFICATION_TIME_NS)
        first: dict[str, str] = await GetToolbox.get_toolbox_info()

        # New text with the same size and modification time: the fingerprint sees no change, so the cache answers.
        self._write_toolbox_file(ONE_TOOL, FIRST_MODIFICATION_TIME_NS)
        cached: dict[str, str] = await GetToolbox.get_toolbox_info()

        self.assertEqual(first, {})
        self.assertEqual(cached, {})

    async def test_edited_file_is_read_again(self) -> None:
        """
        A new modification time makes the next call read the file again, even when the size stays the same.
        """
        self._write_toolbox_file(ONE_TOOL, FIRST_MODIFICATION_TIME_NS)
        before: dict[str, str] = await GetToolbox.get_toolbox_info()

        self._write_toolbox_file(ONE_OTHER_TOOL, SECOND_MODIFICATION_TIME_NS)
        after: dict[str, str] = await GetToolbox.get_toolbox_info()

        self.assertEqual(before, {"gamma": "Does gamma."})
        self.assertEqual(after, {"delta": "Does delta."})

    async def test_rewrite_finishing_in_the_same_timestamp_tick_is_read_again(self) -> None:
        """
        A rewrite that keeps the modification time but changes the size is read again, so an empty read of a
        half-written file is not served after the rewrite finishes.
        """
        # A read that lands just after the rewrite truncated the file.
        self._write_toolbox_file("", FIRST_MODIFICATION_TIME_NS)
        truncated: dict[str, str] = await GetToolbox.get_toolbox_info()

        # The rewrite finishes within the same timestamp tick.
        self._write_toolbox_file(TWO_TOOLS, FIRST_MODIFICATION_TIME_NS)
        finished: dict[str, str] = await GetToolbox.get_toolbox_info()

        self.assertEqual(truncated, {})
        self.assertEqual(sorted(finished), ["alpha", "beta"])

    async def test_missing_file_gives_empty_and_is_read_once_it_appears(self) -> None:
        """
        A missing file gives an empty mapping for that call, and the file is read once it appears.
        """
        missing: dict[str, str] = await GetToolbox.get_toolbox_info()

        self._write_toolbox_file(ONE_TOOL, FIRST_MODIFICATION_TIME_NS)
        found: dict[str, str] = await GetToolbox.get_toolbox_info()

        self.assertEqual(missing, {})
        self.assertEqual(found, {"gamma": "Does gamma."})

    async def test_pointing_the_variable_at_another_file_switches_toolboxes(self) -> None:
        """
        The cache follows the toolbox info variable, so a server can swap the local file for the multi-user one.
        """
        self._write_toolbox_file(TWO_TOOLS, FIRST_MODIFICATION_TIME_NS)
        local: dict[str, str] = await GetToolbox.get_toolbox_info()

        # Same size and modification time as the first file, so only the path tells the two apart.
        multiuser_file: Path = self.toolbox_file.with_name("multiuser_toolbox_info.hocon")
        self._write_file(multiuser_file, NO_TOOLS.ljust(len(TWO_TOOLS)), FIRST_MODIFICATION_TIME_NS)
        with mock.patch.dict(os.environ, {TOOLBOX_INFO_ENV_VAR: str(multiuser_file)}):
            multiuser: dict[str, str] = await GetToolbox.get_toolbox_info()

        self.assertEqual(sorted(local), ["alpha", "beta"])
        self.assertEqual(multiuser, {})
