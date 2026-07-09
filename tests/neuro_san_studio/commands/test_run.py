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

"""Tests for NeuroSanRunner."""

import os
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from pytest import CaptureFixture
from pytest import MonkeyPatch

from neuro_san_studio.commands import run as run_module
from neuro_san_studio.commands.project_environment import ProjectEnvironment
from neuro_san_studio.commands.run import NeuroSanRunner


class TestNeuroSanRunner:
    """Tests for NeuroSanRunner"""

    @staticmethod
    def _make_runner() -> NeuroSanRunner:
        """Construct a NeuroSanRunner without invoking its heavy __init__."""
        return NeuroSanRunner.__new__(NeuroSanRunner)

    @staticmethod
    def _scripted_input(responses: Iterable[str]) -> Callable[..., str]:
        """Return a replacement for timedinput() that pops successive responses."""
        queue: list[str] = list(responses)

        def _input(_prompt: str = "", **_kwargs: Any) -> str:
            if not queue:
                raise AssertionError("timedinput() called more times than scripted responses")
            return queue.pop(0)

        return _input

    # pylint: disable=protected-access

    @pytest.mark.parametrize("response", ["yes", "y", "YES", "Y", "Yes", "  y  "])
    def test_returns_true_for_affirmative(self, monkeypatch: MonkeyPatch, response: str) -> None:
        """Test that any affirmative variant (case/whitespace) returns True."""
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input([response]))
        assert self._make_runner()._validate_yes_no_input("prompt: ") is True

    @pytest.mark.parametrize("response", ["no", "n", "NO", "N", "No", "  n  "])
    def test_returns_false_for_negative(self, monkeypatch: MonkeyPatch, response: str) -> None:
        """Test that any negative variant (case/whitespace) returns False."""
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input([response]))
        assert self._make_runner()._validate_yes_no_input("prompt: ") is False

    def test_reprompts_then_accepts_valid(self, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
        """Test that invalid input triggers a re-prompt before a valid one succeeds."""
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input(["maybe", "y"]))
        assert self._make_runner()._validate_yes_no_input("prompt: ") is True
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    def test_returns_false_after_max_attempts(self, monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]) -> None:
        """Test that exhausting all attempts with invalid input returns False."""
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input(["a", "b", "c"]))
        assert self._make_runner()._validate_yes_no_input("prompt: ") is False
        captured = capsys.readouterr()
        assert "Too many invalid responses." in captured.out

    def test_respects_custom_max_attempts(self, monkeypatch: MonkeyPatch) -> None:
        """Test that max_attempts controls the number of allowed retries."""
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input(["bad", "yes"]))
        assert self._make_runner()._validate_yes_no_input("prompt: ", max_attempts=2) is True

    def test_set_environment_variables_skips_empty_toolbox(
        self, monkeypatch: MonkeyPatch, tmp_path: Path, capsys: CaptureFixture[str]
    ) -> None:
        """set_environment_variables should not export AGENT_TOOLBOX_INFO_FILE when the arg is empty."""
        monkeypatch.setattr(os, "environ", os.environ.copy())
        monkeypatch.delenv("AGENT_TOOLBOX_INFO_FILE", raising=False)
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        runner.project_env = ProjectEnvironment(runner.root_dir)
        runner.args = {
            "agent_manifest_file": str(tmp_path / "manifest.hocon"),
            "agent_tool_path": str(tmp_path / "coded_tools"),
            "agent_toolbox_info_file": "",
            "mcp_servers_info_file": str(tmp_path / "mcp_info.hocon"),
            "server_connection": "http",
            "manifest_update_period_seconds": 5,
            "log_level": "info",
            "server_only": True,
            "client_only": False,
            "server_host": "localhost",
            "server_http_port": 8080,
            "thinking_file": str(tmp_path / "thinking.txt"),
            "thinking_dir": str(tmp_path / "thinking"),
        }
        runner.set_environment_variables()
        assert "AGENT_TOOLBOX_INFO_FILE" not in os.environ
        assert "using built-in default toolbox" in capsys.readouterr().out

    def test_set_environment_variables_exports_toolbox_when_present(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """set_environment_variables should export AGENT_TOOLBOX_INFO_FILE when the arg is set."""
        monkeypatch.setattr(os, "environ", os.environ.copy())
        monkeypatch.delenv("AGENT_TOOLBOX_INFO_FILE", raising=False)
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        runner.project_env = ProjectEnvironment(runner.root_dir)
        runner.args = {
            "agent_manifest_file": str(tmp_path / "manifest.hocon"),
            "agent_tool_path": str(tmp_path / "coded_tools"),
            "agent_toolbox_info_file": "/explicit/path/toolbox.hocon",
            "mcp_servers_info_file": str(tmp_path / "mcp_info.hocon"),
            "server_connection": "http",
            "manifest_update_period_seconds": 5,
            "log_level": "info",
            "server_only": True,
            "client_only": False,
            "server_host": "localhost",
            "server_http_port": 8080,
            "thinking_file": str(tmp_path / "thinking.txt"),
            "thinking_dir": str(tmp_path / "thinking"),
        }
        runner.set_environment_variables()
        assert os.environ["AGENT_TOOLBOX_INFO_FILE"] == "/explicit/path/toolbox.hocon"

    def test_passes_prompt_to_input(self, monkeypatch: MonkeyPatch) -> None:
        """Test that the supplied prompt string is forwarded to timedinput()."""
        seen_prompts: list[str] = []

        def _capturing_input(prompt: str = "", **_kwargs: Any) -> str:
            seen_prompts.append(prompt)
            return "y"

        monkeypatch.setattr(run_module, "timedinput", _capturing_input)
        self._make_runner()._validate_yes_no_input("Kill processes? ")
        assert seen_prompts == ["Kill processes? "]
