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

# Import for asynchronous file operations
import os

import aiofiles

from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler
from middleware.agent_network_designer.persistence.agent_network_persistor import AgentNetworkPersistor
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler


DEFAULT_SUBDIRECTORY: str = "generated"


class FileSystemAgentNetworkPersistor(AgentNetworkPersistor):
    """
    AgentNetworkPersistor implementation for saving agent networks to the file system
    as a hocon file. Also modifies the local manifest file.
    """

    def __init__(self, demo_mode: bool, subdirectory: str = DEFAULT_SUBDIRECTORY):
        """
        Creates a new persistor of the specified type.

        :param demo_mode: Whether to include demo mode instructions for agents
        :param subdirectory: The subdirectory under output_path where networks are saved.
        """
        self.demo_mode: bool = demo_mode
        self.subdirectory: str = subdirectory

        # Derive output_path from the first file listed in AGENT_MANIFEST_FILE
        agent_manifest_file: str = os.environ.get("AGENT_MANIFEST_FILE", "")
        parts: list[str] = agent_manifest_file.split()
        if parts:
            self.output_path: str = os.path.dirname(parts[0])
            self.main_manifest_path: str = parts[0]
        else:
            self.output_path = "registries"
            self.main_manifest_path = os.path.join("registries", "manifest.hocon")

    def get_assembler(self) -> AgentNetworkAssembler:
        """
        :return: An assembler instance associated with this persistor
        """
        return HoconAgentNetworkAssembler(self.demo_mode)

    async def async_persist(self, obj: str, file_reference: str = None) -> str:
        """
        Persists the object passed in.

        :param obj: an object to persist.
                In this case this is the agent network hocon string.
        :param file_reference: The file reference to use when persisting.
                Default is None, implying the file reference is up to the
                implementation.
        :return an object describing the location to which the object was persisted
        """

        the_agent_network_hocon_str: str = obj
        # This agent network name already includes any subdirectory specified.
        the_agent_network_name: str = file_reference

        # Write the agent network file
        file_path: str = os.path.join(self.output_path, the_agent_network_name + ".hocon")
        # Create parent directory automatically if necessary
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        async with aiofiles.open(file_path, "w") as file:
            await file.write(the_agent_network_hocon_str)

        # Update the manifest.hocon file
        manifest_path: str = os.path.join(self.output_path, self.subdirectory, "manifest.hocon")

        # Create the generated directory if it doesn't exist
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

        # Create the manifest file if it doesn't exist
        if not os.path.exists(manifest_path):
            async with aiofiles.open(manifest_path, "w") as file:
                # Initialize with empty JSON format
                await file.write("{\n}")

        # Read the current manifest content
        async with aiofiles.open(manifest_path, "r") as file:
            manifest_content: str = await file.read()

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
        async with aiofiles.open(manifest_path, "w") as file:
            await file.write(updated_content)

        # If using a non-default subdirectory, ensure it is included in the main manifest
        if self.subdirectory != DEFAULT_SUBDIRECTORY:
            await self._async_update_main_manifest()

        return file_path

    async def _async_update_main_manifest(self) -> None:
        """
        Adds an include line for the current subdirectory's manifest into the main manifest,
        if not already present.
        """
        if not os.path.exists(self.main_manifest_path):
            return None

        async with aiofiles.open(self.main_manifest_path, "r") as file:
            content: str = await file.read()

        registries_name: str = os.path.basename(self.output_path)
        include_line: str = f'include "{registries_name}/{self.subdirectory}/manifest.hocon",'

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
            async with aiofiles.open(self.main_manifest_path, "w") as file:
                await file.write("\n".join(lines))
