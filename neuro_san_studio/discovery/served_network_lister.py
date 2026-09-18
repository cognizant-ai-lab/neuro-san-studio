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

"""List the external agent references served by an agent network manifest."""

import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from leaf_common.config.config_filter_chain import ConfigFilterChain
from neuro_san.internals.graph.persistence.manifest_dict_config_filter import ManifestDictConfigFilter
from neuro_san.internals.graph.persistence.manifest_key_config_filter import ManifestKeyConfigFilter
from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer
from neuro_san.internals.graph.persistence.registry_manifest_restorer import RegistryManifestRestorer
from neuro_san.internals.graph.persistence.served_manifest_config_filter import ServedManifestConfigFilter
from pyparsing.exceptions import ParseException

from neuro_san_studio.discovery.manifest_read_error import ManifestReadError


class ServedNetworkLister:  # pylint: disable=too-few-public-methods
    """List the ``/<network_name>`` references for every served entry of one manifest.

    Uses neuro-san's own manifest filters so manifest semantics are not re-implemented here:
    boolean entries are expanded to ``{"serve": ..., "public": ...}`` dictionaries; entries that are
    ``false``, ``{"serve": false}``, or dictionaries lacking ``serve`` are dropped; and names are
    derived exactly as the server derives them (``"tools/x.hocon"`` becomes ``"/tools/x"``).
    ``include`` directives are flattened by pyhocon.

    This is the shared home for the recipe that ``coded_tools/agent_network_editor/get_subnetwork.py``
    also implements for the designer's own manifest.
    """

    def __init__(self, manifest_file: str, base_dir: Optional[str] = None):
        """Initialize the lister.

        Args:
            manifest_file: Path to the manifest HOCON. A relative path is resolved against the
                current working directory before any directory change.
            base_dir: Directory to change into while parsing so that ``include "registries/..."``
                directives resolve. pyhocon resolves includes against the process working directory,
                not the manifest's location. ``None`` means do not change directory.
        """
        self.manifest_file = manifest_file
        self.base_dir = base_dir

    def list_names(self) -> List[str]:
        """Return the ``/<network_name>`` reference for every served manifest entry.

        Returns:
            Names in manifest order, e.g. ``["/agent_network_designer", "/tools/internet_info_gatherer"]``.

        Raises:
            ManifestReadError: The manifest is missing or unreadable, or ``base_dir`` cannot be entered.
        """
        abs_manifest: str = os.path.abspath(self.manifest_file)
        raw_manifest: Optional[Dict[str, Any]] = self._read_raw_manifest(abs_manifest)
        if raw_manifest is None:
            raise ManifestReadError(f"manifest file '{abs_manifest}' not found")

        filter_chain = ConfigFilterChain()
        filter_chain.register(ManifestKeyConfigFilter(abs_manifest))
        filter_chain.register(ManifestDictConfigFilter(abs_manifest))
        filter_chain.register(ServedManifestConfigFilter(abs_manifest, warn_on_skip=False, entry_for_skipped=False))
        served: Dict[str, Any] = filter_chain.filter_config(raw_manifest)

        # Passing manifest_files explicitly keeps the constructor away from the server-wide
        # AGENT_MANIFEST_FILE fallback. Construction is cheap: it stores the path and a name mapper.
        return RegistryManifestRestorer(manifest_files=abs_manifest).find_external_network_names(served)

    def _read_raw_manifest(self, abs_manifest: str) -> Optional[Dict[str, Any]]:
        """Parse the manifest from ``base_dir`` so its includes resolve, restoring the working directory after.

        Args:
            abs_manifest: Absolute path to the manifest HOCON.

        Returns:
            The raw manifest dictionary, or ``None`` when the file does not exist.

        Raises:
            ManifestReadError: ``base_dir`` cannot be entered, or the manifest cannot be read or parsed.
        """
        prev_cwd: str = os.getcwd()
        if self.base_dir:
            try:
                os.chdir(self.base_dir)
            except OSError as error:
                raise ManifestReadError(
                    f"cannot enter include base directory '{self.base_dir}' for manifest '{abs_manifest}': {error}"
                ) from error
        try:
            return RawManifestRestorer().restore(file_reference=abs_manifest)
        except (ParseException, ValueError, OSError) as error:
            # neuro-san's restorer re-wraps HOCON parse errors as ValueError; ParseException is kept in
            # case that wrapping ever goes away.
            raise ManifestReadError(f"could not read manifest '{abs_manifest}': {error}") from error
        finally:
            os.chdir(prev_cwd)
