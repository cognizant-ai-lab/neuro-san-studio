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

"""Implementation of the `ns new tool` command."""

import os
import re
from typing import Optional

from rich.console import Console

from neuro_san_studio.utils.cli_status import CliStatus

_console = Console()

_TOOL_PY = '''\
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
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool


class __CLASS_NAME__(CodedTool):
    """
    CodedTool implementation for __CLASS_NAME__.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Invoke the tool.

        :param args: Dictionary of arguments passed by the calling agent.
        :param sly_data: Read-only side-channel data shared across the agent hierarchy.
        :return: Result string returned to the calling agent.
        """
        # TODO: implement your tool logic here
        return "Not yet implemented."
'''

_TEST_PY = '''\
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

"""Unit tests for __CLASS_NAME__."""

import pytest

from coded_tools.__MODULE_NAME__.__MODULE_NAME__ import __CLASS_NAME__


class Test__CLASS_NAME__:
    """Unit tests for __CLASS_NAME__.async_invoke."""

    @pytest.mark.asyncio
    async def test_returns_string(self) -> None:
        """async_invoke must return a string."""
        tool = __CLASS_NAME__()
        result = await tool.async_invoke({}, {})
        assert isinstance(result, str)
'''


class NewToolCommand:  # pylint: disable=too-few-public-methods
    """Scaffold a new CodedTool subclass and a matching unit test."""

    def __init__(self, name: str, root_dir: Optional[str] = None):
        """
        Args:
            name: Snake-case tool name (e.g. ``my_tool``).
            root_dir: Project root directory. Defaults to the current working directory.
        """
        self.name = name
        self.root_dir = root_dir or os.getcwd()

    @staticmethod
    def _to_class_name(name: str) -> str:
        """Convert snake_case or kebab-case name to PascalCase class name."""
        return "".join(word.capitalize() for word in re.split(r"[_\-]+", name))

    def run(self) -> int:
        """Scaffold the tool. Returns 0 on success, 1 on validation error."""
        if not re.match(r"^[a-z][a-z0-9_]*$", self.name):
            CliStatus.err(
                f"Tool name '{self.name}' must start with a lowercase letter "
                "and contain only lowercase letters, digits, and underscores."
            )
            return 1

        class_name = self._to_class_name(self.name)
        tool_rel = os.path.join("coded_tools", self.name, f"{self.name}.py")
        init_rel = os.path.join("coded_tools", self.name, "__init__.py")
        test_rel = os.path.join("tests", "neuro_san_studio", "coded_tools", f"test_{self.name}.py")

        self._write_file(tool_rel, _TOOL_PY.replace("__CLASS_NAME__", class_name))
        self._write_file(init_rel, "")
        self._write_file(
            test_rel,
            _TEST_PY.replace("__CLASS_NAME__", class_name).replace("__MODULE_NAME__", self.name),
        )

        _console.print()
        _console.print(f"[bold green]Tool '{class_name}' scaffolded.[/bold green]")
        _console.print(f"  Implement [cyan]{tool_rel}[/cyan].")
        _console.print(f'  Reference it in a network\'s \'tools\' list with: [bold]"class": "{class_name}"[/bold]')
        return 0

    def _write_file(self, rel_path: str, content: str) -> None:
        dest = os.path.join(self.root_dir, rel_path)
        if os.path.exists(dest):
            CliStatus.skip(f"{rel_path} (already exists)")
            return
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(content)
        CliStatus.ok(rel_path)
