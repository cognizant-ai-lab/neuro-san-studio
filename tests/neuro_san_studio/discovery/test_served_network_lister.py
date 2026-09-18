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


def _names(manifest: Path, base_dir: Path | None = None) -> list[str]:
    """Run the lister on manifest, optionally anchored at base_dir."""
    return ServedNetworkLister(str(manifest), base_dir=str(base_dir) if base_dir else None).list_names()


def _project_with_include(root: Path) -> Path:
    """Scaffold <root>/registries/manifest.hocon that includes registries/tools/manifest.hocon."""
    _write(root / "registries" / "tools" / "manifest.hocon", '{ "tools/x.hocon": true }\n')
    return _write(
        root / "registries" / "manifest.hocon",
        '{\n    include "registries/tools/manifest.hocon",\n    "a.hocon": true\n}\n',
    )


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


class TestIncludeResolution:
    """pyhocon resolves includes against the working directory, so base_dir controls what is found."""

    def test_base_dir_resolves_includes_from_any_cwd(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """With base_dir set to the project root, included sub-manifests are found from an unrelated cwd."""
        root = _project_with_include(tmp_path / "project")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert set(_names(root, base_dir=tmp_path / "project")) == {"/a", "/tools/x"}

    def test_without_base_dir_includes_resolve_against_cwd(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """Without base_dir, a missing include is silently empty and only root entries are found."""
        root = _project_with_include(tmp_path / "project")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert _names(root) == ["/a"]

    def test_relative_manifest_path_is_resolved_before_chdir(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """A relative manifest path is anchored to the caller's cwd, not to base_dir."""
        _project_with_include(tmp_path / "project")
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.chdir(tmp_path / "project")
        names = ServedNetworkLister("registries/manifest.hocon", base_dir=str(other)).list_names()
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
        with pytest.raises(ManifestReadError):
            _names(bad, base_dir=tmp_path / "project")
        assert Path.cwd().resolve() == tmp_path.resolve()


class TestFailures:
    """Unreadable manifests raise ManifestReadError with a reason the caller can print."""

    def test_missing_manifest_raises(self, tmp_path: Path) -> None:
        """A nonexistent manifest path is reported as not found."""
        with pytest.raises(ManifestReadError, match="not found"):
            _names(tmp_path / "registries" / "manifest.hocon")

    def test_unparseable_manifest_raises(self, tmp_path: Path) -> None:
        """A HOCON syntax error is reported as unreadable."""
        bad = _write(tmp_path / "manifest.hocon", '{ "a.hocon": true\n')
        with pytest.raises(ManifestReadError, match="could not read"):
            _names(bad)

    def test_missing_base_dir_raises_and_keeps_cwd(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """A base_dir that does not exist is reported and the working directory is untouched."""
        manifest = _write(tmp_path / "manifest.hocon", '{ "a.hocon": true }\n')
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ManifestReadError, match="include base directory"):
            _names(manifest, base_dir=tmp_path / "nope")
        assert Path.cwd().resolve() == tmp_path.resolve()
