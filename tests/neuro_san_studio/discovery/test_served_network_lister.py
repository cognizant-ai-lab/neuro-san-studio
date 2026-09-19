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

"""Tests for ServedNetworkLister: which manifest entries become accepted external agent names."""

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from neuro_san_studio.discovery.manifest_read_error import ManifestReadError
from neuro_san_studio.discovery.served_network_lister import ServedNetworkLister


def _write(path: Path, body: str) -> Path:
    """Write body to path, creating parent directories, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def _lister(manifests: Path | list[Path], base_dir: Path | None = None) -> ServedNetworkLister:
    """Build a lister over one manifest or an ordered list of manifests, optionally anchored at base_dir."""
    files = [manifests] if isinstance(manifests, Path) else manifests
    return ServedNetworkLister([str(path) for path in files], base_dir=str(base_dir) if base_dir else None)


def _names(manifests: Path | list[Path], base_dir: Path | None = None) -> list[str]:
    """Run the lister and return the served names."""
    return _lister(manifests, base_dir).list_names()


def _project_with_include(root: Path, entry: str = "a") -> Path:
    """Scaffold <root>/registries/manifest.hocon that includes registries/tools/manifest.hocon."""
    _write(root / "registries" / "tools" / "manifest.hocon", '{ "tools/x.hocon": true }\n')
    return _write(
        root / "registries" / "manifest.hocon",
        f'{{\n    include "registries/tools/manifest.hocon",\n    "{entry}.hocon": true\n}}\n',
    )


def _base_and_overlay(tmp_path: Path, base_body: str, overlay_body: str) -> list[Path]:
    """Write a base manifest and an overlay manifest and return them in composition order."""
    return [_write(tmp_path / "base.hocon", base_body), _write(tmp_path / "overlay.hocon", overlay_body)]


class TestServeSemantics:
    """Only entries the server would serve become external agent names."""

    def test_boolean_true_is_served(self, tmp_path: Path) -> None:
        """A bare `true` entry is served."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "a.hocon": true }\n')
        assert _names(manifest) == ["/a"]

    def test_boolean_false_is_dropped(self, tmp_path: Path) -> None:
        """A bare `false` entry is not served."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "a.hocon": false }\n')
        assert not _names(manifest)

    def test_dict_with_serve_true_is_served(self, tmp_path: Path) -> None:
        """A dictionary entry with serve: true is served even when not public."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "a.hocon": { "serve": true, "public": false } }\n')
        assert _names(manifest) == ["/a"]

    def test_dict_with_serve_false_is_dropped(self, tmp_path: Path) -> None:
        """A dictionary entry with serve: false is not served."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "a.hocon": { "serve": false } }\n')
        assert not _names(manifest)

    def test_dict_without_serve_is_dropped(self, tmp_path: Path) -> None:
        """A dictionary entry that omits serve is treated as not served, matching the server."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "a.hocon": { "public": true } }\n')
        assert not _names(manifest)

    def test_directory_prefix_is_kept(self, tmp_path: Path) -> None:
        """Only the extension is stripped; the directory prefix stays part of the name."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "tools/x.hocon": true }\n')
        assert _names(manifest) == ["/tools/x"]

    def test_manifest_order_is_preserved(self, tmp_path: Path) -> None:
        """Served names come back in manifest order with unserved entries removed."""
        manifest = _write(
            tmp_path / "manifest.hocon",
            '{ "first.hocon": true, "second.hocon": false, "tools/third.hocon": { "serve": true } }\n',
        )
        assert _names(manifest) == ["/first", "/tools/third"]


class TestOverlayComposition:
    """Several manifests compose as RegistryManifestRestorer.restore_from_files composes them."""

    def test_overlay_false_disables_base_true(self, tmp_path: Path) -> None:
        """A later `false` removes an earlier `true`; siblings survive."""
        manifests = _base_and_overlay(
            tmp_path, '{ "keep.hocon": true, "gone.hocon": true }\n', '{ "gone.hocon": false }\n'
        )
        assert _names(manifests) == ["/keep"]

    def test_overlay_true_re_enables_base_false(self, tmp_path: Path) -> None:
        """A later `true` re-enables an earlier `false`, as the multiuser overlay does for the designer."""
        manifests = _base_and_overlay(tmp_path, '{ "designer.hocon": false }\n', '{ "designer.hocon": true }\n')
        assert _names(manifests) == ["/designer"]

    def test_overlay_only_entry_is_appended(self, tmp_path: Path) -> None:
        """An entry that only the overlay mentions is served, after the base entries."""
        manifests = _base_and_overlay(tmp_path, '{ "a.hocon": true }\n', '{ "b.hocon": true }\n')
        assert _names(manifests) == ["/a", "/b"]

    def test_untouched_entries_keep_base_status(self, tmp_path: Path) -> None:
        """Entries the overlay does not mention keep whatever the base decided."""
        manifests = _base_and_overlay(tmp_path, '{ "a.hocon": true, "b.hocon": false }\n', '{ "c.hocon": true }\n')
        assert _names(manifests) == ["/a", "/c"]

    def test_bare_false_does_not_disable_protected_entry(self, tmp_path: Path) -> None:
        """Server quirk: a bare `false` tombstones public storage, so a protected base entry stays served."""
        manifests = _base_and_overlay(
            tmp_path, '{ "x.hocon": { "serve": true, "public": false } }\n', '{ "x.hocon": false }\n'
        )
        assert _names(manifests) == ["/x"]

    def test_protected_tombstone_disables_protected_entry(self, tmp_path: Path) -> None:
        """A tombstone in the same storage class as the base entry disables it."""
        manifests = _base_and_overlay(
            tmp_path,
            '{ "x.hocon": { "serve": true, "public": false } }\n',
            '{ "x.hocon": { "serve": false, "public": false } }\n',
        )
        assert not _names(manifests)

    def test_protected_tombstone_does_not_disable_public_entry(self, tmp_path: Path) -> None:
        """Server quirk in the other direction: a protected tombstone leaves a public base entry served."""
        manifests = _base_and_overlay(
            tmp_path, '{ "x.hocon": true }\n', '{ "x.hocon": { "serve": false, "public": false } }\n'
        )
        assert _names(manifests) == ["/x"]

    def test_missing_overlay_is_skipped_with_warning(self, tmp_path: Path) -> None:
        """A manifest that does not exist is skipped and reported; the others still compose."""
        base = _write(tmp_path / "base.hocon", '{ "a.hocon": true }\n')
        lister = _lister([base, tmp_path / "missing.hocon"])
        assert lister.list_names() == ["/a"]
        assert len(lister.warnings) == 1
        assert "missing.hocon" in lister.warnings[0]
        assert "not found" in lister.warnings[0]

    def test_each_manifest_resolves_includes_from_its_own_root(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Without base_dir, every manifest's includes resolve from that manifest's grandparent directory."""
        first = _write(tmp_path / "one" / "registries" / "manifest.hocon", '{ "a.hocon": true }\n')
        second = _project_with_include(tmp_path / "two", entry="b")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert set(_names([first, second])) == {"/a", "/b", "/tools/x"}


class TestIncludeResolution:
    """pyhocon resolves includes against the working directory, so the include base controls what is found."""

    def test_base_dir_resolves_includes_from_any_cwd(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """With base_dir set to the project root, included sub-manifests are found from an unrelated cwd."""
        root = _project_with_include(tmp_path / "project")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert set(_names(root, base_dir=tmp_path / "project")) == {"/a", "/tools/x"}

    def test_default_base_dir_is_manifest_grandparent(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Without base_dir, includes resolve from the manifest's grandparent, so the cwd does not matter."""
        root = _project_with_include(tmp_path / "project")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert set(_names(root)) == {"/a", "/tools/x"}

    def test_relative_manifest_path_is_resolved_before_chdir(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """A relative manifest path is anchored to the caller's cwd, not to base_dir."""
        _project_with_include(tmp_path / "project")
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.chdir(tmp_path / "project")
        names = ServedNetworkLister(["registries/manifest.hocon"], base_dir=str(other)).list_names()
        # The manifest itself is found; its include does not resolve from `other`, so only the root entry remains.
        assert names == ["/a"]

    def test_cwd_restored_after_success(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """The working directory is restored after a successful read."""
        root = _project_with_include(tmp_path / "project")
        monkeypatch.chdir(tmp_path)
        _names(root, base_dir=tmp_path / "project")
        assert Path.cwd().resolve() == tmp_path.resolve()

    def test_cwd_restored_after_parse_failure(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """The working directory is restored even when parsing fails."""
        bad = _write(tmp_path / "project" / "registries" / "manifest.hocon", '{ "a.hocon": true\n')
        monkeypatch.chdir(tmp_path)
        assert not _names(bad, base_dir=tmp_path / "project")
        assert Path.cwd().resolve() == tmp_path.resolve()


class TestFailures:
    """Unreadable manifests are skipped with a reason; a bad include base is an error."""

    def test_missing_manifest_is_skipped_with_warning(self, tmp_path: Path) -> None:
        """A nonexistent manifest yields no names and one 'not found' warning naming the path."""
        missing = tmp_path / "registries" / "manifest.hocon"
        lister = _lister(missing)
        assert not lister.list_names()
        assert lister.warnings == [f"manifest file '{missing}' not found"]

    def test_unparseable_manifest_is_skipped_with_warning(self, tmp_path: Path) -> None:
        """A HOCON syntax error yields no names and one 'could not read' warning."""
        bad = _write(tmp_path / "manifest.hocon", '{ "a.hocon": true\n')
        lister = _lister(bad)
        assert not lister.list_names()
        assert len(lister.warnings) == 1
        assert lister.warnings[0].startswith(f"could not read manifest '{bad}'")

    def test_warnings_reset_on_each_run(self, tmp_path: Path) -> None:
        """Calling list_names() twice does not accumulate warnings."""
        lister = _lister(tmp_path / "missing.hocon")
        lister.list_names()
        lister.list_names()
        assert len(lister.warnings) == 1

    def test_missing_base_dir_raises_and_keeps_cwd(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """A base_dir that does not exist is an error, and the working directory is untouched."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "a.hocon": true }\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ManifestReadError, match="include base directory"):
            _names(manifest, base_dir=tmp_path / "nope")
        assert Path.cwd().resolve() == tmp_path.resolve()
