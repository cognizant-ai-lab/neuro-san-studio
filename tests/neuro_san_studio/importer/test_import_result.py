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

"""Tests for ImportResult's display-path convention."""

import unittest

from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter
from neuro_san_studio.importer.import_result import ImportResult


class TestImportResult(unittest.TestCase):
    """`canonical_display` must map every recorded display onto one target-relative form."""

    def test_registry_hocon_names_gain_the_registries_prefix(self) -> None:
        """
        A HOCON recorded relative to registries/ (how import_network records it) is re-rooted.
        """
        self.assertEqual(ImportResult.canonical_display("aaosa.hocon"), "registries/aaosa.hocon")
        self.assertEqual(
            ImportResult.canonical_display("basic/music_nerd.hocon"),
            "registries/basic/music_nerd.hocon",
        )

    def test_target_relative_paths_are_returned_unchanged(self) -> None:
        """
        A display already under one of the target roots (zip entries, coded tools, inits) is kept.
        """
        for root in ImportResult.TARGET_ROOTS:
            display: str = root + "some/file.py"
            self.assertEqual(ImportResult.canonical_display(display), display)

    def test_target_roots_are_the_zip_whitelist(self) -> None:
        """
        The importer's zip whitelist must be the very same tuple, so the two cannot drift.
        """
        self.assertIs(AgentNetworkImporter.ALLOWED_TOP_LEVEL, ImportResult.TARGET_ROOTS)
