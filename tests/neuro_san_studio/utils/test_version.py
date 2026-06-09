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

from importlib.metadata import PackageNotFoundError

import pytest

from neuro_san_studio.utils import version as version_module
from neuro_san_studio.utils.version import studio_version


class TestStudioVersion:
    """Resolving the installed neuro-san-studio version."""

    def test_returns_installed_distribution_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The resolved string is whatever the distribution metadata reports."""
        monkeypatch.setattr(version_module, "library_version", lambda _name: "1.2.3")
        assert studio_version() == "1.2.3"

    def test_resolves_the_studio_distribution_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The resolver looks up the published distribution name, not the import package."""
        seen: dict = {}

        def fake_version(name: str) -> str:
            seen["name"] = name
            return "9.9.9"

        monkeypatch.setattr(version_module, "library_version", fake_version)
        studio_version()
        assert seen["name"] == "neuro-san-studio"

    def test_falls_back_to_unknown_when_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing distribution surfaces 'unknown' rather than raising."""

        def boom(_name: str) -> str:
            raise PackageNotFoundError("neuro-san-studio")

        monkeypatch.setattr(version_module, "library_version", boom)
        assert studio_version() == "unknown"
