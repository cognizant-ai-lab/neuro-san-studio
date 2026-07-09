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

"""Implementation of the `neuro-san-studio chat` command.

Runs an interactive or one-shot chat with an agent network by delegating to
neuro-san's ``AgentCli`` (the tool also exposed as
``python -m neuro_san.client.agent_cli``). Studio stays a thin wrapper: it
marshals the command options into the arguments that ``AgentCli`` expects,
runs it, and normalizes the exit code to studio's 0/1 convention.

Unlike ``run``, this command does NOT start any server processes. By default it
uses a direct (in-process library) connection, so no server needs to be running.
It can also connect to an already-running neuro-san server via HTTP or HTTPS.
"""

import os
import sys
from typing import List
from typing import Optional

from neuro_san.client.agent_cli import AgentCli

from neuro_san_studio.commands.project_environment import ProjectEnvironment

EXIT_OK = 0
EXIT_ERROR = 1


class ChatCommand:  # pylint: disable=too-few-public-methods
    """Chat with an agent network via the CLI.

    Thin wrapper around neuro-san's ``AgentCli``. Returns exit code 0
    on normal completion and 1 on error.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        agent: Optional[str],
        *,
        connection: str = "direct",
        host: Optional[str] = None,
        port: Optional[int] = None,
        one_shot: bool = False,
        list_agents: bool = False,
        extra_args: Optional[List[str]] = None,
    ):
        """Initialize the command.

        Args:
            agent: Name of the agent network to chat with (None when listing).
            connection: Connection type (direct, http, or https).
            host: Hostname of the neuro-san server (for http/https).
            port: Port of the neuro-san server (for http/https).
            one_shot: When True, send one prompt then exit.
            list_agents: When True, list available agents and exit.
            extra_args: Additional arguments forwarded to AgentCli.
        """
        self.agent = agent
        self.connection = connection
        self.host = host
        self.port = port
        self.one_shot = one_shot
        self.list_agents = list_agents
        self.extra_args = extra_args or []

    def _build_argv(self) -> List[str]:
        """Marshal the command options into an argv list for AgentCli."""
        argv: List[str] = ["agent_cli"]

        if self.list_agents:
            argv.append("--list")
        elif self.agent is not None:
            argv.extend(["--agent", self.agent])

        argv.extend(["--connection", self.connection])

        if self.host is not None:
            argv.extend(["--host", self.host])
        if self.port is not None:
            argv.extend(["--port", str(self.port)])
        if self.one_shot:
            argv.append("--one_shot")

        argv.extend(self.extra_args)
        return argv

    def run(self) -> int:
        """Delegate to AgentCli and return a normalized exit code (0 ok, 1 problem)."""
        # Point neuro-san at this project's agents/coded tools before chatting. A direct
        # session runs in-process, so without this it falls back to neuro-san's bundled
        # library manifest and can't find the project's own networks.
        ProjectEnvironment(os.getcwd()).apply()

        saved_argv: List[str] = sys.argv
        try:
            sys.argv = self._build_argv()
            AgentCli().main()
            return EXIT_OK
        except KeyboardInterrupt:
            print()
            return EXIT_OK
        except Exception as exception:  # pylint: disable=broad-except
            print(f"Error: {exception}", file=sys.stderr)
            return EXIT_ERROR
        finally:
            sys.argv = saved_argv
