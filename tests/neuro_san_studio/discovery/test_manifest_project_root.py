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

"""Tests for ManifestProjectRoot: the directory that contains a manifest's registries folder."""

from pathlib import Path

from pytest import MonkeyPatch

from neuro_san_studio.discovery.manifest_project_root import ManifestProjectRoot


class TestManifestProjectRoot:
    """The project root is the grandparent of a manifest that lives in a registries folder."""

    def test_manifest_in_registries_folder_yields_grandparent(self) -> None:
        """The Dockerfile shape: /app/registries/manifest.hocon belongs to /app."""
        assert ManifestProjectRoot("/app/registries/manifest.hocon").resolve() == "/app"

    def test_nested_registries_folder_counts(self) -> None:
        """Only the immediate parent has to be named registries."""
        assert ManifestProjectRoot("/app/sub/registries/overlay.hocon").resolve() == "/app/sub"

    def test_manifest_elsewhere_yields_none(self) -> None:
        """A scratch manifest outside any registries folder implies no project root."""
        assert ManifestProjectRoot("/tmp/scratch.hocon").resolve() is None

    def test_relative_path_resolves_against_cwd(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        """A relative manifest path is anchored to the current working directory first."""
        monkeypatch.chdir(tmp_path)
        root = ManifestProjectRoot("registries/manifest.hocon").resolve()
        assert root is not None
        assert Path(root).resolve() == tmp_path.resolve()
