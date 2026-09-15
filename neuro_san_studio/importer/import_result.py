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

"""Outcome of importing a single agent network."""

from dataclasses import dataclass
from dataclasses import field
from typing import ClassVar
from typing import List
from typing import Tuple


@dataclass
class ImportResult:  # pylint: disable=too-many-instance-attributes
    """Outcome of importing one agent network into the target project.

    A value object accumulating every interesting datum from one import; the breadth
    of fields reflects the breadth of an import (files copied/skipped, manifest entries,
    MCP merge deltas, warnings, errors), not a missing abstraction.
    """

    network_name: str
    hocon_path: str
    copied_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    mcp_added: List[str] = field(default_factory=list)
    mcp_skipped: List[str] = field(default_factory=list)
    # Manifest-relative HOCONs that should be registered for serving. Includes the top-level
    # network plus every transitively-imported sub-network. Distinct from copied_files because
    # copied_files also contains coded_tools/middleware/__init__.py paths that don't belong
    # in the manifest, and because skipped (already-present) HOCONs still need their key
    # ensured in the manifest if the import had to register a new entry for it.
    manifest_entries: List[str] = field(default_factory=list)

    # Display-path convention for copied_files / skipped_files. Everything the importer records
    # is relative to the target project root ("coded_tools/pkg/tool.py", or "registries/x.hocon"
    # for a zip entry) EXCEPT registry HOCONs delivered by name, which are recorded relative to
    # registries/ ("basic/music_nerd.hocon") because that is the form the manifest and the CLI
    # speak. Cross-mode comparisons must therefore go through canonical_display first. This is
    # also the zip whitelist: the importer aliases it so the two lists cannot drift apart.
    TARGET_ROOTS: ClassVar[Tuple[str, ...]] = ("registries/", "coded_tools/", "middleware/", "skills/", "mcp/")

    @staticmethod
    def canonical_display(display: str) -> str:
        """
        Return a recorded display path in target-relative form.

        A display that already starts with one of the target's top-level roots is target-relative
        and comes back unchanged; anything else is a registries-relative HOCON name and gains the
        ``registries/`` prefix. Batches mixing import modes need this: ``ns import foo.hocon
        bundle.zip`` records the very same target file as ``foo.hocon`` from the first input and
        ``registries/foo.hocon`` from the second.

        :param display: A path as recorded in ``copied_files`` or ``skipped_files``.
        :return: The same path expressed relative to the target project root.
        """
        for root in ImportResult.TARGET_ROOTS:
            if display.startswith(root):
                return display
        return "registries/" + display
