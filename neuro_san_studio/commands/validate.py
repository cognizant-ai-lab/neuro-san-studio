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

The one thing studio adds is manifest discovery. ``HoconValidatorCli`` only
accepts ``/external_agent`` tool references that are listed in
``--external-agents``; it never reads the manifest. Studio fills that list with
the networks served by the project's manifest (``--manifest``, else
``AGENT_MANIFEST_FILE``, else ``<registry-dir or cwd>/registries/manifest.hocon``)
so a network that calls sibling networks validates with no flags. Several
manifests separated by ``os.pathsep`` are composed as the server composes them:
later manifests override earlier ones entry by entry. Explicit
``--external-agents`` are added on top. A manifest that cannot be read produces
a warning, not a failure.

Because the actual validation lives in the library, any future improvement there
(for example, gracefully handling non-agent-network files) is picked up here
automatically. A broad guard around the call keeps the command from printing a
raw traceback if the underlying validator raises.

Unlike ``check-config``, this command does NOT call any LLM - it performs purely
structural validation and therefore needs no API keys.
"""

import os
import sys
from typing import List
from typing import Optional

from neuro_san.client.hocon_validator_cli import HoconValidatorCli

from neuro_san_studio.commands.project_environment import ProjectEnvironment
from neuro_san_studio.discovery.manifest_read_error import ManifestReadError
from neuro_san_studio.discovery.served_network_lister import ServedNetworkLister

# Exit codes. neuro-san-studio's main() treats code 2 as a clean "help" exit,
# so (like check-config) we normalize to a binary contract: 0 = valid, 1 = problem.
EXIT_OK = 0
EXIT_ERROR = 1


class ValidateCommand:  # pylint: disable=too-few-public-methods
    """Validate the structure of an agent network HOCON file.

    Thin wrapper around neuro-san's ``HoconValidatorCli`` that first discovers the
    external agents served by the project's manifest. Returns exit code 0 when the
    file is valid and 1 when it is invalid or cannot be validated.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        hocon_path: str,
        *,
        verbose: bool = False,
        external_agents: Optional[str] = None,
        mcp_servers: Optional[str] = None,
        registry_dir: Optional[str] = None,
        manifest: Optional[str] = None,
    ):
        """Initialize the command.

        Args:
            hocon_path: Path to the agent network HOCON file to validate.
            verbose: When True, print the manifest discovery summary and, on success,
                an agent network summary.
            external_agents: Comma-separated external agent references accepted in
                addition to those discovered from the manifest (e.g. ``/agent1,/agent2``).
            mcp_servers: Comma-separated valid MCP server URLs.
            registry_dir: Base directory for resolving HOCON includes. Also anchors the
                default manifest location, ``<registry_dir>/registries/manifest.hocon``.
            manifest: Manifest HOCON whose served networks are accepted as external
                agents. An ``os.pathsep``-separated list is composed as the server
                composes it, later manifests overriding earlier ones. Defaults to
                ``AGENT_MANIFEST_FILE``, then ``<registry_dir or cwd>/registries/manifest.hocon``.
        """
        self.hocon_path = hocon_path
        self.verbose = verbose
        self.external_agents = external_agents
        self.mcp_servers = mcp_servers
        self.registry_dir = registry_dir
        self.manifest = manifest

    def _manifest_files(self) -> List[str]:
        """Resolve the manifest file(s) to discover external agents from.

        Precedence: ``--manifest``, then ``AGENT_MANIFEST_FILE``, then
        ``<registry_dir or cwd>/registries/manifest.hocon``. An ``os.pathsep``-separated
        list is accepted, as the neuro-san server accepts for ``AGENT_MANIFEST_FILE``.
        """
        base_dir: str = self.registry_dir or os.getcwd()
        manifest_spec: str = self.manifest or ProjectEnvironment(base_dir).resolve_manifest_file()
        return [path for path in manifest_spec.split(os.pathsep) if path]

    def _discover_external_agents(self) -> List[str]:
        """Collect ``/<network_name>`` references for every network the composed manifest(s) serve.

        Several manifests are composed as the server composes them: later manifests override
        earlier ones entry by entry. A manifest that cannot be read is reported on stderr and
        skipped, so validation proceeds with whatever else was provided.
        """
        manifest_files: List[str] = self._manifest_files()
        lister = ServedNetworkLister(manifest_files, base_dir=self.registry_dir)
        try:
            names: List[str] = lister.list_names()
        except ManifestReadError as error:
            print(f"Warning: {error}; no external agents will be discovered from the manifest.", file=sys.stderr)
            return []
        for message in lister.warnings:
            print(
                f"Warning: {message}; networks from this manifest will not be accepted as external agents.",
                file=sys.stderr,
            )
        if self.verbose:
            print(f"Using {len(names)} external agent name(s) from manifest(s): {', '.join(manifest_files)}")
        return names

    def _resolve_external_agents(self) -> Optional[str]:
        """Merge explicit ``--external-agents`` with the names discovered from the manifest.

        Explicit names come first, then discovered names, de-duplicated in order.

        Returns:
            A comma-separated list for ``HoconValidatorCli``, or ``None`` when there is nothing to pass.
        """
        explicit: List[str] = [name.strip() for name in (self.external_agents or "").split(",") if name.strip()]
        merged: List[str] = list(dict.fromkeys([*explicit, *self._discover_external_agents()]))
        return ",".join(merged) if merged else None

    def _build_argv(self, external_agents: Optional[str]) -> List[str]:
        """Marshal the command options into an argv list for HoconValidatorCli.

        Args:
            external_agents: Comma-separated external agent references to pass through, if any.
        """
        argv: List[str] = ["hocon_validator_cli", self.hocon_path]
        if self.verbose:
            argv.append("--verbose")
        if external_agents:
            argv.extend(["--external-agents", external_agents])
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
            sys.argv = self._build_argv(self._resolve_external_agents())
            exit_code: int = HoconValidatorCli().main()
            return EXIT_OK if exit_code == 0 else EXIT_ERROR
        except Exception as exception:  # pylint: disable=broad-except
            print(f"Error: Could not validate '{self.hocon_path}' - {exception}", file=sys.stderr)
            return EXIT_ERROR
        finally:
            sys.argv = saved_argv
