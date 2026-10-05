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

"""Tests for temporary fixture success-ratio changes."""

import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from neuro_san_studio.agent_network_consultant.fixture_ratio_manager import FixtureRatioManager


class TestFixtureRatioManager(TestCase):
    """Verify that success-ratio changes are selective and reversible."""

    FIXTURE_TEXT = '{"success_ratio": "3/3", "interactions": []}'

    def setUp(self) -> None:
        """Create one isolated fixture directory for each test."""
        self.directory = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Remove the isolated fixture directory after each test."""
        shutil.rmtree(self.directory)

    def _fixture(self, name: str) -> Path:
        """
        Create a fixture with the default success ratio.

        :param name: The fixture file name.
        :return: The created fixture path.
        """
        path = self.directory / name
        path.write_text(self.FIXTURE_TEXT, encoding="utf-8")
        return path

    def test_set_for_paths_records_and_replaces_original_ratio(self) -> None:
        """Record the original ratio before replacing it."""
        fixture = self._fixture("one.hocon")

        originals = FixtureRatioManager.set_for_paths([str(fixture)], "1/1")

        self.assertEqual({str(fixture): "3/3"}, originals)
        self.assertIn('"success_ratio": "1/1"', fixture.read_text(encoding="utf-8"))

    def test_set_for_fixtures_changes_only_named_fixtures(self) -> None:
        """Leave unselected fixtures unchanged."""
        selected = self._fixture("selected.hocon")
        untouched = self._fixture("untouched.hocon")

        originals = FixtureRatioManager.set_for_fixtures(
            [str(selected), str(untouched)],
            [selected.name],
            "1/1",
        )

        self.assertEqual({str(selected): "3/3"}, originals)
        self.assertIn('"success_ratio": "1/1"', selected.read_text(encoding="utf-8"))
        self.assertIn('"success_ratio": "3/3"', untouched.read_text(encoding="utf-8"))

    def test_restore_continues_after_an_unreadable_fixture(self) -> None:
        """Continue restoring remaining fixture ratios when one fixture is missing."""
        good = self._fixture("good.hocon")
        missing = self.directory / "deleted-mid-run.hocon"

        FixtureRatioManager.restore({str(missing): "1/1", str(good): "1/1"})

        self.assertIn('"success_ratio": "1/1"', good.read_text(encoding="utf-8"))
