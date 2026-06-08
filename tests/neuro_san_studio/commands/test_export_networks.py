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

"""Tests for ExportCommand — interactive picker behavior and the orchestration around it."""

from pathlib import Path
from typing import Optional

import pytest

from neuro_san_studio.commands.export_networks import ExportCommand


def _scaffold_project(project_dir: Path) -> None:
    """Lay out a minimal manifest-driven project with two networks across two groups."""
    registries = project_dir / "registries"
    (registries / "basic").mkdir(parents=True)
    (registries / "industry").mkdir(parents=True)
    (registries / "manifest.hocon").write_text(
        '{\n    "basic/music_nerd.hocon": true,\n    "industry/airline_policy.hocon": true,\n}\n'
    )
    (registries / "basic" / "music_nerd.hocon").write_text(
        '{\n    "tools": [{"name": "frontman", "class": "openai"}]\n}\n'
    )
    (registries / "industry" / "airline_policy.hocon").write_text(
        '{\n    "tools": [{"name": "frontman", "class": "openai"}]\n}\n'
    )


class _StubApplication:  # pylint: disable=too-few-public-methods
    """Just enough of questionary's application surface for the Esc-binding helper to attach."""

    def __init__(self) -> None:
        # pylint: disable-next=import-outside-toplevel
        from prompt_toolkit.key_binding import KeyBindings

        self.key_bindings = KeyBindings()


class _StubQuestion:  # pylint: disable=too-few-public-methods
    """Stand-in for ``questionary.select(...)`` — captures the choices and returns a preset value."""

    def __init__(self, return_value: Optional[str], capture: dict) -> None:
        self._return_value = return_value
        self._capture = capture
        self.application = _StubApplication()

    def ask(self) -> Optional[str]:
        """Return the preset value, mimicking questionary's blocking ask()."""
        return self._return_value


class TestInteractivePicker:
    """`ns export` with no positional arg drops into a single-select picker over the project manifest."""

    def test_picker_returns_chosen_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The user's selection is returned verbatim as a registries-relative path."""
        _scaffold_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        captured: dict = {}

        def fake_select(prompt, *, choices):
            captured["prompt"] = prompt
            captured["choices"] = choices
            return _StubQuestion("basic/music_nerd.hocon", captured)

        monkeypatch.setattr("neuro_san_studio.commands.export_networks.questionary.select", fake_select)

        cmd = ExportCommand()
        # pylint: disable-next=protected-access
        result = cmd._prompt_for_network()
        assert result == "basic/music_nerd.hocon"
        assert "network" in captured["prompt"].lower()

    def test_picker_groups_networks_with_separators(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each group becomes a separator row followed by Choices for its networks."""
        _scaffold_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        captured: dict = {}

        def fake_select(_prompt, *, choices):
            captured["choices"] = choices
            return _StubQuestion(None, captured)

        monkeypatch.setattr("neuro_san_studio.commands.export_networks.questionary.select", fake_select)

        # pylint: disable-next=protected-access
        ExportCommand()._prompt_for_network()

        # Sanity: group headers came through (uppercased), and both networks are pickable.
        rendered_titles = [getattr(c, "title", "") for c in captured["choices"]]
        assert any("BASIC" in t for t in rendered_titles)
        assert any("INDUSTRY" in t for t in rendered_titles)
        values = [getattr(c, "value", None) for c in captured["choices"] if getattr(c, "value", None)]
        assert "basic/music_nerd.hocon" in values
        assert "industry/airline_policy.hocon" in values

    def test_picker_returns_none_when_user_aborts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ctrl-C / Esc → questionary returns None → we return None (caller treats as cancelled)."""
        _scaffold_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        def fake_select(*_args, **_kwargs):
            return _StubQuestion(None, {})

        monkeypatch.setattr("neuro_san_studio.commands.export_networks.questionary.select", fake_select)
        # pylint: disable-next=protected-access
        assert ExportCommand()._prompt_for_network() is None

    def test_picker_handles_keyboard_interrupt(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A raised KeyboardInterrupt at .ask() is caught and surfaces as None, not a stack trace."""
        _scaffold_project(tmp_path)
        monkeypatch.chdir(tmp_path)

        class _RaisingQuestion:  # pylint: disable=too-few-public-methods
            """Stub questionary object whose ask() raises KeyboardInterrupt."""

            def __init__(self) -> None:
                self.application = _StubApplication()

            def ask(self):
                """Simulate Ctrl-C at the prompt."""
                raise KeyboardInterrupt()

        monkeypatch.setattr(
            "neuro_san_studio.commands.export_networks.questionary.select",
            lambda *_a, **_kw: _RaisingQuestion(),
        )
        # pylint: disable-next=protected-access
        assert ExportCommand()._prompt_for_network() is None

    def test_picker_returns_none_for_empty_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A project with an empty manifest prints a hint and returns None instead of opening a blank picker."""
        (tmp_path / "registries").mkdir()
        (tmp_path / "registries" / "manifest.hocon").write_text("{}\n")
        monkeypatch.chdir(tmp_path)

        called = {"select": False}

        def fake_select(*_a, **_kw):
            called["select"] = True
            return _StubQuestion(None, {})

        monkeypatch.setattr("neuro_san_studio.commands.export_networks.questionary.select", fake_select)
        # pylint: disable-next=protected-access
        assert ExportCommand()._prompt_for_network() is None
        assert called["select"] is False
        assert "No networks declared" in capsys.readouterr().out


class TestRunCancellation:  # pylint: disable=too-few-public-methods
    """Top-level `run()` should swallow a cancelled picker and exit cleanly."""

    def test_run_exits_clean_when_picker_cancelled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Cancelled picker → printed message, no SystemExit, no exporter call."""
        _scaffold_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "neuro_san_studio.commands.export_networks.ExportCommand._prompt_for_network",
            lambda self: None,
        )

        # If the exporter ran, it'd succeed silently — assert it never gets a chance.
        called = {"export": 0}

        def boom(*_a, **_kw):
            called["export"] += 1
            raise AssertionError("exporter must not run when picker is cancelled")

        monkeypatch.setattr("neuro_san_studio.commands.export_networks.AgentNetworkExporter.export", boom)

        ExportCommand().run()
        assert called["export"] == 0
        assert "No network selected" in capsys.readouterr().out
