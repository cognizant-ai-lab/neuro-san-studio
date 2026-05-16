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
import sys
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from pytest import CaptureFixture
from pytest import MonkeyPatch

from neuro_san_studio.commands import init as init_module
from neuro_san_studio.commands import run as run_module
from neuro_san_studio.commands.run import NeuroSanRunner
from neuro_san_studio.commands.run import main


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

    def test_toolbox_env_var_takes_precedence(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """Explicit AGENT_TOOLBOX_INFO_FILE should be used verbatim, ignoring the filesystem."""
        monkeypatch.setenv("AGENT_TOOLBOX_INFO_FILE", "/custom/path/toolbox.hocon")
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        assert runner._resolve_toolbox_info_file() == "/custom/path/toolbox.hocon"

    def test_toolbox_default_path_used_when_file_exists(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """With no env var, fall back to <root>/toolbox/toolbox_info.hocon if it exists."""
        monkeypatch.delenv("AGENT_TOOLBOX_INFO_FILE", raising=False)
        toolbox_dir = tmp_path / "toolbox"
        toolbox_dir.mkdir()
        toolbox_file = toolbox_dir / "toolbox_info.hocon"
        toolbox_file.write_text("{}\n", encoding="utf-8")
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        assert runner._resolve_toolbox_info_file() == str(toolbox_file)

    def test_toolbox_unset_when_no_env_and_no_file(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """With no env var and no file on disk, return "" so the env var stays unset."""
        monkeypatch.delenv("AGENT_TOOLBOX_INFO_FILE", raising=False)
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        assert runner._resolve_toolbox_info_file() == ""

    def test_set_environment_variables_skips_empty_toolbox(
        self, monkeypatch: MonkeyPatch, tmp_path: Path, capsys: CaptureFixture[str]
    ) -> None:
        """set_environment_variables should not export AGENT_TOOLBOX_INFO_FILE when the arg is empty."""
        monkeypatch.setattr(os, "environ", os.environ.copy())
        monkeypatch.delenv("AGENT_TOOLBOX_INFO_FILE", raising=False)
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
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
            "use_flask_web_client": False,
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
            "use_flask_web_client": False,
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


class TestMainEntryPoint:
    """Tests for the `main()` console script entry point."""

    @staticmethod
    def _install_fake_runner(monkeypatch: MonkeyPatch) -> list[str]:
        """Replace NeuroSanRunner with a recording stand-in and return the call log."""
        call_order: list[str] = []

        class FakeRunner:  # pylint: disable=too-few-public-methods
            """Stand-in for NeuroSanRunner that records method calls."""

            def __init__(self) -> None:
                call_order.append("init")

            def run(self) -> None:
                """Record that run() was invoked."""
                call_order.append("run")

        monkeypatch.setattr(run_module, "NeuroSanRunner", FakeRunner)
        return call_order

    def test_main_with_no_args_shows_help(self, monkeypatch: MonkeyPatch) -> None:
        """Bare `neuro-san-studio` should show help and exit cleanly without starting the server."""
        call_order = self._install_fake_runner(monkeypatch)
        monkeypatch.setattr(sys, "argv", ["neuro-san-studio"])
        # Typer exits with code 0 after printing help; main() swallows that for clean exits.
        main()
        assert not call_order

    def test_main_with_run_subcommand_runs_server(self, monkeypatch: MonkeyPatch) -> None:
        """Explicit `neuro-san-studio run` should start the server."""
        call_order = self._install_fake_runner(monkeypatch)
        monkeypatch.setattr(sys, "argv", ["neuro-san-studio", "run"])
        main()
        assert call_order == ["init", "run"]

    def test_main_with_init_subcommand_invokes_init(self, monkeypatch: MonkeyPatch) -> None:
        """`neuro-san-studio init` should invoke InitCommand and NOT NeuroSanRunner."""
        runner_call_order = self._install_fake_runner(monkeypatch)
        init_calls: list[tuple[str | None]] = []

        class FakeInit:  # pylint: disable=too-few-public-methods
            """Stand-in for InitCommand that records the providers_arg it received."""

            def __init__(self, providers_arg: str | None = None) -> None:
                init_calls.append((providers_arg,))

            def run(self) -> None:
                """Record that init.run() was invoked."""
                init_calls.append(("run",))

        monkeypatch.setattr(init_module, "InitCommand", FakeInit)
        monkeypatch.setattr(sys, "argv", ["neuro-san-studio", "init", "--providers", "openai,anthropic"])
        main()
        assert not runner_call_order
        assert init_calls == [("openai,anthropic",), ("run",)]

    def test_main_propagates_runner_exceptions(self, monkeypatch: MonkeyPatch) -> None:
        """Exceptions from NeuroSanRunner().run() should bubble up to the caller."""

        class ExplodingRunner:  # pylint: disable=too-few-public-methods
            """Runner whose run() raises, to verify main() does not swallow errors."""

            def run(self) -> None:
                """Raise to simulate a runtime failure."""
                raise RuntimeError("boom")

        monkeypatch.setattr(run_module, "NeuroSanRunner", ExplodingRunner)
        monkeypatch.setattr(sys, "argv", ["neuro-san-studio", "run"])
        with pytest.raises(RuntimeError, match="boom"):
            main()
