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

"""Tests for BulkImportResult's batch-level aggregation."""

import unittest
from typing import List

from neuro_san_studio.importer.bulk_import_result import BulkImportResult
from neuro_san_studio.importer.import_result import ImportResult


class TestBulkImportResult(unittest.TestCase):
    """`skipped_preexisting` must separate real prior state from within-batch re-offers.

    Networks in a batch re-offer files a sibling already copied — every network offers the
    shared includes, and a transitively-copied sub-network may also appear top-level.
    Counting those skips as "already exist" made a fresh `ns init` in an empty directory
    report dozens of skips as if it had found prior files.
    """

    def test_within_batch_duplicates_are_not_preexisting(self) -> None:
        """
        A skip of a file some earlier network in the batch copied is bookkeeping, not state.
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
        bulk: BulkImportResult = BulkImportResult(results=[first, second])

        # The raw total still counts every skip event; only the preexisting view filters.
        self.assertEqual(bulk.skipped, 2)
        self.assertEqual(bulk.skipped_preexisting, 0)

    def test_genuinely_preexisting_skips_are_counted(self) -> None:
        """
        A skip of a file nothing in this batch copied really does predate the batch.
        """
        only: ImportResult = ImportResult(
            network_name="music_nerd",
            hocon_path="basic/music_nerd.hocon",
            skipped_files=["basic/music_nerd.hocon"],
        )
        bulk: BulkImportResult = BulkImportResult(results=[only])

        self.assertEqual(bulk.skipped_preexisting, 1)

    def test_mixed_batch_counts_only_the_preexisting_skips(self) -> None:
        """
        Re-offers and genuine collisions in the same batch must be told apart.

        aaosa.hocon predates the batch and is skipped by BOTH networks: that is one
        pre-existing file, not two — the count is distinct files, matching the summary's
        "N files" wording.
        """
        first: ImportResult = ImportResult(
            network_name="designer",
            hocon_path="agent_network_designer.hocon",
            copied_files=["coded_tools/editor/logger.py"],
            # aaosa.hocon existed before the batch (e.g. scaffolded by `ns init`).
            skipped_files=["aaosa.hocon"],
        )
        second: ImportResult = ImportResult(
            network_name="test_generator",
            hocon_path="agent_network_test_generator.hocon",
            # One within-batch re-offer, one repeat of the genuine collision.
            skipped_files=["coded_tools/editor/logger.py", "aaosa.hocon"],
        )
        bulk: BulkImportResult = BulkImportResult(results=[first, second])

        self.assertEqual(bulk.skipped, 3)
        self.assertEqual(bulk.skipped_preexisting, 1)

    def test_repeated_preexisting_skip_counts_as_one_file(self) -> None:
        """
        Several networks re-offering the same pre-existing include is one file, not several.

        This is the re-init shape: every network in the batch skips the same
        already-present shared includes, and the summary says "N files".
        """
        results: List[ImportResult] = []
        for name in ("one", "two", "three"):
            results.append(
                ImportResult(
                    network_name=name,
                    hocon_path=f"{name}.hocon",
                    skipped_files=["aaosa.hocon"],
                )
            )
        bulk: BulkImportResult = BulkImportResult(results=results)

        self.assertEqual(bulk.skipped, 3)
        self.assertEqual(bulk.skipped_preexisting, 1)

    def test_skip_inside_a_copied_directory_is_not_preexisting(self) -> None:
        """
        A file delivered inside a copied directory is batch output, not prior state.

        A package-directory dependency lands via copytree under the directory's display;
        the walker may list an inner file separately, whose skip must not read as
        "already exist" on a fresh import.
        """
        result: ImportResult = ImportResult(
            network_name="pkg_net",
            hocon_path="pkg_net.hocon",
            copied_files=["pkg_net.hocon", "coded_tools/pkg"],
            skipped_files=["coded_tools/pkg/helper.py"],
        )
        bulk: BulkImportResult = BulkImportResult(results=[result])

        self.assertEqual(bulk.skipped_preexisting, 0)

    def test_mixed_import_modes_recognize_the_same_file(self) -> None:
        """
        A file recorded registries-relative by one mode and target-relative by another is one file.

        `ns import foo.hocon bundle.zip` copies registries/foo.hocon via the first input, which
        records it as "foo.hocon", then skips it via the zip, which records "registries/foo.hocon".
        That skip is a within-batch re-offer, not prior state.
        """
        from_hocon: ImportResult = ImportResult(
            network_name="foo",
            hocon_path="foo.hocon",
            copied_files=["foo.hocon"],
        )
        from_zip: ImportResult = ImportResult(
            network_name="bundle",
            hocon_path="bundle.zip",
            skipped_files=["registries/foo.hocon"],
        )
        bulk: BulkImportResult = BulkImportResult(results=[from_hocon, from_zip])

        self.assertEqual(bulk.skipped, 1)
        self.assertEqual(bulk.skipped_preexisting, 0)

    def test_mixed_import_modes_in_the_other_order_still_match(self) -> None:
        """
        The zip landing the file first and the bare HOCON skipping it second is also a re-offer.

        A genuinely pre-existing sibling in the same batch must still be counted, so the
        canonical comparison collapses only true duplicates.
        """
        from_zip: ImportResult = ImportResult(
            network_name="bundle",
            hocon_path="bundle.zip",
            copied_files=["registries/foo.hocon", "coded_tools/foo/tool.py"],
            skipped_files=["registries/other.hocon"],
        )
        from_hocon: ImportResult = ImportResult(
            network_name="foo",
            hocon_path="foo.hocon",
            skipped_files=["foo.hocon"],
        )
        bulk: BulkImportResult = BulkImportResult(results=[from_zip, from_hocon])

        self.assertEqual(bulk.skipped, 2)
        self.assertEqual(bulk.skipped_preexisting, 1)

    def test_empty_batch_has_no_preexisting_skips(self) -> None:
        """
        An empty batch reports zero without tripping over empty aggregates.
        """
        bulk: BulkImportResult = BulkImportResult()

        self.assertEqual(bulk.skipped_preexisting, 0)
