# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from leaf_common.resolution.resolver_util import ResolverUtil
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.activations.abstract_class_activation import AbstractClassActivation
from neuro_san.internals.graph.activations.class_activation import ClassActivation
from neuro_san.internals.graph.persistence.agent_filetree_mapper import AgentFileTreeMapper
from neuro_san.internals.graph.persistence.agent_network_restorer import AgentNetworkRestorer
from neuro_san.internals.graph.registry.activation_factory import ActivationFactory
from neuro_san.internals.graph.registry.agent_network import AgentNetwork

# The server's coded tool error starts with the class, the module and the AGENT_TOOL_PATH it searched,
# one per line, then a long list of hints. Only those first lines go into the short report.
SUMMARY_LINE_COUNT: int = 3


# This check repeats rules that neuro-san owns, so it should move into neuro-san's validator later.
# ValidateCommand would then call neuro-san's check, and this class could be deleted.
class NetworkClassChecker:
    """
    Loads the coded tool and middleware classes an agent network file names, the way the server loads
    them, and reports the ones that fail.

    The server names a network by its path under the manifest's folder and looks its coded tools up from
    AGENT_TOOL_PATH plus that name, so the check restores the file the same way. Coded tools go through
    neuro-san's own lookup, which honors AGENT_TOOL_PATH_ONLY, and middleware through the call the server's
    middleware factory makes. Classes are loaded but not created. Toolbox tools, checkpointers and LLM
    classes are not checked.

    Loading a class imports its module, so the process must be set up as it is for the server: the
    project root first on sys.path and in PYTHONPATH, and AGENT_TOOL_PATH set.
    """

    def __init__(self, hocon_path: str, manifest_files: list[str], verbose: bool = False) -> None:
        """
        Set up a check of one network file.

        :param hocon_path: The agent network file to check
        :param manifest_files: The manifest files whose folders the server loads networks from, earliest first
        :param verbose: True to report the full error for each class that cannot be loaded
        """
        self.hocon_path: str = hocon_path
        self.manifest_files: list[str] = manifest_files
        self.verbose: bool = verbose
        self.checked_count: int = 0

    def get_checked_count(self) -> int:
        """
        Return how many class references the last check tried to load.

        :return: The number of coded tool and middleware class references checked
        """
        return self.checked_count

    def find_network_location(self) -> tuple[Path, str] | None:
        """
        Find the manifest folder that holds the file, and the file's path under it.

        The server only loads networks from a manifest's folder, and that path is what gives the network
        its name. The first manifest whose folder holds the file wins.

        :return: The manifest folder, resolved as the server resolves it, and the file's path under it in
                POSIX form, or None when the file is not inside the folder of any manifest
        """
        for manifest_file in self.manifest_files:
            # The server resolves the folder of the manifest path, not the manifest file itself.
            manifest_dir: Path = Path(manifest_file).parent.resolve()
            relative_path: str | None = self._path_under_manifest_folder(manifest_dir)
            if relative_path is not None:
                return manifest_dir, relative_path
        return None

    def _path_under_manifest_folder(self, manifest_dir: Path) -> str | None:
        """
        Return the network file's path under a manifest's folder.

        The server resolves only the manifest's folder and keeps the path below it as written, so a
        symlinked folder below it keeps its name. The file's folders are therefore resolved one at a time
        from the top, and the first one that lands in the manifest's folder gives the file's place there,
        with the rest of the path kept as given. A file that is a symlink from elsewhere into the folder is
        placed by resolving the file itself.

        :param manifest_dir: The manifest's folder, resolved
        :return: The file's path under the folder in POSIX form, or None when the file is not in the folder
        """
        network_file: Path = Path(os.path.abspath(self.hocon_path))
        # Top first: a deeper folder can be a symlink inside the manifest's folder, which the server never
        # resolves. parents runs from the file's folder up to the root, so it is reversed.
        for folder in reversed(network_file.parents):
            resolved_folder: Path = folder.resolve()
            # is_relative_to answers False for a path on another Windows drive instead of raising.
            if resolved_folder.is_relative_to(manifest_dir):
                place: Path = resolved_folder.relative_to(manifest_dir)
                return (place / network_file.relative_to(folder)).as_posix()
        resolved_file: Path = network_file.resolve()
        if resolved_file.is_relative_to(manifest_dir):
            return resolved_file.relative_to(manifest_dir).as_posix()
        return None

    def check(self) -> list[str] | None:
        """
        Load the coded tool and middleware classes the network names, and report the ones that fail.

        One bad reference does not stop the check, so the report lists every failure.

        :return: One message per problem, an empty list when every class loads, or None when the file is not
                inside the folder of any manifest, so it has no network name
        """
        self.checked_count = 0
        location: tuple[Path, str] | None = self.find_network_location()
        if location is None:
            return None
        manifest_dir, file_reference = location
        restorer: AgentNetworkRestorer = AgentNetworkRestorer(
            registry_dir=str(manifest_dir), agent_mapper=AgentFileTreeMapper()
        )
        network: AgentNetwork = restorer.restore(file_reference=file_reference)

        errors: list[str] = []
        # The server logs a long list of hints for each failed lookup, and the report has its own message.
        # logging has no getter for the level logging.disable() sets, so it is read from the manager.
        previous_disable: int = logging.root.manager.disable
        logging.disable(max(previous_disable, logging.ERROR))
        try:
            factory: ActivationFactory | None = self._create_factory(network, errors)
            for spec in network.get_config().get("tools") or []:
                self._check_spec(network, factory, spec, errors)
        finally:
            logging.disable(previous_disable)
        return errors

    @staticmethod
    def _create_factory(network: AgentNetwork, errors: list[str]) -> ActivationFactory | None:
        """
        Create the factory the server would use for the network, which knows where coded tools live.

        :param network: The network the coded tools belong to
        :param errors: The report, which gets a message when AGENT_TOOL_PATH cannot be used
        :return: The factory, or None when AGENT_TOOL_PATH cannot be mapped to a module path
        """
        try:
            return ActivationFactory(network)
        except ValueError as error:
            errors.append(f"Coded tools cannot be looked up: {error}")
            return None

    def _check_spec(
        self, network: AgentNetwork, factory: ActivationFactory | None, spec: Any, errors: list[str]
    ) -> None:
        """
        Check the classes one agent names, telling agent kinds apart the way the server does.

        A toolbox agent names no class of its own. An agent with both a function and a class is a coded
        tool. Any other agent is run by an LLM, and only those agents load middleware.

        :param network: The network the agent belongs to
        :param factory: The factory for looking up coded tools, or None when it could not be created
        :param spec: The agent's spec from the network's tools list
        :param errors: The report, which gets a message for each class that cannot be loaded
        """
        if not isinstance(spec, dict) or spec.get("toolbox") is not None:
            return
        agent_name: str = network.get_name_from_spec(spec)
        if spec.get("function") is not None and spec.get("class") is not None:
            if factory is not None:
                self._check_coded_tool(factory, spec, agent_name, errors)
            return
        self._check_middleware(spec, agent_name, errors)

    def _check_coded_tool(
        self, factory: ActivationFactory, spec: dict[str, Any], agent_name: str, errors: list[str]
    ) -> None:
        """
        Load a coded tool's class with neuro-san's own lookup, and check that it is a CodedTool.

        :param factory: The factory that knows where the network's coded tools live
        :param spec: The coded tool's spec
        :param agent_name: The name of the coded tool, for the report
        :param errors: The report, which gets a message when the class cannot be loaded
        """
        class_reference: Any = spec.get("class")
        self.checked_count += 1
        if not isinstance(class_reference, str) or not class_reference:
            errors.append(f"Agent '{agent_name}': class must be a non-empty string, not {class_reference!r}.")
            return
        # Split as the server does: the class is the last part and the module is everything before it.
        module_name, _, class_name = class_reference.rpartition(".")
        module_name = module_name.rstrip(".")
        # The lookup never reads "allow", but building an activation for a spec that allows reservations
        # needs a running server, so the lookup gets a copy without it.
        lookup_spec: dict[str, Any] = dict(spec)
        lookup_spec.pop("allow", None)
        try:
            found: Any = ClassActivation(None, factory, {}, lookup_spec, {}).resolve_class(class_name, module_name)
        except (ValueError, TypeError, AttributeError) as error:
            errors.append(f"Agent '{agent_name}': {self._describe(error, self._strict_note())}")
            return
        # The server only runs an instance of a CodedTool. The class is checked without creating an
        # instance, so a constructor that needs arguments is not caught here.
        if not isinstance(found, type) or not issubclass(found, CodedTool):
            errors.append(f"Agent '{agent_name}': class '{class_reference}' is not a CodedTool.")

    def _check_middleware(self, spec: dict[str, Any], agent_name: str, errors: list[str]) -> None:
        """
        Check each middleware entry an LLM agent has.

        :param spec: The agent's spec
        :param agent_name: The name of the agent, for the report
        :param errors: The report, which gets a message for each entry the server cannot use
        """
        entries: Any = spec.get("middleware")
        # The server builds no middleware from a missing or empty value, and fails on any other value that
        # is not a list, including a number or a boolean.
        if entries is None or (isinstance(entries, (dict, str)) and not entries):
            return
        if not isinstance(entries, list):
            errors.append(f"Agent '{agent_name}': middleware must be a list of dictionaries.")
            return
        for index, entry in enumerate(entries):
            self._check_middleware_entry(entry, index, agent_name, errors)

    def _check_middleware_entry(self, entry: Any, index: int, agent_name: str, errors: list[str]) -> None:
        """
        Load the class one middleware entry names with the call the server's middleware factory makes.

        :param entry: The middleware entry
        :param index: The entry's place in the agent's middleware list
        :param agent_name: The name of the agent, for the report
        :param errors: The report, which gets a message when the server cannot use the entry
        """
        if not isinstance(entry, dict):
            errors.append(f"Agent '{agent_name}': middleware at index {index} must be a dictionary.")
            return
        class_name: Any = entry.get("class")
        # The server skips an entry that names no class, with a warning.
        if class_name is None:
            return
        self.checked_count += 1
        if not isinstance(class_name, str) or not class_name:
            errors.append(
                f"Agent '{agent_name}': middleware at index {index} must name its class as a non-empty string,"
                f" not {class_name!r}."
            )
            return
        try:
            ResolverUtil.create_class(class_name, f"middleware at index {index}", AgentMiddleware)
        except (ValueError, TypeError, AttributeError) as error:
            errors.append(f"Agent '{agent_name}': {self._describe(error)}")

    def _describe(self, error: Exception, note: str = "") -> str:
        """
        Describe an error from a class lookup for the report.

        :param error: The error the lookup raised
        :param note: A note for the short form. The full error explains itself.
        :return: The full error when verbose, else its first lines on one line, followed by the note
        """
        if self.verbose:
            return str(error).strip()
        lines: list[str] = []
        for line in str(error).splitlines():
            if line.strip():
                lines.append(line.strip())
            if len(lines) == SUMMARY_LINE_COUNT:
                break
        return " ".join(lines) + note

    @staticmethod
    def _strict_note() -> str:
        """
        Explain a failed coded tool lookup that AGENT_TOOL_PATH_ONLY may have caused, and how to fix it.

        :return: A note for the report when AGENT_TOOL_PATH_ONLY is on, else an empty string
        """
        if AbstractClassActivation.is_agent_tool_path_only():
            return (
                " (AGENT_TOOL_PATH_ONLY is on, so the class is only looked up under AGENT_TOOL_PATH: name its"
                " module relative to AGENT_TOOL_PATH, not by its full package path.)"
            )
        return ""
