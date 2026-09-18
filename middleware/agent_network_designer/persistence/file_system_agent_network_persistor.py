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

import os
from logging import getLogger
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiofiles
from leaf_common.serialization.util.text_file_reader import TextFileReader
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

from coded_tools.agent_network_editor.and_logger import AndLogger
from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler
from middleware.agent_network_designer.persistence.agent_network_persistor import AgentNetworkPersistor
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler

DEFAULT_SUBDIRECTORY: str = "generated"
DEFAULT_REGISTRIES_DIR: str = "registries"
MANIFEST_FILENAME: str = "manifest.hocon"


class FileSystemAgentNetworkPersistor(AgentNetworkPersistor):
    """
    AgentNetworkPersistor implementation for saving agent networks to the file system
    as a hocon file. Also modifies the local manifest file.
    """

    def __init__(self, demo_mode: bool, subdirectory: str = DEFAULT_SUBDIRECTORY) -> None:
        """
        Creates a new persistor of the specified type.

        :param demo_mode: Whether to include demo mode instructions for agents
        :param subdirectory: The subdirectory under output_path where networks are saved.
                Leading and trailing slashes are stripped so callers can pass either
                "generated" or "generated/" interchangeably.
        """
        self.logger: AndLogger = AndLogger(getLogger(self.__class__.__name__))
        self.demo_mode: bool = demo_mode
        self.subdirectory: str = subdirectory.strip("/")

        # Derive output_path from the first file listed in AGENT_MANIFEST_FILE,
        # falling back to the repo defaults when no usable entry exists.
        first_manifest: str = self.get_first_manifest_path()
        if first_manifest:
            self.output_path: str = os.path.dirname(first_manifest)
            self.main_manifest_path: str = first_manifest
        else:
            self.output_path = DEFAULT_REGISTRIES_DIR
            self.main_manifest_path = os.path.join(DEFAULT_REGISTRIES_DIR, MANIFEST_FILENAME)

    @staticmethod
    def get_first_manifest_path() -> str:
        """
        Returns the first non-empty entry of the AGENT_MANIFEST_FILE environment variable.

        The env var is an os.pathsep-separated list (like PATH), matching how neuro-san's
        RegistryManifestRestorer parses the same variable. Empty entries — from a stray
        leading or doubled separator, or an empty env var (which splits to [""]) — are
        skipped because the neuro-san server likewise skips them and serves the remaining
        manifests. Entries are deliberately NOT stripped of whitespace: the server does not
        strip either, so padded values fail consistently on both sides instead of silently
        diverging. AgentNetworkDefinitionMiddleware shares this helper so loads and saves
        agree on file location.

        :return: The first non-empty manifest path, or "" when no such entry exists.
        """
        agent_manifest_file: str = os.environ.get("AGENT_MANIFEST_FILE", "")
        parts: list[str] = agent_manifest_file.split(os.pathsep)
        for part in parts:
            if part:
                return part
        return ""

    def get_assembler(self) -> AgentNetworkAssembler:
        """
        :return: An assembler instance associated with this persistor
        """
        return HoconAgentNetworkAssembler(self.demo_mode)

    def get_network_file_path(self, file_reference: str) -> Path:
        """
        Resolve the path of the HOCON file a network is persisted under.

        Shared by async_persist and async_restore_metadata so the fallback read in
        AgentNetworkPersistenceMiddleware targets exactly the file the write overwrites.
        Path() handles OS-specific separators: even though the relative name contains '/',
        pathlib recognizes it as an alt-separator on Windows and normalizes it to a backslash
        when the path is handed to the file system APIs.

        The network name is client input. A nested name (team/my_net) is fine; a name that climbs
        out of <output_path>/<subdirectory> ("../x") is refused, since the fallback read would hand
        that file's metadata upstream and the write would land outside the registries directory.

        :param file_reference: The raw network name, without subdirectory prefix or extension
        :return: <output_path>/<subdirectory>/<file_reference>.hocon
        :raises ValueError: When the name resolves to a path outside <output_path>/<subdirectory>
        """
        root: Path = Path(self.output_path) / self.subdirectory
        file_path: Path = Path(self.output_path) / f"{self.subdirectory}/{file_reference}.hocon"
        # resolve() folds ".." and follows symlinks on both sides, so a root that is itself a symlink
        # (macOS temp dirs, for one) compares consistently; a first save, whose file does not exist
        # yet, resolves fine because strict is False.
        if not file_path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Agent network name {file_reference!r} resolves outside {root}")
        return file_path

    async def async_restore_metadata(self, file_reference: str) -> dict[str, Any] | None:
        """
        Read the metadata block of the network currently persisted under file_reference.

        Parses the whole file with the restorer the designer also loads networks with, so the
        block comes back as plain dicts and lists. Generated files include registries/aaosa.hocon
        and config/llm_config.hocon relative to the process CWD, so the read only succeeds from
        the project root, where the server that serves those files runs anyway.

        Read and parse failures are not fatal to the save: a network that cannot be read is
        logged and treated as having no metadata, which is exactly the pre-#1398 behaviour, so a
        corrupt file can still be repaired by saving over it.

        :param file_reference: The raw network name, without subdirectory prefix or extension
        :return: The metadata block, or None when the file does not exist, cannot be read or
                parsed, or has no dict-valued "metadata"
        :raises ValueError: When the name resolves outside the generated directory (see
                get_network_file_path); a bad name is the client's error, not a file to skip
        """
        file_path: Path = self.get_network_file_path(file_reference)
        # must_exist=False: a first save has nothing to carry forward and must not be an error.
        restorer: AbstractAsyncConfigRestorer = AbstractAsyncConfigRestorer(
            file_purpose="existing agent network", must_exist=False
        )
        try:
            # An empty file parses as an empty config and would pass as "no metadata" silently; it
            # is never something the persistor wrote, so leave a trace before saving over it.
            if file_path.is_file() and file_path.stat().st_size == 0:
                self.logger.warning("Existing agent network %s is empty; saving without its metadata.", file_path)
                return None
            config: Any = await restorer.async_restore(file_reference=str(file_path))
        except (OSError, ValueError) as error:
            # ValueError is how the restorer reports HOCON/JSON parse and substitution failures. A
            # generated file read from the wrong CWD lands here too: pyhocon only warns about the
            # include it cannot find, then the ${aaosa_call} substitution fails. OSError covers
            # unreadable paths, a stat that fails included.
            self.logger.warning(
                "Could not read existing agent network %s; saving without its metadata: %s", file_path, error
            )
            return None
        return self._metadata_from_config(config, file_path)

    def _metadata_from_config(self, config: Any, file_path: Path) -> dict[str, Any] | None:
        """
        Pick the metadata block out of a parsed network config, warning about the shapes that
        cannot hold one.

        :param config: What the restorer returned for the existing network file
        :param file_path: The file it came from, named in the warnings
        :return: The block, or None when the config is empty, not an object, has no
                "metadata" or a non-dict one (an explicit null included)
        """
        if config is None:
            return None
        if not isinstance(config, dict):
            self.logger.warning(
                "Existing agent network %s is not an object (%s); saving without its metadata.",
                file_path,
                type(config).__name__,
            )
            return None
        if "metadata" not in config:
            return None
        # An explicit null is a non-dict too: neither assembler writes one, so it gets the same trace.
        metadata: Any = config["metadata"]
        if not isinstance(metadata, dict):
            self.logger.warning(
                "Ignoring non-dict 'metadata' (%s) in existing agent network %s.", type(metadata).__name__, file_path
            )
            return None
        return metadata

    async def async_persist(self, obj: str, file_reference: str = None) -> str:
        """
        Persists the object passed in.

        :param obj: an object to persist.
                In this case this is the agent network hocon string.
        :param file_reference: The file reference to use when persisting.
                Default is None, implying the file reference is up to the
                implementation.
        :return: The path the network was written to, or None when the manifest already
                listed the network (the file is still rewritten; see #1425)
        """

        the_agent_network_hocon_str: str = obj
        # Prepend subdirectory to form the full relative network path.
        the_agent_network_name: str = f"{self.subdirectory}/{file_reference}"

        # Write the agent network file; see get_network_file_path for the OS-separator note.
        file_path: Path = self.get_network_file_path(file_reference)
        # Create parent directory automatically if necessary
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Write a sibling temp file and swap it in with os.replace, which is atomic on POSIX and
        # Windows. Opening the target with "w" would truncate it first and fill it on a later
        # thread hop, and a concurrent same-name save reading the block through
        # async_restore_metadata in that window would see an empty file, take it as "no
        # metadata" and write the network without its block. With the swap a reader always
        # sees either the complete old file or the complete new one.
        temp_path: Path = file_path.with_name(f"{file_path.name}.{uuid4().hex}.tmp")
        try:
            async with aiofiles.open(temp_path, "w", encoding="utf-8", newline="\n") as file:
                await file.write(the_agent_network_hocon_str)
            os.replace(temp_path, file_path)
        finally:
            # Still present only if the write or the swap raised; never leave it behind.
            if temp_path.exists():
                temp_path.unlink()

        # Update the manifest.hocon file
        manifest_path: Path = Path(self.output_path) / self.subdirectory / MANIFEST_FILENAME

        # Create the generated directory if it doesn't exist
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the manifest file if it doesn't exist
        if not manifest_path.exists():
            async with aiofiles.open(manifest_path, "w", encoding="utf-8", newline="\n") as file:
                # Initialize with empty JSON format
                await file.write("{\n}")

        # Read the current manifest content
        manifest_content: str = await TextFileReader.async_read_text_file(str(manifest_path))

        # Check if the entry already exists to avoid duplicates
        if (
            f'"{the_agent_network_name}.hocon"' in manifest_content
            or f"{the_agent_network_name}.hocon" in manifest_content
        ):
            return

        # Detect format: JSON (has braces) or HOCON (no braces)
        is_json_format = "{" in manifest_content and "}" in manifest_content
        updated_content: str = ""
        if is_json_format:
            # JSON format handling
            manifest_entry: str = f'    "{the_agent_network_name}.hocon": true,'
            insert_position: int = manifest_content.rfind("}")

            if insert_position != -1:
                updated_content: str = (
                    manifest_content[:insert_position]
                    + "\n"
                    + manifest_entry
                    + "\n"
                    + manifest_content[insert_position:]
                )
        else:
            # HOCON format handling
            manifest_entry = f'"{the_agent_network_name}.hocon" = true\n'
            updated_content = manifest_content.rstrip() + "\n" + manifest_entry

        # Write the updated content back to the manifest file
        async with aiofiles.open(manifest_path, "w", encoding="utf-8", newline="\n") as file:
            await file.write(updated_content)

        # If using a non-default subdirectory, ensure it is included in the main manifest
        if self.subdirectory != DEFAULT_SUBDIRECTORY:
            await self._async_update_main_manifest()

        return str(file_path)

    async def _async_update_main_manifest(self) -> None:
        """
        Adds an include line for the current subdirectory's manifest into the main manifest,
        if not already present.
        """
        if not os.path.exists(self.main_manifest_path):
            return None

        content: str = await TextFileReader.async_read_text_file(self.main_manifest_path)

        registries_name: str = os.path.basename(self.output_path)
        include_line: str = f'include "{registries_name}/{self.subdirectory}/{MANIFEST_FILENAME}",'

        if include_line in content:
            return None

        # Insert after the last existing include line
        lines: list[str] = content.split("\n")
        last_include_idx: int = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("include "):
                last_include_idx = i

        if last_include_idx >= 0:
            lines.insert(last_include_idx + 1, f"    {include_line}")
            async with aiofiles.open(self.main_manifest_path, "w", encoding="utf-8", newline="\n") as file:
                await file.write("\n".join(lines))
