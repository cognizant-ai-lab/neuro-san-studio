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
from typing import Set

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
    def skipped_preexisting(self) -> int:
        """
        Number of distinct files skipped that were NOT delivered earlier in this same batch.

        Networks in a batch routinely re-offer files a sibling already landed — every network
        offers the shared includes, and a sub-network copied transitively may also be listed
        top-level. Those skips are batch bookkeeping, not project state: reporting them as
        "already exist" makes a fresh `ns init` look like it found prior files. Only the
        files counted here genuinely predate the batch.

        Distinct files, not skip events: eight networks re-offering the same pre-existing
        include is one file the user already has, not eight. A skip whose path sits inside
        a directory the batch copied (a package dependency lands via copytree under the
        directory's display) was also delivered by the batch and is excluded, as is a
        skipped directory that only exists because the batch copied a file beneath it.

        Displays are compared in canonical target-relative form: a registry HOCON imported by
        name is recorded as ``foo.hocon`` while the same file inside a zip is recorded as
        ``registries/foo.hocon``, so a batch mixing import modes would otherwise report its
        own re-offer as pre-existing.

        :return: The count of distinct skipped display paths that the batch neither copied
            directly nor delivered inside a copied directory.
        """
        copied_in_batch: Set[str] = set()
        for result in self.results:
            for copied_file in result.copied_files:
                copied_in_batch.add(ImportResult.canonical_display(copied_file))
        distinct_skips: Set[str] = set()
        for result in self.results:
            for skipped_file in result.skipped_files:
                distinct_skips.add(ImportResult.canonical_display(skipped_file))
        count: int = 0
        for skipped_file in distinct_skips:
            if skipped_file in copied_in_batch:
                continue
            if self._inside_copied_directory(skipped_file, copied_in_batch):
                continue
            if self._created_by_a_copy_beneath(skipped_file, copied_in_batch):
                continue
            count += 1
        return count

    @staticmethod
    def _inside_copied_directory(skipped_file: str, copied_in_batch: Set[str]) -> bool:
        """
        Whether a skipped display path lies inside a directory display the batch copied.

        :param skipped_file: The skipped file's canonical display path, e.g. ``"coded_tools/pkg/helper.py"``.
        :param copied_in_batch: Every display path the batch recorded as copied, canonical form.
        :return: True when some copied display is a directory prefix of ``skipped_file``.
        """
        for copied_file in copied_in_batch:
            if skipped_file.startswith(copied_file + "/"):
                return True
        return False

    @staticmethod
    def _created_by_a_copy_beneath(skipped_file: str, copied_in_batch: Set[str]) -> bool:
        """
        Whether a skipped display is a directory that an earlier copy in the batch brought into being.

        `_copy_file_or_dir` records a directory dependency as skipped whenever its target
        already exists -- including when the only reason it exists is that an earlier
        dependency copied a file beneath it and `os.makedirs` created the directory on the
        way. That directory is batch output, not prior state, so it must not be reported
        as "already exist".

        This is an inference from recorded paths, not filesystem history: a directory that
        pre-existed and merely received a new file during the batch is read the same way.
        Telling the two apart needs the importer to record the directories it creates,
        which ImportResult does not carry; the fresh-import shape is the one this summary
        exists to get right, so the inference errs toward it.

        :param skipped_file: The skipped display's canonical path, e.g. ``"coded_tools/pkg"``.
        :param copied_in_batch: Every display path the batch recorded as copied, canonical form.
        :return: True when some copied display lies beneath ``skipped_file``.
        """
        for copied_file in copied_in_batch:
            if copied_file.startswith(skipped_file + "/"):
                return True
        return False

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
