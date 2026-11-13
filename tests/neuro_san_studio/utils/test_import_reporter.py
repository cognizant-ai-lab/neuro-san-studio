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

"""Tests for ImportReporter's batch summary rendering."""

import contextlib
import io
import unittest

from neuro_san_studio.importer.bulk_import_result import BulkImportResult
from neuro_san_studio.importer.import_result import ImportResult
from neuro_san_studio.utils.import_reporter import ImportReporter


class TestImportReporter(unittest.TestCase):
    """The "Skipped ... (already exist)" line must describe prior state, not batch re-offers."""

    @staticmethod
    def _render(bulk: BulkImportResult) -> str:
        """
        Run the reporter over a batch outcome and capture everything it prints.

        :param bulk: The batch outcome to summarize.
        :return: The text the reporter wrote to stdout.
        """
        buffer: io.StringIO = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ImportReporter.report(bulk)
        return buffer.getvalue()

    def test_fresh_batch_prints_no_skipped_line(self) -> None:
        """
        A batch whose only skips are within-batch duplicates reads as a clean first run.

        This is the fresh `ns init` shape: an empty directory used to end with
        "Skipped: 88 files (already exist)" purely from networks re-offering files their
        siblings had just copied.
        """
        first: ImportResult = ImportResult(
            network_name="designer",
            hocon_path="agent_network_designer.hocon",
            copied_files=["aaosa.hocon", "coded_tools/editor/logger.py"],
        )
        second: ImportResult = ImportResult(
            network_name="editor",
            hocon_path="agent_network_editor.hocon",
            skipped_files=["aaosa.hocon", "coded_tools/editor/logger.py"],
        )

        output: str = self._render(BulkImportResult(results=[first, second]))

        self.assertIn("Copied: 2 files", output)
        self.assertNotIn("already exist", output)

    def test_preexisting_skips_are_reported_with_their_own_count(self) -> None:
        """
        Only the genuinely pre-batch files appear in the skipped count.
        """
        result: ImportResult = ImportResult(
            network_name="music_nerd",
            hocon_path="basic/music_nerd.hocon",
            copied_files=["coded_tools/basic/lookup.py"],
            # One genuine collision plus one re-offer of the file copied above.
            skipped_files=["basic/music_nerd.hocon", "coded_tools/basic/lookup.py"],
        )

        output: str = self._render(BulkImportResult(results=[result]))

        self.assertIn("Skipped: 1 files (already exist)", output)
