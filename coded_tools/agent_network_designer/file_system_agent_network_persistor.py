# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#

# Import for asynchronous file operations
import aiofiles

from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor


# pylint: disable=too-few-public-methods
class FileSystemAgentNetworkPersistor(AgentNetworkPersistor):
    """
    AgentNetworkPersistor implementation for saving agent networks to the file system
    as a hocon file. Also modifies the local manifest file.
    """

    OUTPUT_PATH: str = "registries/"

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
        the_agent_network_name: str = file_reference

        # Write the agent network file
        file_path: str = self.OUTPUT_PATH + the_agent_network_name + ".hocon"
        async with aiofiles.open(file_path, "w") as file:
            await file.write(the_agent_network_hocon_str)

        # Update the manifest.hocon file
        manifest_path: str = self.OUTPUT_PATH + "manifest.hocon"

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
                    manifest_content[:insert_position] + "\n" +
                    manifest_entry + "\n" +
                    manifest_content[insert_position:]
                )
        else:
            # HOCON format handling
            manifest_entry = f'"{the_agent_network_name}.hocon" = true\n'
            updated_content = manifest_content.rstrip() + "\n" + manifest_entry

        # Write the updated content back to the manifest file
        async with aiofiles.open(manifest_path, "w") as file:
            await file.write(updated_content)

        return file_path
