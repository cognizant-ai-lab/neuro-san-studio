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

"""Aggregate outcome of importing a batch of agent networks."""

from dataclasses import dataclass
from dataclasses import field
from typing import List

from neuro_san_studio.importer.import_result import ImportResult


@dataclass
class BulkImportResult:
    """Outcome of importing a batch of agent networks in one pass.

    `errors` holds the top-level failures -- a network whose analysis or import raised, and
    which therefore has no `ImportResult` at all. The `all_errors` property folds those
    together with the per-network errors, which is what every caller actually reports.
    """

    results: List[ImportResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def copied(self) -> int:
        """Total number of files copied across every network in the batch."""
        return sum(len(result.copied_files) for result in self.results)

    @property
    def skipped(self) -> int:
        """Total number of files left alone because the target already had them."""
        return sum(len(result.skipped_files) for result in self.results)

    @property
    def warnings(self) -> List[str]:
        """Every non-fatal warning raised while importing the batch."""
        return [warning for result in self.results for warning in result.warnings]

    @property
    def all_errors(self) -> List[str]:
        """Top-level failures plus the per-network ones, in that order."""
        return self.errors + [error for result in self.results for error in result.errors]

    @property
    def manifest_entries(self) -> List[str]:
        """Registry-relative HOCONs to declare in the manifest, including sub-networks."""
        return self._flatten("manifest_entries")

    @property
    def mcp_added(self) -> List[str]:
        """MCP server URLs merged into the target's mcp_info.hocon."""
        return self._flatten("mcp_added")

    @property
    def mcp_skipped(self) -> List[str]:
        """MCP server URLs the target had already configured, left untouched."""
        return self._flatten("mcp_skipped")

    def _flatten(self, attr: str) -> List[str]:
        """Concatenate one list-valued field across the results, keeping order and dropping repeats."""
        return list(dict.fromkeys(item for result in self.results for item in getattr(result, attr)))
