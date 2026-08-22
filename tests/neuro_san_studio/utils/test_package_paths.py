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

"""Tests for PackagePaths.installed_library_root."""

import os

import pytest

from neuro_san_studio.utils.package_paths import PackagePaths


class TestInstalledLibraryRoot:  # pylint: disable=too-few-public-methods
    """Verify the helper resolves to the installed library, not the user's project."""

    def test_returns_library_root_even_when_cwd_has_shadow_registries(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A registries/ in cwd must not shadow the installed library's registries/.

        This is the regression case for the original bug: ``registries`` is a PEP 420
        namespace package, so ``import registries`` from a project that has its own
        ``registries/`` (e.g. just after ``ns init``) would resolve __path__[0] to
        the user's directory and make ``ns import`` think there is nothing to import.
        """
        shadow_registries = tmp_path / "registries"
        shadow_registries.mkdir()
        (shadow_registries / "manifest.hocon").write_text("{ fake_local_only.hocon = true }\n")
        monkeypatch.chdir(tmp_path)

        resolved = PackagePaths.installed_library_root()

        assert resolved != str(tmp_path)
        manifest = os.path.join(resolved, "registries", "manifest.hocon")
        assert os.path.exists(manifest)
        with open(manifest, encoding="utf-8") as fh:
            contents = fh.read()
        assert "basic/manifest.hocon" in contents
