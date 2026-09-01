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

"""Console rendering for a batch of agent-network imports.

`ns init` and `ns import` run the same batch through
``AgentNetworkImporter.import_networks``; they report it the same way too. Keeping the
rendering here -- rather than in either command -- means the importer stays silent and
testable without capturing stdout, and the two commands cannot drift on what a batch
looks like when it finishes.
"""

from typing import List

from neuro_san_studio.importer.bulk_import_result import BulkImportResult
from neuro_san_studio.utils.cli_status import CliStatus

# Long lists of near-identical warnings bury the summary they belong to. Show a handful
# and count the rest; the full detail is on the failing network itself.
MAX_LISTED = 5


class ImportReporter:
    """Print per-network progress and the closing summary for an import batch."""

    @staticmethod
    def announce(hocon_path: str) -> None:
        """Progress line for one network, printed before its work starts."""
        CliStatus.info(f"Importing {hocon_path}...")

    @classmethod
    def report(cls, bulk: BulkImportResult) -> None:
        """Print the copied/skipped totals, any warnings and errors, then the MCP deltas."""
        print()
        CliStatus.info("Summary:")
        CliStatus.ok(f"Copied: {bulk.copied} files")
        if bulk.skipped:
            CliStatus.skip(f"Skipped: {bulk.skipped} files (already exist)")
        cls._print_list("Warnings", bulk.warnings, CliStatus.warn)
        cls._print_list("Errors", bulk.all_errors, CliStatus.err)
        cls._print_mcp(bulk)

    @staticmethod
    def _print_list(label: str, items: List[str], header) -> None:
        """Print at most MAX_LISTED entries under a counted header, or nothing when empty."""
        if not items:
            return
        print()
        header(f"{label} ({len(items)}):")
        for item in items[:MAX_LISTED]:
            print(f"        - {item}")
        if len(items) > MAX_LISTED:
            print(f"        ... and {len(items) - MAX_LISTED} more")

    @staticmethod
    def _print_mcp(bulk: BulkImportResult) -> None:
        """List MCP servers merged into <project>/mcp/mcp_info.hocon, plus any left untouched."""
        if bulk.mcp_added:
            print()
            CliStatus.info(f"MCP servers added to mcp/mcp_info.hocon ({len(bulk.mcp_added)}):")
            for url in bulk.mcp_added:
                print(f"        - {url}")
        if bulk.mcp_skipped:
            print()
            CliStatus.info(f"MCP servers already configured, left untouched ({len(bulk.mcp_skipped)}):")
            for url in bulk.mcp_skipped:
                print(f"        - {url}")
