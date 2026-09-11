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

import tempfile
from pathlib import Path
from unittest import TestCase

from neuro_san_studio.coded_tools.file_management.path_rules import PathRules


class TestPathRules(TestCase):
    """Unit tests for the PathRules pre-parsed allow/block rule set."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _rules(self, **kwargs) -> PathRules:
        """Build PathRules with allowed_paths defaulted to the temp root."""
        args = {"allowed_paths": [str(self.tmp_root)]}
        args.update(kwargs)
        return PathRules(args)

    def _deny(self, rules: PathRules, path: Path, display_name: str | None = None, is_directory: bool = False):
        """Invoke deny_reason with the display name defaulted to the path's own name."""
        return rules.deny_reason(path, display_name if display_name is not None else path.name, is_directory)

    # ------------------------------------------------------------ construction

    def test_missing_allowed_paths_raises_invalid_input(self):
        """Tests that construction fails loudly when allowed_paths is missing or empty."""
        for args in [{}, {"allowed_paths": []}]:
            with self.assertRaises(ValueError) as ctx:
                PathRules(args)
            self.assertIn("invalid_input", str(ctx.exception))

    def test_unresolvable_rule_entry_raises_invalid_input_up_front(self):
        """Tests that a malformed rule entry fails at construction, never midway through a scan."""
        with self.assertRaises(ValueError) as ctx:
            self._rules(blocked_paths=["bad\x00entry"])
        self.assertIn("invalid_input", str(ctx.exception))

    def test_blank_rule_entry_raises_invalid_input(self):
        """Tests that blank entries are rejected (CWD-resolution hazard, fail closed)."""
        with self.assertRaises(ValueError) as ctx:
            PathRules({"allowed_paths": [""]})
        self.assertIn("invalid_input", str(ctx.exception))

    # ------------------------------------------------------------- deny_reason

    def test_path_inside_allowed_root_allowed(self):
        """Tests that a file under an allowed root with no other rules passes."""
        self.assertIsNone(self._deny(self._rules(), self.tmp_root / "a.txt"))

    def test_path_outside_allowed_root_denied(self):
        """Tests that a path outside every allowed root is denied."""
        self.assertEqual(self._deny(self._rules(), Path("/some/other/root/a.txt")), "outside_allowed_paths")

    def test_blocked_path_denied(self):
        """Tests that a path under a blocked subtree is denied even inside an allowed root."""
        rules = self._rules(blocked_paths=[str(self.tmp_root / "secret")])
        self.assertEqual(self._deny(rules, self.tmp_root / "secret" / "a.txt"), "blocked_path")

    def test_allowed_extensions_filter_files_not_directories(self):
        """Tests that the extension allow-list applies to files but exempts directories."""
        rules = self._rules(allowed_file_extensions=[".txt"])
        self.assertIsNone(self._deny(rules, self.tmp_root / "a.txt"))
        self.assertEqual(self._deny(rules, self.tmp_root / "a.log"), "extension_not_allowed")
        # A directory named 'data' must not be denied as pseudo-extension '.data'.
        self.assertIsNone(self._deny(rules, self.tmp_root / "data", is_directory=True))

    def test_empty_allowed_extensions_denies_files_but_not_directories(self):
        """Tests that an empty allow-list omits all files while directories stay visible."""
        rules = self._rules(allowed_file_extensions=[])
        self.assertEqual(self._deny(rules, self.tmp_root / "a.txt"), "extension_not_allowed")
        self.assertIsNone(self._deny(rules, self.tmp_root / "sub", is_directory=True))

    def test_display_and_resolved_suffixes_both_must_pass_allow_list(self):
        """Tests the fail-closed symlink rule: every candidate suffix must be allowed."""
        rules = self._rules(allowed_file_extensions=[".txt"])
        # Symlink 'notes.txt' -> extensionless 'README': resolved pseudo-suffix fails.
        self.assertEqual(
            rules.deny_reason(self.tmp_root / "README", "notes.txt", False),
            "extension_not_allowed",
        )
        # Symlink 'notes.txt' -> 'real.txt': both suffixes allowed.
        self.assertIsNone(rules.deny_reason(self.tmp_root / "real.txt", "notes.txt", False))

    def test_blocked_extension_matches_either_name(self):
        """Tests that a block rule fires on the displayed name OR the resolved name."""
        rules = self._rules(blocked_file_extensions=[".env"])
        # Displayed name blocked, target innocent: a '.env'-named symlink must not be listed.
        self.assertEqual(
            rules.deny_reason(self.tmp_root / "readme.txt", "prod.env", False),
            "blocked_extension",
        )
        # Displayed name innocent, target blocked.
        self.assertEqual(
            rules.deny_reason(self.tmp_root / "secrets.env", "innocent.txt", False),
            "blocked_extension",
        )

    def test_blocked_extension_applies_to_directories(self):
        """Tests that block rules are never exempted, even for directories."""
        rules = self._rules(blocked_file_extensions=[".env"])
        self.assertEqual(
            self._deny(rules, self.tmp_root / "prod.env", is_directory=True),
            "blocked_extension",
        )

    def test_root_allowed_path_admits_every_absolute_path(self) -> None:
        """Tests that an allowed root of '/' matches any resolved path (ancestor walk reaches the root)."""
        rules = PathRules({"allowed_paths": ["/"]})
        self.assertIsNone(self._deny(rules, self.tmp_root / "deep" / "nested" / "a.txt"))

    def test_sibling_prefix_is_not_a_match(self) -> None:
        """Tests that root matching is by path component, so '/x/data' never admits '/x/database'."""
        rules = PathRules({"allowed_paths": [str(self.tmp_root / "data")]})
        self.assertIsNone(self._deny(rules, self.tmp_root / "data" / "a.txt"))
        self.assertEqual(self._deny(rules, self.tmp_root / "database" / "a.txt"), "outside_allowed_paths")
        self.assertEqual(self._deny(rules, self.tmp_root / "data.txt"), "outside_allowed_paths")

    def test_many_roots_do_not_change_verdicts(self) -> None:
        """Tests that verdicts are identical with one root or many (the lookup is indexed, not scanned)."""
        roots: list[str] = []
        for index in range(200):
            roots.append(str(self.tmp_root / f"root{index}"))
        roots.append(str(self.tmp_root / "real"))
        rules = PathRules({"allowed_paths": roots, "blocked_paths": [str(self.tmp_root / "real" / "secret")]})
        self.assertIsNone(self._deny(rules, self.tmp_root / "real" / "a.txt"))
        self.assertEqual(self._deny(rules, self.tmp_root / "real" / "secret" / "a.txt"), "blocked_path")
        self.assertEqual(self._deny(rules, self.tmp_root / "other" / "a.txt"), "outside_allowed_paths")

    def test_extension_normalization(self):
        """Tests that rule extensions match case-insensitively with or without the leading dot."""
        rules = self._rules(allowed_file_extensions=["TXT"])
        self.assertIsNone(self._deny(rules, self.tmp_root / "a.TXT"))
