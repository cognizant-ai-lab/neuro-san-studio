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

"""List the external agent references served by one or more agent network manifests."""

import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

from leaf_common.config.config_filter_chain import ConfigFilterChain
from neuro_san.internals.graph.persistence.manifest_dict_config_filter import ManifestDictConfigFilter
from neuro_san.internals.graph.persistence.manifest_key_config_filter import ManifestKeyConfigFilter
from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer
from neuro_san.internals.graph.persistence.registry_manifest_restorer import RegistryManifestRestorer
from neuro_san.internals.interfaces.storage_class import StorageClass
from pyparsing.exceptions import ParseException

from neuro_san_studio.discovery.manifest_read_error import ManifestReadError


class ServedNetworkLister:  # pylint: disable=too-few-public-methods
    """List the ``/<network_name>`` references served by one or more manifests, composed as the server composes them.

    Mirrors ``RegistryManifestRestorer.restore_from_files``: each manifest is normalized with neuro-san's own
    manifest filters, every entry is placed under the storage class its ``public`` flag implies (``public`` or
    ``protected``), and later manifests override earlier ones entry by entry. A non-served entry (``false``,
    ``{"serve": false}``, or a dictionary lacking ``serve``) acts as a tombstone for that storage class only, so an
    overlay manifest can disable a network or re-enable one. A network is served when any storage class still holds
    a live entry after composition. Names are derived exactly as the server derives them (``"tools/x.hocon"``
    becomes ``"/tools/x"``), and ``include`` directives are flattened by pyhocon.

    Two deliberate simplifications. A manifest that is missing, unparseable, or malformed is skipped with a
    message in ``warnings`` rather than aborting, as the server does. And every served entry is treated as
    served, whereas the server stores nothing for a served entry whose network fails to load; knowing that
    would require loading every network.

    This is the shared home for the recipe that ``coded_tools/agent_network_editor/get_subnetwork.py`` also
    implements for the designer's own manifest.
    """

    def __init__(self, manifest_files: Sequence[str], base_dir: Optional[str] = None):
        """Initialize the lister.

        Args:
            manifest_files: Paths to the manifest HOCON files, earliest first. Relative paths are resolved
                against the current working directory before any directory change.
            base_dir: Directory to change into while parsing every manifest so that ``include "registries/..."``
                directives resolve. pyhocon resolves includes against the process working directory, not the
                manifest's location. ``None`` uses each manifest's grandparent directory, which is the project
                root in the standard ``<root>/registries/manifest.hocon`` layout.
        """
        self.manifest_files: List[str] = list(manifest_files)
        self.base_dir: Optional[str] = base_dir
        # Populated by list_names(): one human-readable reason per manifest that was skipped.
        self.warnings: List[str] = []

    def list_names(self) -> List[str]:
        """Return the ``/<network_name>`` reference for every network the composed manifests serve.

        Returns:
            Names in manifest order, with names introduced by later manifests appended, e.g.
            ``["/agent_network_designer", "/tools/internet_info_gatherer"]``.

        Raises:
            ManifestReadError: ``base_dir`` was given but is not a directory.
        """
        self.warnings = []
        if self.base_dir and not os.path.isdir(self.base_dir):
            raise ManifestReadError(f"include base directory '{self.base_dir}' does not exist")

        # (storage class, "/name") -> served? Later manifests overwrite earlier keys, mirroring the server's overlay.
        composite: Dict[Tuple[str, str], bool] = {}
        for manifest_file in self.manifest_files:
            for storage, name, is_served in self._serve_statuses(os.path.abspath(manifest_file)):
                composite[(storage, name)] = is_served

        served: List[str] = [name for (_, name), is_served in composite.items() if is_served]
        # A name that is live in both storage classes appears once.
        return list(dict.fromkeys(served))

    def _serve_statuses(self, abs_manifest: str) -> List[Tuple[str, str, bool]]:
        """Read one manifest and return ``(storage class, "/name", served?)`` for each of its entries.

        Every failure here is a problem with the manifest, not with the network being validated, so it
        is recorded in ``warnings`` and the manifest is skipped, as the server skips a manifest it
        cannot use.

        Args:
            abs_manifest: Absolute path to the manifest HOCON.

        Returns:
            One tuple per entry in manifest order, or an empty list when the manifest was skipped.
        """
        raw_manifest: Optional[Any] = self._read_raw_manifest(abs_manifest)
        if raw_manifest is None:
            return []
        if not isinstance(raw_manifest, dict):
            self.warnings.append(
                f"manifest '{abs_manifest}' must be a dictionary of entries, not {type(raw_manifest).__name__}"
            )
            return []
        try:
            entries: Dict[str, Dict[str, Any]] = self._normalize(abs_manifest, raw_manifest)
            names: List[str] = RegistryManifestRestorer(manifest_files=abs_manifest).find_external_network_names(
                entries
            )
            return [
                (
                    StorageClass.PUBLIC if entry.get(StorageClass.PUBLIC) else StorageClass.PROTECTED,
                    name,
                    bool(entry.get("serve", False)),
                )
                for name, entry in zip(names, entries.values())
            ]
        except Exception as error:  # pylint: disable=broad-except
            # neuro-san's filters assume well-formed entries and raise AttributeError or similar on odd
            # shapes, for example a string where a dictionary is expected. Any such failure is a manifest
            # problem and must not surface as a validation error against the network file.
            self.warnings.append(f"could not process manifest '{abs_manifest}': {error}")
            return []

    @staticmethod
    def _normalize(abs_manifest: str, raw_manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Normalize raw manifest entries with neuro-san's own filters, keeping non-served entries as tombstones.

        ``ManifestKeyConfigFilter`` cleans the keys. ``ManifestDictConfigFilter`` expands booleans into
        ``{"serve": ..., "public": ...}`` dictionaries and applies the MCP and periodic defaults, which is what
        decides each entry's storage class. Non-served entries are kept on purpose: their storage class decides
        which earlier entry they override.

        Args:
            abs_manifest: Absolute path to the manifest, used by the filters for diagnostics.
            raw_manifest: The manifest dictionary as parsed from HOCON.

        Returns:
            Manifest key to normalized entry dictionary, in manifest order.
        """
        filter_chain = ConfigFilterChain()
        filter_chain.register(ManifestKeyConfigFilter(abs_manifest))
        filter_chain.register(ManifestDictConfigFilter(abs_manifest))
        return filter_chain.filter_config(raw_manifest)

    def _read_raw_manifest(self, abs_manifest: str) -> Optional[Any]:
        """Parse one manifest with its includes resolved, restoring the working directory afterwards.

        Args:
            abs_manifest: Absolute path to the manifest HOCON.

        Returns:
            Whatever the HOCON parsed to, normally a dictionary, or ``None`` when the manifest was skipped.
            The reason is appended to ``warnings``. The caller checks the shape.
        """
        include_base: str = self.base_dir or os.path.dirname(os.path.dirname(abs_manifest))
        prev_cwd: str = os.getcwd()
        try:
            os.chdir(include_base)
            raw_manifest: Optional[Any] = RawManifestRestorer().restore(file_reference=abs_manifest)
        except (ParseException, ValueError, OSError) as error:
            # neuro-san's restorer re-wraps HOCON parse errors as ValueError; ParseException is kept in case that
            # wrapping ever goes away. OSError covers an unreadable file or include base directory.
            self.warnings.append(f"could not read manifest '{abs_manifest}': {error}")
            return None
        finally:
            os.chdir(prev_cwd)

        if raw_manifest is None:
            self.warnings.append(f"manifest file '{abs_manifest}' not found")
        return raw_manifest
