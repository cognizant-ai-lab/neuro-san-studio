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

from neuro_san_studio.coded_tools.file_management.path_access import PathAccess


# One consolidated TestCase per source module means many test methods by design.
class TestPathAccess(TestCase):  # pylint: disable=too-many-public-methods
    """Unit tests for PathAccess.

    Covers check_path_allowed, normalize_extensions, path_matches_any, resolve_path,
    validate_allowed_paths, validate_bool, validate_extension_list, and validate_path_list.
    """

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_root = Path(self.tmpdir.name).resolve()

    def tearDown(self):
        self.tmpdir.cleanup()

    # ---------------------------------------------------------------- helpers

    def _make_doc_file(self) -> Path:
        """Create tmp_root/doc.txt (used by check_path_allowed tests) and return its path."""
        file = self.tmp_root / "doc.txt"
        file.write_text("x", encoding="utf-8")
        return file

    def _make_sub_file(self) -> Path:
        """Create tmp_root/sub/a.txt (used by path_matches_any tests) and return its path."""
        (self.tmp_root / "sub").mkdir(exist_ok=True)
        file = self.tmp_root / "sub" / "a.txt"
        file.write_text("x", encoding="utf-8")
        return file

    def _call_check_path_allowed(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, path, allowed_paths, allowed_exts=None, blocked_paths=None, blocked_exts=None
    ):
        """Invoke check_path_allowed with sensible defaults; returns None or raises."""
        return PathAccess.check_path_allowed(
            path,
            allowed_paths,
            allowed_exts,
            blocked_paths or [],
            blocked_exts,
        )

    def _call_normalize_extensions(self, extensions):
        """Invoke normalize_extensions and return the result list."""
        return PathAccess.normalize_extensions(extensions)

    def _call_path_matches_any(self, file_path, path_list):
        """Invoke path_matches_any and return the boolean result."""
        return PathAccess.path_matches_any(file_path, path_list)

    def _call_resolve_path(self, args):
        """Invoke resolve_path with the given args dict and return the result."""
        return PathAccess.resolve_path(args)

    def _call_validate_allowed_paths(self, args):
        """Invoke validate_allowed_paths and return the result."""
        return PathAccess.validate_allowed_paths(args)

    def _call_validate_bool(self, args, param_name="test_flag", default=False):
        """Invoke validate_bool with the given args dict and return the result."""
        return PathAccess.validate_bool(args, param_name, default)

    def _call_validate_extension_list(self, value, param_name="test_param"):
        """Invoke validate_extension_list with the given value and return the result."""
        return PathAccess.validate_extension_list(value, param_name)

    def _call_validate_path_list(self, value, param_name="test_param"):
        """Invoke validate_path_list with the given value and return the result."""
        return PathAccess.validate_path_list(value, param_name)

    # ---------------------------------------------------- check_path_allowed

    def test_check_path_allowed_path_outside_allow_list_denied(self):
        """Tests that a file outside every allowed_paths entry is denied."""
        file = self._make_doc_file()
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_allowed(file, ["/some/other/root"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_check_path_allowed_path_inside_allowed_dir_passes(self):
        """Tests that a file inside an allowed directory passes the path check."""
        file = self._make_doc_file()
        self._call_check_path_allowed(file, [str(self.tmp_root)])  # should not raise

    def test_check_path_allowed_exact_file_match_passes(self):
        """Tests that an exact file path in allowed_paths is accepted."""
        file = self._make_doc_file()
        self._call_check_path_allowed(file, [str(file)])  # should not raise

    def test_check_path_allowed_omitted_extensions_passes(self):
        """Tests that omitted allowed_file_extensions (None) skips the extension check."""
        file = self._make_doc_file()
        self._call_check_path_allowed(file, [str(self.tmp_root)], allowed_exts=None)  # should not raise

    def test_check_path_allowed_empty_extensions_denies_all(self):
        """Tests that an empty allowed_file_extensions list denies the read."""
        file = self._make_doc_file()
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_allowed(file, [str(self.tmp_root)], allowed_exts=[])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_check_path_allowed_extension_not_in_allow_list_denied(self):
        """Tests that a file with an extension not in allowed_file_extensions is denied."""
        file = self._make_doc_file()
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_allowed(file, [str(self.tmp_root)], allowed_exts=[".md"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_check_path_allowed_extension_in_allow_list_passes(self):
        """Tests that a file with an extension in allowed_file_extensions is accepted."""
        file = self._make_doc_file()
        self._call_check_path_allowed(file, [str(self.tmp_root)], allowed_exts=[".txt"])  # should not raise

    def test_check_path_allowed_extension_normalized_to_lowercase(self):
        """Tests that case differences in extensions are handled by normalization."""
        upper_file = self.tmp_root / "DOC.TXT"
        upper_file.write_text("x", encoding="utf-8")
        self._call_check_path_allowed(upper_file, [str(self.tmp_root)], allowed_exts=[".TXT"])  # should not raise

    def test_check_path_allowed_blocked_path_denies_even_when_allowed(self):
        """Tests that a blocked path overrides an allow-listed parent directory."""
        file = self._make_doc_file()
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_allowed(file, [str(self.tmp_root)], blocked_paths=[str(file)])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_check_path_allowed_blocked_extension_denies_even_when_allowed(self):
        """Tests that a blocked extension overrides an allow-listed extension."""
        file = self._make_doc_file()
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_allowed(file, [str(self.tmp_root)], allowed_exts=[".txt"], blocked_exts=[".txt"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_check_path_allowed_dotfile_matched_by_full_name(self):
        """Tests that a dotfile like '.env' is matched using the full filename as its extension."""
        env_file = self.tmp_root / ".env"
        env_file.write_text("x", encoding="utf-8")
        self._call_check_path_allowed(env_file, [str(self.tmp_root)], allowed_exts=[".env"])  # should not raise

    def test_check_path_allowed_dotfile_blocked_by_full_name(self):
        """Tests that a dotfile '.env' is blocked when listed in blocked_file_extensions."""
        env_file = self.tmp_root / ".env"
        env_file.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_allowed(env_file, [str(self.tmp_root)], allowed_exts=None, blocked_exts=[".env"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    def test_check_path_allowed_extensionless_file_matched_by_name(self):
        """Tests that an extensionless file like 'Dockerfile' can be whitelisted by name."""
        dockerfile = self.tmp_root / "Dockerfile"
        dockerfile.write_text("x", encoding="utf-8")
        # Accept the bare name with or without a leading dot; normalization handles both.
        self._call_check_path_allowed(dockerfile, [str(self.tmp_root)], allowed_exts=["Dockerfile"])  # no raise

    def test_check_path_allowed_extensionless_file_blocked_by_name(self):
        """Tests that an extensionless file like 'Makefile' can be blocked by name."""
        makefile = self.tmp_root / "Makefile"
        makefile.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            self._call_check_path_allowed(makefile, [str(self.tmp_root)], allowed_exts=None, blocked_exts=["Makefile"])
        self.assertIn("path_not_allowed", str(ctx.exception))

    # -------------------------------------------------- normalize_extensions

    def test_normalize_extensions_already_normalized(self):
        """Tests that lowercase dot-prefixed extensions are returned unchanged."""
        self.assertEqual(self._call_normalize_extensions([".py", ".md"]), [".py", ".md"])

    def test_normalize_extensions_adds_leading_dot(self):
        """Tests that extensions without a leading dot get one added."""
        self.assertEqual(self._call_normalize_extensions(["py", "md"]), [".py", ".md"])

    def test_normalize_extensions_lowercases_extensions(self):
        """Tests that uppercase extensions are lowercased."""
        self.assertEqual(self._call_normalize_extensions([".PY", ".Md"]), [".py", ".md"])

    def test_normalize_extensions_mixed_input(self):
        """Tests that a mix of dotted/undotted and case variants is normalized."""
        self.assertEqual(self._call_normalize_extensions(["PY", ".Md", "txt"]), [".py", ".md", ".txt"])

    def test_normalize_extensions_empty_list(self):
        """Tests that an empty list returns an empty list."""
        self.assertEqual(self._call_normalize_extensions([]), [])

    # ------------------------------------------------------ path_matches_any

    def test_path_matches_any_empty_list_returns_false(self):
        """Tests that an empty list matches no paths."""
        file = self._make_sub_file()
        self.assertFalse(self._call_path_matches_any(file, []))

    def test_path_matches_any_exact_file_match_returns_true(self):
        """Tests that the file's own path in the list matches."""
        file = self._make_sub_file()
        self.assertTrue(self._call_path_matches_any(file, [str(file)]))

    def test_path_matches_any_parent_directory_matches(self):
        """Tests that a directory containing the file matches."""
        file = self._make_sub_file()
        self.assertTrue(self._call_path_matches_any(file, [str(self.tmp_root)]))

    def test_path_matches_any_grandparent_directory_matches(self):
        """Tests that any ancestor directory matches via descendant relation."""
        file = self._make_sub_file()
        self.assertTrue(self._call_path_matches_any(file, [str(self.tmp_root.parent)]))

    def test_path_matches_any_sibling_directory_does_not_match(self):
        """Tests that a directory not containing the file is not a match."""
        file = self._make_sub_file()
        other = self.tmp_root / "other"
        other.mkdir()
        self.assertFalse(self._call_path_matches_any(file, [str(other)]))

    def test_path_matches_any_unrelated_path_does_not_match(self):
        """Tests that an unrelated path does not match."""
        file = self._make_sub_file()
        self.assertFalse(self._call_path_matches_any(file, ["/totally/different/place"]))

    def test_path_matches_any_one_of_many_matches(self):
        """Tests that the function returns True as soon as any entry matches."""
        file = self._make_sub_file()
        self.assertTrue(self._call_path_matches_any(file, ["/nope", str(self.tmp_root), "/also/nope"]))

    def test_path_matches_any_tilde_entry_expanded(self):
        """Tests that an allow-list entry like '~' is expanded to the user home directory."""
        home_file: Path = (Path.home() / "definitely-not-a-real-file.txt").resolve()
        # A path under $HOME should match an allow-list entry of '~' or '~/'.
        self.assertTrue(self._call_path_matches_any(home_file, ["~"]))

    def test_path_matches_any_invalid_entry_fails_closed(self):
        """Tests that an unresolvable entry raises invalid_input instead of being skipped.

        These lists are operator security config: silently skipping a mis-typed
        blocked_paths entry would fail open.
        """
        file = self._make_sub_file()
        # A null byte in a path is rejected by Path.resolve on most platforms.
        with self.assertRaises(ValueError) as ctx:
            self._call_path_matches_any(file, ["bad\x00entry", str(self.tmp_root)])
        self.assertIn("invalid_input", str(ctx.exception))

    # ---------------------------------------------------------- resolve_path

    def test_resolve_path_resolves_existing_file(self):
        """Tests that an existing file path is resolved to an absolute Path."""
        path = self.tmp_root / "a.txt"
        path.write_text("x", encoding="utf-8")
        self.assertEqual(self._call_resolve_path({"file_path": str(path)}), path.resolve())

    def test_resolve_path_resolves_nonexistent_path(self):
        """Tests that a nonexistent path still resolves without raising (no fs access)."""
        path = self.tmp_root / "nope.txt"
        result = self._call_resolve_path({"file_path": str(path)})
        self.assertEqual(result, path.resolve())

    def test_resolve_path_empty_string_raises(self):
        """Tests that an empty string path raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_resolve_path({"file_path": ""})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_resolve_path_unknown_user_tilde_raises_invalid_input(self):
        """Tests that '~unknownuser/...' raises invalid_input instead of leaking RuntimeError.

        Path.expanduser() raises RuntimeError (not OSError) when the named user's home
        directory cannot be determined; resolve_path must map it into the taxonomy.
        """
        with self.assertRaises(ValueError) as ctx:
            self._call_resolve_path({"file_path": "~no_such_user_xyz_12345/notes.txt"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_resolve_path_whitespace_only_raises(self):
        """Tests that a whitespace-only path raises invalid_input after stripping."""
        with self.assertRaises(ValueError) as ctx:
            self._call_resolve_path({"file_path": "   "})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_resolve_path_missing_key_raises(self):
        """Tests that an args dict missing the 'file_path' key raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_resolve_path({})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_resolve_path_non_string_raises(self):
        """Tests that a non-string path raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_resolve_path({"file_path": 123})
        self.assertIn("invalid_input", str(ctx.exception))

    # ------------------------------------------------- validate_allowed_paths

    def test_validate_allowed_paths_missing_key_raises_invalid_input(self):
        """Tests that omitting allowed_paths raises invalid_input (required parameter)."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_allowed_paths({})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_allowed_paths_empty_list_raises_invalid_input(self):
        """Tests that an empty allowed_paths list raises invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_allowed_paths({"allowed_paths": []})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_allowed_paths_valid_list_returned(self):
        """Tests that a non-empty list of path strings is returned."""
        self.assertEqual(self._call_validate_allowed_paths({"allowed_paths": ["/a", "/b"]}), ["/a", "/b"])

    def test_validate_allowed_paths_single_string_coerced(self):
        """Tests that a single string is coerced into a one-element list."""
        self.assertEqual(self._call_validate_allowed_paths({"allowed_paths": "/a"}), ["/a"])

    # --------------------------------------------------------- validate_bool

    def test_validate_bool_explicit_true_returned(self):
        """Tests that an explicit True value is returned."""
        self.assertTrue(self._call_validate_bool({"test_flag": True}))

    def test_validate_bool_explicit_false_returned(self):
        """Tests that an explicit False value is returned even when the default is True."""
        self.assertFalse(self._call_validate_bool({"test_flag": False}, default=True))

    def test_validate_bool_missing_returns_default(self):
        """Tests that an omitted parameter returns the provided default."""
        self.assertFalse(self._call_validate_bool({}))
        self.assertTrue(self._call_validate_bool({}, default=True))

    def test_validate_bool_non_bool_raises_invalid_input(self):
        """Tests that non-boolean values raise invalid_input (including truthy strings and ints)."""
        for bad in ["true", "yes", 1, 0, [], {}]:
            with self.assertRaises(ValueError) as ctx:
                self._call_validate_bool({"test_flag": bad})
            self.assertIn("invalid_input", str(ctx.exception))

    # ---------------------------------------------- validate_extension_list

    def test_validate_extension_list_none_returned_as_none_sentinel(self):
        """Tests that None is preserved (sentinel: omitted = skip filtering)."""
        self.assertIsNone(self._call_validate_extension_list(None))

    def test_validate_extension_list_empty_list_returned_as_empty(self):
        """Tests that an empty list is preserved (means deny all extensions)."""
        self.assertEqual(self._call_validate_extension_list([]), [])

    def test_validate_extension_list_single_string_coerced_to_list(self):
        """Tests that a single string extension is coerced into a one-element list."""
        self.assertEqual(self._call_validate_extension_list(".py"), [".py"])

    def test_validate_extension_list_valid_list_returned_unchanged(self):
        """Tests that a valid list of extension strings is returned unchanged."""
        exts = [".py", ".md"]
        self.assertEqual(self._call_validate_extension_list(exts), exts)

    def test_validate_extension_list_non_list_non_string_raises(self):
        """Tests that a non-list, non-string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_extension_list(42)
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_extension_list_list_with_non_string_element_raises(self):
        """Tests that a list containing a non-string element raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_extension_list([".py", 1])
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_extension_list_blank_entry_raises(self):
        """Tests that blank/whitespace entries are rejected as invalid_input (config error, fail closed)."""
        for bad in [[""], ["   "], [".py", ""]]:
            with self.assertRaises(ValueError) as ctx:
                self._call_validate_extension_list(bad)
            self.assertIn("invalid_input", str(ctx.exception))
            self.assertIn("blank", str(ctx.exception))

    # ------------------------------------------------------ validate_path_list

    def test_validate_path_list_none_returns_empty_list(self):
        """Tests that passing None returns an empty list.

        What an empty list means is up to the caller: allowed_paths requires a
        non-empty list (validate_allowed_paths), while an empty blocked_paths
        simply blocks nothing.
        """
        self.assertEqual(self._call_validate_path_list(None), [])

    def test_validate_path_list_single_string_coerced_to_list(self):
        """Tests that a single string path is coerced into a one-element list."""
        self.assertEqual(self._call_validate_path_list("/some/path"), ["/some/path"])

    def test_validate_path_list_valid_list_returned_unchanged(self):
        """Tests that a valid list of path strings is returned unchanged."""
        paths = ["/a", "/b/c"]
        self.assertEqual(self._call_validate_path_list(paths), paths)

    def test_validate_path_list_empty_list_returned_as_empty(self):
        """Tests that an empty list is returned unchanged (caller-defined semantics; see above)."""
        self.assertEqual(self._call_validate_path_list([]), [])

    def test_validate_path_list_non_list_non_string_raises(self):
        """Tests that a non-list, non-string value raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_path_list(123)
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_path_list_list_with_non_string_element_raises(self):
        """Tests that a list containing a non-string element raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_path_list(["/a", 42])
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_path_list_dict_raises(self):
        """Tests that passing a dict raises ValueError with invalid_input."""
        with self.assertRaises(ValueError) as ctx:
            self._call_validate_path_list({"path": "/a"})
        self.assertIn("invalid_input", str(ctx.exception))

    def test_validate_path_list_blank_entry_raises(self):
        """Tests that blank/whitespace entries are rejected: Path('').resolve() is the CWD, so a
        blank allow-list entry would silently grant access to the whole working-directory tree."""
        for bad in [[""], ["   "], ["/a", ""], ""]:
            with self.assertRaises(ValueError) as ctx:
                self._call_validate_path_list(bad)
            self.assertIn("invalid_input", str(ctx.exception))
            self.assertIn("blank", str(ctx.exception))
