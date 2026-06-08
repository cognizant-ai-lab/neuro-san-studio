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

"""Implementation of the `neuro-san-studio validate` command.

Validates the structure of an agent network HOCON file by delegating to the
neuro-san library's ``HoconValidatorCli`` (the tool also exposed as
``python -m neuro_san.client.hocon_validator_cli``). Studio stays a thin
wrapper: it marshals the command options into the arguments that
``HoconValidatorCli`` expects, runs it, and normalizes the exit code to studio's
0/1 convention (studio's ``main()`` reserves exit code 2 for clean help exits).

Because the actual validation lives in the library, any future improvement there
(for example, gracefully handling non-agent-network files) is picked up here
automatically. A broad guard around the call keeps the command from printing a
raw traceback if the underlying validator raises.

Unlike ``check-config``, this command does NOT call any LLM - it performs purely
structural validation and therefore needs no API keys.
"""

import sys
from typing import List
from typing import Optional

from neuro_san.client.hocon_validator_cli import HoconValidatorCli

# Exit codes. neuro-san-studio's main() treats code 2 as a clean "help" exit,
# so (like check-config) we normalize to a binary contract: 0 = valid, 1 = problem.
EXIT_OK = 0
EXIT_ERROR = 1


class ValidateCommand:  # pylint: disable=too-few-public-methods
    """Validate the structure of an agent network HOCON file.

    Thin wrapper around neuro-san's ``HoconValidatorCli``. Returns exit code 0
    when the file is valid and 1 when it is invalid or cannot be validated.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        hocon_path: str,
        *,
        verbose: bool = False,
        external_agents: Optional[str] = None,
        mcp_servers: Optional[str] = None,
        registry_dir: Optional[str] = None,
    ):
        """Initialize the command.

        Args:
            hocon_path: Path to the agent network HOCON file to validate.
            verbose: When True, print an agent network summary on success.
            external_agents: Comma-separated valid external agent references
                (e.g. ``/agent1,/agent2``).
            mcp_servers: Comma-separated valid MCP server URLs.
            registry_dir: Base directory for resolving HOCON includes.
        """
        self.hocon_path = hocon_path
        self.verbose = verbose
        self.external_agents = external_agents
        self.mcp_servers = mcp_servers
        self.registry_dir = registry_dir

    def _build_argv(self) -> List[str]:
        """Marshal the command options into an argv list for HoconValidatorCli."""
        argv: List[str] = ["hocon_validator_cli", self.hocon_path]
        if self.verbose:
            argv.append("--verbose")
        if self.external_agents:
            argv.extend(["--external-agents", self.external_agents])
        if self.mcp_servers:
            argv.extend(["--mcp-servers", self.mcp_servers])
        if self.registry_dir:
            argv.extend(["--registry-dir", self.registry_dir])
        return argv

    def run(self) -> int:
        """Delegate to HoconValidatorCli and return a normalized exit code (0 ok, 1 problem)."""
        # HoconValidatorCli.main() reads sys.argv, so temporarily install our argv
        # and restore it afterwards regardless of outcome.
        saved_argv: List[str] = sys.argv
        try:
            sys.argv = self._build_argv()
            exit_code: int = HoconValidatorCli().main()
            return EXIT_OK if exit_code == 0 else EXIT_ERROR
        except Exception as exception:  # pylint: disable=broad-except
            print(f"Error: Could not validate '{self.hocon_path}' - {exception}", file=sys.stderr)
            return EXIT_ERROR
        finally:
            sys.argv = saved_argv
