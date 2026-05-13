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

import logging
import os
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.persistence.registry_manifest_restorer import RegistryManifestRestorer
from neuro_san.internals.graph.registry.agent_network import AgentNetwork
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer
from pyparsing.exceptions import ParseException

from coded_tools.agent_network_editor.constants import SUBNETWORK_NAMES
from coded_tools.agent_network_editor.constants import SUBNETWORKS
from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock

DEFAULT_MANIFEST_FILE = os.path.join("registries", "manifest_and.hocon")
logger = logging.getLogger(__name__)


class GetSubnetwork(CodedTool):
    """
    CodedTool implementation which provides a way to get subnetwork names and descriptions from the manifest file
    """

    @staticmethod
    async def get_subnetwork_names(sly_data: dict[str, Any]) -> list[str]:
        """
        Get the list of subnetwork names. Reads only the manifest HOCON file rather
        than each individual subnetwork's HOCON, since callers only need names
        (no descriptions). Results are cached in sly_data.

        :param sly_data: The sly_data dictionary from the agent hierarchy.
        :return: List of subnetwork name strings, or empty list if none / on error.
        """
        # If the full subnetwork dict was already loaded by get_subnetworks(),
        # reuse its keys instead of re-reading the manifest.
        if SUBNETWORKS in sly_data:
            return list(sly_data[SUBNETWORKS].keys())

        async with await SlyDataLock.get_lock(sly_data, "subnetwork_names_lock"):
            # Re-check caches after acquiring the lock.
            if SUBNETWORK_NAMES in sly_data:
                return sly_data.get(SUBNETWORK_NAMES)

            manifest_file: str = os.getenv("AGENT_NETWORK_DESIGNER_MANIFEST_FILE") or DEFAULT_MANIFEST_FILE

            logger.info(">>>>>>>>>>>>>>>>>>>Getting Subnetwork Names from Manifest>>>>>>>>>>>>>>>>>>>")
            logger.info("Manifest file: %s", manifest_file)

            # Parse the manifest HOCON directly. pyhocon resolves `include` statements,
            # so composed manifests (e.g. manifest_and.hocon) flatten into a single
            # mapping of "path/to/file.hocon" -> enabled-bool entries. Only enabled
            # entries are exposed, matching the semantics used elsewhere.
            names: list[str] = []
            try:
                restorer = AbstractAsyncConfigRestorer(file_purpose="get_subnetwork_names", must_exist=True)
                manifest: dict[str, Any] = await restorer.async_restore(file_reference=manifest_file)
                for agent_name, enabled in manifest.items():
                    # Manifest entries are either `path: true/false` or `path: { "serve": true, ... }`.
                    # Both forms are documented; the dict form is the canonical one used post-filter
                    # by RegistryManifestRestorer.
                    if enabled is True or (isinstance(enabled, dict) and enabled.get("serve") is True):
                        # External network names follow neuro-san's convention of "/<network_name>",
                        # where network_name is the manifest path without its file extension
                        # (matching AgentFileTreeMapper.filepath_to_agent_network_name).
                        # pyhocon keeps the literal quote characters in dict keys when the original
                        # HOCON key was quoted — and manifest keys are always quoted because they
                        # contain "/" — so we strip those quote chars before deriving the name.
                        clean_name: str = agent_name.replace('"', "").removesuffix(".hocon").removesuffix(".json")
                        names.append("/" + clean_name)
            except FileNotFoundError as file_error:
                logger.warning(
                    "Manifest file not found, no external agents/subnetworks will be available "
                    "in the generated network: %s",
                    file_error
                )
            except ParseException as parse_error:
                logger.warning(
                    "Failed to parse manifest '%s', no subnetwork names will be available: %s",
                    manifest_file,
                    parse_error,
                )

            # Cache whatever we found, including an empty list on failure, to avoid reloading.
            sly_data[SUBNETWORK_NAMES] = names

        return names

    # pylint: disable=too-many-locals
    @staticmethod
    async def get_subnetworks(sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        Read the subnetwork name -> description mapping
        either from a cache on sly_data or from the manifest file.

        :param sly_data: sly_data possibly containing cached subnetworks info
        :return: dict of subnetwork name to description
        """
        subnetworks: dict[str, str] = {}

        async with await SlyDataLock.get_lock(sly_data, "subnetworks_lock"):
            # Try getting from sly_data
            if SUBNETWORKS in sly_data:
                # Exit early, including for an explicitly cached empty mapping
                return sly_data.get(SUBNETWORKS)

            # Check manifest file from env var. Use a default if no value provided.
            manifest_file: str = os.getenv("AGENT_NETWORK_DESIGNER_MANIFEST_FILE") or DEFAULT_MANIFEST_FILE

            empty: dict[str, AgentNetwork] = {}
            networks: dict[str, AgentNetwork] = {}
            logger.info(">>>>>>>>>>>>>>>>>>>Getting Subnetwork Descriptions from Manifest>>>>>>>>>>>>>>>>>>>")
            logger.info("Manifest file: %s", str(manifest_file))

            # What is returned is mapping from storage type -> (name -> AgentNetwork mapping)
            restorer = RegistryManifestRestorer(manifest_file)
            try:
                # Note that any hocon includes will be done synchronously
                networks_by_storage: dict[str, dict[str, AgentNetwork]] = await restorer.async_restore()
                logger.info("Successfully loaded agent networks info from %s", str(manifest_file))

                # Put all name -> AgentNetwork mappings into a single dictionary,
                # as is expected by the rest of this tool.
                for storage_type in ["public", "protected"]:
                    one_storage_dict: dict[str, AgentNetwork] = networks_by_storage.get(storage_type, empty)
                    networks.update(one_storage_dict)

                for name, network in networks.items():
                    front_man: str = network.find_front_man()
                    desc: str = network.get_agent_tool_spec(front_man).get("function", {}).get("description")
                    if desc is not None and len(desc) > 0:
                        subnetworks["/" + name] = desc

            except FileNotFoundError as file_error:
                logger.warning(
                    "Manifest file not found, no external agents/subnetworks will be available "
                    "in the generated network: %s",
                    file_error
                )

            # Cache whatever we found, including an empty mapping on failure, to avoid reloading.
            sly_data[SUBNETWORKS] = subnetworks

        return subnetworks

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any]:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    None

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                the names and descriptions as keys and values of a dictionary.
            otherwise:
                an empty dictionary.
        """
        return await self.get_subnetworks(sly_data)
