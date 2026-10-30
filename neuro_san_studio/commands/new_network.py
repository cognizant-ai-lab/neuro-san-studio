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

"""Implementation of the `ns new network` command."""

import keyword
import os
import re
from typing import Optional

from rich.console import Console

from neuro_san_studio.utils.cli_status import CliStatus

_console = Console()

# Placeholders replaced at generation time — avoids f-string / .format() conflicts
# with HOCON substitution syntax (${...}) and triple-quote literals.
_NETWORK_HOCON = '''\
{
    "metadata": {
        "description": "Agent network for __CLASS_NAME__."
        "tags": []
        "sample_queries": [
            "Hello, what can you do?",
        ]
    },

    include "registries/expertise_scoping_instructions.hocon",

    include "config/llm_config.hocon",
    "max_steps": 40000,
    "max_execution_seconds": 6000,
    "tools": [
        {
            "name": "__CLASS_NAME__",

            "function": {
                "description": """
I can help with __DESCRIPTION__ tasks.
"""
            },

            "instructions": ${expertise_scoping_instructions} """
You are __CLASS_NAME__. Describe your role and capabilities here.
""",
            "tools": []
        }
    ]
}
'''

_FIXTURE_HOCON = """\
{
    "agent": "__NETWORK_NAME__",

    "timeout_in_seconds": 90,

    "connections": ["direct"],

    "interactions": [
        {
            "text": "Hello, what can you do?",

            "response": {
                "structure": {
                    "answer": {
                        "keywords": ""
                    }
                }
            }
        }
    ]
}
"""


class NewNetworkCommand:  # pylint: disable=too-few-public-methods
    """Scaffold a new agent network HOCON file, register it in the manifest, and create a sample fixture."""

    def __init__(self, name: str, root_dir: Optional[str] = None):
        """
        Args:
            name: Snake-case network name (e.g. ``my_network``).
            root_dir: Project root directory. Defaults to the current working directory.
        """
        self.name = name
        self.root_dir = root_dir or os.getcwd()

    @staticmethod
    def _to_class_name(name: str) -> str:
        """Convert snake_case or kebab-case name to PascalCase class name."""
        return "".join(word.capitalize() for word in re.split(r"[_\-]+", name))

    def run(self) -> int:
        """Scaffold the network. Returns 0 on success, 1 on validation error."""
        if not re.match(r"^[a-z][a-z0-9_]*$", self.name) or keyword.iskeyword(self.name):
            CliStatus.err(
                f"Network name '{self.name}' must start with a lowercase letter, "
                "contain only lowercase letters, digits, and underscores, "
                "and must not be a Python keyword."
            )
            return 1

        class_name = self._to_class_name(self.name)
        hocon_rel = os.path.join("registries", f"{self.name}.hocon")
        fixture_rel = os.path.join("tests", "fixtures", self.name, "sample.hocon")

        self._write_network_hocon(hocon_rel, class_name)
        self._update_manifest()
        self._write_fixture(fixture_rel)

        _console.print()
        _console.print(f"[bold green]Network '{self.name}' scaffolded.[/bold green]")
        _console.print(f"  Edit [cyan]{hocon_rel}[/cyan] to build your agent network.")
        _console.print(f"  Then run: [bold]ns run[/bold]  and chat: [bold]ns chat {self.name}[/bold]")
        return 0

    def _write_network_hocon(self, rel_path: str, class_name: str) -> None:
        dest = os.path.join(self.root_dir, rel_path)
        if os.path.exists(dest):
            CliStatus.skip(f"{rel_path} (already exists)")
            return
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        description = self.name.replace("_", " ")
        content = _NETWORK_HOCON.replace("__CLASS_NAME__", class_name).replace("__DESCRIPTION__", description)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(content)
        CliStatus.ok(rel_path)

    def _update_manifest(self) -> None:
        manifest_rel = os.path.join("registries", "manifest.hocon")
        manifest_path = os.path.join(self.root_dir, manifest_rel)
        if not os.path.exists(manifest_path):
            CliStatus.warn(f"{manifest_rel} not found — skipping manifest update.")
            return
        with open(manifest_path, "r", encoding="utf-8") as fh:
            text = fh.read()
        if f'"{self.name}.hocon"' in text:
            CliStatus.skip(f"{manifest_rel} (entry already present)")
            return
        closing = text.rfind("}")
        if closing == -1:
            CliStatus.warn(f"Could not locate closing brace in {manifest_rel} — skipping manifest update.")
            return
        entry = f'    "{self.name}.hocon": true\n'
        updated = text[:closing] + entry + text[closing:]
        with open(manifest_path, "w", encoding="utf-8") as fh:
            fh.write(updated)
        CliStatus.ok(f"{manifest_rel} (added {self.name}.hocon)")

    def _write_fixture(self, rel_path: str) -> None:
        dest = os.path.join(self.root_dir, rel_path)
        if os.path.exists(dest):
            CliStatus.skip(f"{rel_path} (already exists)")
            return
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        content = _FIXTURE_HOCON.replace("__NETWORK_NAME__", self.name)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(content)
        CliStatus.ok(rel_path)
