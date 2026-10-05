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

"""Tests for the `ns new network` command."""

from pathlib import Path

import pytest

from neuro_san_studio.commands.new_network import NewNetworkCommand


class TestToClassName:
    """Unit tests for NewNetworkCommand._to_class_name."""

    def test_snake_case(self) -> None:
        assert NewNetworkCommand._to_class_name("my_network") == "MyNetwork"  # pylint: disable=protected-access

    def test_single_word(self) -> None:
        assert NewNetworkCommand._to_class_name("agent") == "Agent"  # pylint: disable=protected-access

    def test_kebab_case(self) -> None:
        assert NewNetworkCommand._to_class_name("my-network") == "MyNetwork"  # pylint: disable=protected-access

    def test_three_words(self) -> None:
        assert NewNetworkCommand._to_class_name("foo_bar_baz") == "FooBarBaz"  # pylint: disable=protected-access


class TestNewNetworkValidation:
    """Name validation tests."""

    def test_invalid_name_uppercase_returns_error(self, tmp_path: Path) -> None:
        result = NewNetworkCommand(name="MyNetwork", root_dir=str(tmp_path)).run()
        assert result == 1

    def test_invalid_name_leading_digit_returns_error(self, tmp_path: Path) -> None:
        result = NewNetworkCommand(name="1network", root_dir=str(tmp_path)).run()
        assert result == 1

    def test_invalid_name_spaces_returns_error(self, tmp_path: Path) -> None:
        result = NewNetworkCommand(name="my network", root_dir=str(tmp_path)).run()
        assert result == 1


class TestNewNetworkRun:
    """Integration tests for NewNetworkCommand.run()."""

    def _run(self, tmp_path: Path, name: str = "my_network") -> int:
        return NewNetworkCommand(name=name, root_dir=str(tmp_path)).run()

    def test_creates_network_hocon(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        hocon = tmp_path / "registries" / "my_network.hocon"
        assert hocon.is_file()

    def test_hocon_contains_class_name(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        text = (tmp_path / "registries" / "my_network.hocon").read_text()
        assert "MyNetwork" in text

    def test_hocon_contains_llm_config_include(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        text = (tmp_path / "registries" / "my_network.hocon").read_text()
        assert 'include "config/llm_config.hocon"' in text

    def test_hocon_contains_expertise_scoping_include(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        text = (tmp_path / "registries" / "my_network.hocon").read_text()
        assert 'include "registries/expertise_scoping_instructions.hocon"' in text

    def test_creates_sample_fixture(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        fixture = tmp_path / "tests" / "fixtures" / "my_network" / "sample.hocon"
        assert fixture.is_file()

    def test_fixture_references_correct_agent(self, tmp_path: Path) -> None:
        self._run(tmp_path)
        text = (tmp_path / "tests" / "fixtures" / "my_network" / "sample.hocon").read_text()
        assert '"agent": "my_network"' in text

    def test_updates_manifest_when_present(self, tmp_path: Path) -> None:
        registries = tmp_path / "registries"
        registries.mkdir()
        manifest = registries / "manifest.hocon"
        manifest.write_text('{\n    "music_nerd.hocon": true\n}\n', encoding="utf-8")

        self._run(tmp_path)

        text = manifest.read_text()
        assert '"my_network.hocon": true' in text

    def test_skips_manifest_update_when_entry_already_present(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        registries = tmp_path / "registries"
        registries.mkdir()
        manifest = registries / "manifest.hocon"
        manifest.write_text('{\n    "my_network.hocon": true\n}\n', encoding="utf-8")

        self._run(tmp_path)

        # Manifest should be unchanged
        assert manifest.read_text().count('"my_network.hocon"') == 1

    def test_warns_when_manifest_missing(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        self._run(tmp_path)
        out = capsys.readouterr().out
        assert "[warn]" in out

    def test_skips_existing_hocon(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        registries = tmp_path / "registries"
        registries.mkdir()
        hocon = registries / "my_network.hocon"
        hocon.write_text("DO NOT OVERWRITE\n", encoding="utf-8")

        self._run(tmp_path)

        assert hocon.read_text() == "DO NOT OVERWRITE\n"
        out = capsys.readouterr().out
        assert "[skip]" in out

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        assert self._run(tmp_path) == 0

    def test_idempotent_second_run(self, tmp_path: Path) -> None:
        registries = tmp_path / "registries"
        registries.mkdir()
        (registries / "manifest.hocon").write_text('{\n    "music_nerd.hocon": true\n}\n', encoding="utf-8")
        self._run(tmp_path)
        # Second run must not duplicate the manifest entry
        self._run(tmp_path)
        text = (registries / "manifest.hocon").read_text()
        assert text.count('"my_network.hocon"') == 1
