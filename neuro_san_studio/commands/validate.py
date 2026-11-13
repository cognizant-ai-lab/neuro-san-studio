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
``python -m neuro_san.client.hocon_validator_cli``). For the structure, studio
stays a thin wrapper: it marshals the command options into the arguments that
``HoconValidatorCli`` expects, runs it, and normalizes the exit code to studio's
0/1 convention (studio's ``main()`` reserves exit code 2 for clean help exits).

Studio adds two things. The first is manifest discovery. ``HoconValidatorCli`` only
accepts ``/external_agent`` tool references that are listed in
``--external-agents``; it never reads the manifest. Studio fills that list with
the networks served by the project's manifest (``--manifest``, else
``AGENT_MANIFEST_FILE``, else ``<registry-dir or cwd>/registries/manifest.hocon``)
so a network that calls sibling networks validates with no flags. Several
manifests separated by ``os.pathsep`` are composed as the server composes them:
later manifests override earlier ones entry by entry. Explicit
``--external-agents`` are added on top. A manifest that cannot be read produces
a warning, not a failure.

Studio also always passes ``--registry-dir`` to the library. Left unset, the
library derives it from the raw ``AGENT_MANIFEST_FILE`` string, which is a
nonexistent path when that string is an ``os.pathsep`` list (neuro-san issue
#1370). The fallback is the first manifest's project root, which is what the
library intends for a single manifest, else the current directory.

Because the actual validation lives in the library, any future improvement there
(for example, gracefully handling non-agent-network files) is picked up here
automatically. A broad guard around the call keeps the command from printing a
raw traceback if the underlying validator raises.

The second is the class check. When the structure is valid, studio loads every
coded tool and middleware class the network names, the way the server loads them
(see NetworkClassChecker). Loading a class imports its module, so the check only
runs from the project root, the folder that holds the first manifest's
``registries`` folder. That is where ``ns run`` starts the server and reads the
project's ``.env``. It also only runs for a file inside the folder of a manifest,
which is where the server loads networks from.

Unlike ``check-config``, this command does NOT call any LLM and therefore needs
no API keys.
"""

import os
import sys
from pathlib import Path
from typing import List
from typing import Optional

from neuro_san.client.hocon_validator_cli import HoconValidatorCli

from neuro_san_studio.commands.network_class_checker import NetworkClassChecker
from neuro_san_studio.commands.project_environment import ProjectEnvironment
from neuro_san_studio.discovery.manifest_project_root import ManifestProjectRoot
from neuro_san_studio.discovery.manifest_read_error import ManifestReadError
from neuro_san_studio.discovery.served_network_lister import ServedNetworkLister

# Exit codes. neuro-san-studio's main() treats code 2 as a clean "help" exit,
# so (like check-config) we normalize to a binary contract: 0 = valid, 1 = problem.
EXIT_OK = 0
EXIT_ERROR = 1

# The environment variables the class check sets the way `ns run` sets them for the server.
CLASS_CHECK_ENV_VARS: tuple[str, ...] = ("AGENT_TOOL_PATH", "PYTHONPATH")


class ValidateCommand:  # pylint: disable=too-few-public-methods
    """Validate an agent network HOCON file and load its coded tool and middleware classes.

    Thin wrapper around neuro-san's ``HoconValidatorCli`` that first discovers the
    external agents served by the project's manifest, then loads the network's coded
    tool and middleware classes the way the server would. Returns exit code 0 when the
    file is valid and no class fails to load, and 1 otherwise.
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
            verbose: When True, print the manifest discovery summary, an agent network
                summary on success, and the full error for each class that cannot be loaded.
            external_agents: Comma-separated external agent references accepted in
                addition to those discovered from the manifest (e.g. ``/agent1,/agent2``).
            mcp_servers: Comma-separated valid MCP server URLs.
            registry_dir: Base directory for resolving HOCON includes. Also anchors the
                default manifest location, ``<registry_dir>/registries/manifest.hocon``.
                Defaults to the first manifest's project root, else the current directory.
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

    def _registry_dir(self, manifest_files: List[str]) -> str:
        """Return the registry directory to hand to HoconValidatorCli.

        ``--registry-dir`` wins. Otherwise the project root of the first manifest, the directory
        containing its ``registries`` folder, which is what the library derives for a single
        ``AGENT_MANIFEST_FILE``. Otherwise the current directory, the library's own last resort.
        It is always passed explicitly because the library's derivation breaks on an
        ``os.pathsep`` list (neuro-san issue #1370).
        """
        if self.registry_dir:
            return self.registry_dir
        return self._manifest_project_root(manifest_files) or os.getcwd()

    @staticmethod
    def _manifest_project_root(manifest_files: List[str]) -> Optional[str]:
        """
        Return the project root of the first manifest, the folder that holds its registries folder.

        :param manifest_files: The manifest files, earliest first
        :return: The project root, or None when there is no manifest or it is not in a registries folder
        """
        if not manifest_files:
            return None
        return ManifestProjectRoot(manifest_files[0]).resolve()

    def _discover_external_agents(self, manifest_files: List[str]) -> List[str]:
        """Collect ``/<network_name>`` references for every network the composed manifest(s) serve.

        Several manifests are composed as the server composes them: later manifests override
        earlier ones entry by entry. A manifest that cannot be read is reported on stderr and
        skipped, so validation proceeds with whatever else was provided.

        Args:
            manifest_files: The manifest files to compose, earliest first.
        """
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

    def _resolve_external_agents(self, manifest_files: List[str]) -> Optional[str]:
        """Merge explicit ``--external-agents`` with the names discovered from the manifest(s).

        Explicit names come first, then discovered names, de-duplicated in order.

        Args:
            manifest_files: The manifest files to compose, earliest first.

        Returns:
            A comma-separated list for ``HoconValidatorCli``, or ``None`` when there is nothing to pass.
        """
        explicit: List[str] = [name.strip() for name in (self.external_agents or "").split(",") if name.strip()]
        merged: List[str] = list(dict.fromkeys([*explicit, *self._discover_external_agents(manifest_files)]))
        return ",".join(merged) if merged else None

    def _build_argv(self, external_agents: Optional[str], registry_dir: str) -> List[str]:
        """Marshal the command options into an argv list for HoconValidatorCli.

        Args:
            external_agents: Comma-separated external agent references to pass through, if any.
            registry_dir: Registry directory to pass through. Always present; see ``_registry_dir``.
        """
        argv: List[str] = ["hocon_validator_cli", self.hocon_path]
        if self.verbose:
            argv.append("--verbose")
        if external_agents:
            argv.extend(["--external-agents", external_agents])
        if self.mcp_servers:
            argv.extend(["--mcp-servers", self.mcp_servers])
        argv.extend(["--registry-dir", registry_dir])
        return argv

    def run(self) -> int:
        """
        Validate the structure with HoconValidatorCli, then load the classes the network names.

        :return: EXIT_OK when the file is valid and no class fails to load, else EXIT_ERROR
        """
        # HoconValidatorCli.main() reads sys.argv, so temporarily install our argv
        # and restore it afterwards regardless of outcome.
        saved_argv: List[str] = sys.argv
        try:
            manifest_files: List[str] = self._manifest_files()
            external_agents: Optional[str] = self._resolve_external_agents(manifest_files)
            registry_dir: str = self._registry_dir(manifest_files)
            sys.argv = self._build_argv(external_agents, registry_dir)
            exit_code: int = HoconValidatorCli().main()
            if exit_code != 0:
                return EXIT_ERROR
            return self._check_classes(manifest_files)
        except Exception as exception:  # pylint: disable=broad-except
            print(f"Error: Could not validate '{self.hocon_path}' - {exception}", file=sys.stderr)
            return EXIT_ERROR
        finally:
            sys.argv = saved_argv

    def _check_classes(self, manifest_files: List[str]) -> int:
        """
        Load the coded tool and middleware classes the network names the way the server would, and print
        the result.

        `ns run` starts the server from the project root, the folder that holds the manifest's registries
        folder, and reads the .env there. So the check only runs from the project root too. It runs with
        the process set up as `ns run` sets up the server, and sys.path and the environment are put back
        afterwards.

        :param manifest_files: The manifest files, earliest first
        :return: EXIT_ERROR when a class cannot be loaded, else EXIT_OK
        """
        project_root: Optional[str] = self._manifest_project_root(manifest_files)
        if project_root is None:
            first_manifest: str = manifest_files[0] if manifest_files else ""
            print(
                f"Class check skipped: the manifest '{first_manifest}' is not in a registries folder, so there"
                " is no project root to load the classes from."
            )
            return EXIT_OK
        current_dir: Path = Path.cwd().resolve()
        if Path(project_root).resolve() != current_dir:
            print(
                f"Class check skipped: the current directory is not the project root '{project_root}'."
                " Run ns validate from the project root, where ns run starts the server, so the check uses"
                " the project's .env."
            )
            return EXIT_OK
        saved_path: List[str] = list(sys.path)
        saved_environ: dict[str, str | None] = {}
        for name in CLASS_CHECK_ENV_VARS:
            saved_environ[name] = os.environ.get(name)
        checker: NetworkClassChecker = NetworkClassChecker(self.hocon_path, manifest_files, verbose=self.verbose)
        try:
            self._prepare_class_environment(current_dir)
            errors: list[str] | None = checker.check()
        finally:
            sys.path[:] = saved_path
            self._restore_environ(saved_environ)
        return self._report_class_check(errors, checker.get_checked_count(), manifest_files)

    @staticmethod
    def _prepare_class_environment(root: Path) -> None:
        """
        Set the process up the way `ns run` sets up the server, so classes load from the project.

        The project root goes into PYTHONPATH, which neuro-san uses to turn AGENT_TOOL_PATH into a module
        path. AGENT_TOOL_PATH defaults to the project's coded_tools folder, and AGENT_TOOL_PATH_ONLY stays
        as the user set it. The server starts in the project root, so its sys.path begins with the root and
        then each PYTHONPATH entry, ahead of the copies of coded_tools and middleware installed with the
        package. This process read .env after Python set up sys.path, so the same entries go first here.

        :param root: The project root, as an absolute path
        """
        environment: ProjectEnvironment = ProjectEnvironment(str(root))
        environment.set_pythonpath()
        if not os.environ.get("AGENT_TOOL_PATH"):
            os.environ["AGENT_TOOL_PATH"] = environment.resolve_tool_path()
        import_paths: list[str] = [str(root)]
        for entry in os.environ.get("PYTHONPATH", "").split(os.pathsep):
            # Python makes each PYTHONPATH entry absolute at startup, from the folder it starts in.
            if entry:
                import_paths.append(os.path.abspath(entry))
        sys.path[0:0] = import_paths

    @staticmethod
    def _restore_environ(saved_environ: dict[str, str | None]) -> None:
        """
        Put environment variables back to the values they had before the class check.

        :param saved_environ: Each variable's value before the check, or None when it was not set
        """
        for name, value in saved_environ.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _report_class_check(self, errors: list[str] | None, checked_count: int, manifest_files: List[str]) -> int:
        """
        Print the result of the class check, and turn it into an exit code.

        :param errors: One message per problem, or None when the file was not checked
        :param checked_count: How many class references were checked
        :param manifest_files: The manifest files whose folders the file was looked for in
        :return: EXIT_ERROR when a class cannot be loaded, else EXIT_OK
        """
        if errors is None:
            print(
                f"Class check skipped: '{self.hocon_path}' is not inside the folder of any manifest"
                f" ({', '.join(manifest_files)})."
            )
            return EXIT_OK
        if errors:
            print(f"Class check failed with {len(errors)} error(s):\n")
            for number, error in enumerate(errors, 1):
                # A full error from --verbose has several lines, which go under the number.
                print(f"  {number}. " + error.replace("\n", "\n     "))
            return EXIT_ERROR
        print(f"Class check passed: {checked_count} class reference(s) loaded.")
        return EXIT_OK
