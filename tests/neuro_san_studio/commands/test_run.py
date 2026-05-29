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

import logging
import os
import sys
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pytest import LogCaptureFixture
from pytest import MonkeyPatch

from neuro_san_studio.commands import run as run_module
from neuro_san_studio.commands.run import NeuroSanRunner


class TestNeuroSanRunner:  # pylint: disable=too-many-public-methods
    """Tests for NeuroSanRunner"""

    @pytest.fixture(autouse=True)
    def _restore_root_logger(self):
        """Snapshot and restore the root logger around each test.

        ``_configure_logging`` mutates the global root logger (handlers + level)
        and opens a ``runner.log`` file handler, so restore the prior state and
        close any file handlers added during the test to avoid leaking config or
        descriptors into other tests.
        """
        root = logging.getLogger()
        saved_handlers = root.handlers[:]
        saved_level = root.level
        yield
        for handler in root.handlers[:]:
            if handler not in saved_handlers and isinstance(handler, logging.FileHandler):
                handler.close()
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)

    @staticmethod
    def _make_runner() -> NeuroSanRunner:
        """Construct a NeuroSanRunner without invoking its heavy __init__.

        ``__new__`` skips ``__init__``, so the logger that the real constructor
        sets up is attached here too: every method now emits through
        ``self._logger`` rather than ``print``, and would raise AttributeError
        without it.
        """
        runner = NeuroSanRunner.__new__(NeuroSanRunner)
        runner._logger = logging.getLogger(NeuroSanRunner.__name__)  # pylint: disable=protected-access
        return runner

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

    def test_reprompts_then_accepts_valid(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that invalid input triggers a re-prompt before a valid one succeeds.

        The re-prompt feedback is now logged at WARNING level (it used to print
        to stdout), so assert against the captured log instead of capsys.
        """
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input(["maybe", "y"]))
        with caplog.at_level(logging.WARNING, logger="NeuroSanRunner"):
            assert self._make_runner()._validate_yes_no_input("prompt: ") is True
        assert "Invalid input" in caplog.text

    def test_returns_false_after_max_attempts(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Test that exhausting all attempts with invalid input returns False."""
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input(["a", "b", "c"]))
        with caplog.at_level(logging.WARNING, logger="NeuroSanRunner"):
            assert self._make_runner()._validate_yes_no_input("prompt: ") is False
        assert "Too many invalid responses." in caplog.text

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
        """With no env var, fall back to <root>/neuro_san_studio/toolbox/toolbox_info.hocon if it exists."""
        monkeypatch.delenv("AGENT_TOOLBOX_INFO_FILE", raising=False)
        toolbox_dir = tmp_path / "neuro_san_studio" / "toolbox"
        toolbox_dir.mkdir(parents=True)
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

    def test_mcp_env_var_takes_precedence(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """Explicit MCP_SERVERS_INFO_FILE should be used verbatim, ignoring the filesystem."""
        monkeypatch.setenv("MCP_SERVERS_INFO_FILE", "/custom/path/mcp_info.hocon")
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        assert runner._resolve_mcp_info_file() == "/custom/path/mcp_info.hocon"

    def test_mcp_scaffolded_path_used_when_file_exists(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """With no env var, prefer <root>/mcp/mcp_info.hocon (what `init` scaffolds) over the bundled file."""
        monkeypatch.delenv("MCP_SERVERS_INFO_FILE", raising=False)
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        mcp_file = mcp_dir / "mcp_info.hocon"
        mcp_file.write_text("{}\n", encoding="utf-8")
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        assert runner._resolve_mcp_info_file() == str(mcp_file)

    def test_mcp_falls_back_to_bundled_when_no_env_and_no_scaffold(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """With no env var and no scaffolded file, fall back to the mcp_info.hocon shipped in the package."""
        monkeypatch.delenv("MCP_SERVERS_INFO_FILE", raising=False)
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        result = runner._resolve_mcp_info_file()
        assert os.path.isfile(result)
        assert result.endswith(os.path.join("neuro_san_studio", "mcp", "mcp_info.hocon"))

    def test_set_environment_variables_skips_empty_toolbox(
        self, monkeypatch: MonkeyPatch, tmp_path: Path, caplog: LogCaptureFixture
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
        }
        with caplog.at_level(logging.INFO, logger="NeuroSanRunner"):
            runner.set_environment_variables()
        assert "AGENT_TOOLBOX_INFO_FILE" not in os.environ
        assert "using built-in default toolbox" in caplog.text

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

    # ---- #994: output is routed through the logger, not print ----

    @staticmethod
    def _full_args(tmp_path: Path) -> dict[str, Any]:
        """Return a complete args dict suitable for set_environment_variables()."""
        return {
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

    def test_no_bare_print_calls_in_source(self) -> None:
        """Regression guard for #994: run.py must route output through the logger.

        A bare ``print(`` reintroduces the stdout bypass this issue removed.
        Asserting against the source keeps the guard robust even for code paths
        that are hard to exercise (server startup, signal handling).
        """
        source = Path(run_module.__file__).read_text(encoding="utf-8")
        assert "print(" not in source

    def test_resolve_log_level_maps_names(self) -> None:
        """_resolve_log_level maps names case-insensitively and defaults to INFO."""
        assert NeuroSanRunner._resolve_log_level("warning") == logging.WARNING
        assert NeuroSanRunner._resolve_log_level("DEBUG") == logging.DEBUG
        assert NeuroSanRunner._resolve_log_level("bogus") == logging.INFO

    def test_early_log_level_prefers_cli_flag(self, monkeypatch: MonkeyPatch) -> None:
        """--log-level on argv wins over the LOG_LEVEL env var."""
        monkeypatch.setenv("LOG_LEVEL", "error")
        monkeypatch.setattr(sys, "argv", ["ns", "run", "--log-level", "warning"])
        assert NeuroSanRunner._early_log_level() == "warning"

    def test_early_log_level_accepts_equals_form(self, monkeypatch: MonkeyPatch) -> None:
        """The --log-level=value form is parsed as well as the space-separated form."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.setattr(sys, "argv", ["ns", "run", "--log-level=debug"])
        assert NeuroSanRunner._early_log_level() == "debug"

    def test_early_log_level_falls_back_to_env(self, monkeypatch: MonkeyPatch) -> None:
        """Without a CLI flag, the LOG_LEVEL env var is used."""
        monkeypatch.setenv("LOG_LEVEL", "warning")
        monkeypatch.setattr(sys, "argv", ["ns", "run"])
        assert NeuroSanRunner._early_log_level() == "warning"

    def test_configure_logging_honors_log_level(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """Regression for #994: LOG_LEVEL=warning suppresses INFO startup chatter.

        The earlier bootstrap hard-coded INFO; this asserts the root level follows
        the requested level so info-level runner messages are dropped.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("LOG_LEVEL", "warning")
        monkeypatch.setattr(sys, "argv", ["ns", "run"])
        logging.getLogger().handlers.clear()
        self._make_runner()._configure_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_configure_logging_writes_runner_log(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """Regression for #994: early runner output is captured in logs/runner.log.

        Messages logged before the ProcessLogBridge attaches (which happens only
        on first process start) must still reach the runner log, not just the
        console.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("LOG_LEVEL", "info")
        monkeypatch.setattr(sys, "argv", ["ns", "run"])
        logging.getLogger().handlers.clear()
        runner = self._make_runner()
        runner._configure_logging()
        runner._logger.info("startup probe line")
        for handler in logging.getLogger().handlers:
            handler.flush()
        runner_log = tmp_path / "logs" / "runner.log"
        assert runner_log.is_file()
        assert "startup probe line" in runner_log.read_text(encoding="utf-8")

    def test_configure_logging_does_not_stack_handlers(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """When the root logger already has handlers, only the level is applied."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("LOG_LEVEL", "warning")
        monkeypatch.setattr(sys, "argv", ["ns", "run"])
        root = logging.getLogger()
        root.handlers.clear()
        sentinel = logging.NullHandler()
        root.addHandler(sentinel)
        self._make_runner()._configure_logging()
        assert root.handlers == [sentinel]
        assert root.level == logging.WARNING

    def test_apply_log_level_overrides_after_parse(self) -> None:
        """_apply_log_level updates the root logger to the resolved level (CLI override)."""
        self._make_runner()._apply_log_level("warning")
        assert logging.getLogger().level == logging.WARNING

    def test_apply_log_level_propagates_to_process_logger_plugin(self) -> None:
        """_apply_log_level forwards the resolved level to a plugin that supports it.

        Covers the default run path where a process-logger plugin (the
        ProcessLogBridge) is constructed before --log-level is parsed, so its
        console level must be updated afterwards or the override is lost.
        """
        recorded: list[str] = []
        runner = self._make_runner()
        runner.plugins = [SimpleNamespace(set_console_level=recorded.append)]
        runner._apply_log_level("warning")
        assert recorded == ["warning"]
        assert logging.getLogger().level == logging.WARNING

    def test_apply_log_level_skips_plugin_without_setter(self) -> None:
        """Plugins lacking set_console_level are skipped without error."""
        runner = self._make_runner()
        runner.plugins = [SimpleNamespace(name="no-logging-hook")]
        runner._apply_log_level("warning")  # must not raise
        assert logging.getLogger().level == logging.WARNING

    def test_process_log_bridge_plugin_honors_late_log_level(self, monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
        """End-to-end handoff: a real ProcessLogBridgePlugin adopts a level resolved after construction.

        Reproduces the reported failure path: the bridge is built with the
        pre-parse level ("info"), then the runner applies the resolved "warning"
        after argparse, and the bridge's console handler must follow.
        """
        # pylint: disable=import-outside-toplevel
        from neuro_san_studio.plugins.log_bridge.process_log_bridge_plugin import ProcessLogBridgePlugin

        monkeypatch.chdir(tmp_path)
        plugin = ProcessLogBridgePlugin(args={"logs_dir": str(tmp_path / "logs"), "log_level": "info"})
        assert plugin.log_bridge.rich_handler.level == logging.INFO
        runner = self._make_runner()
        runner.plugins = [plugin]
        runner._apply_log_level("warning")
        assert plugin.log_bridge.rich_handler.level == logging.WARNING

    def test_load_env_variables_logs_when_missing(self, tmp_path: Path, caplog: LogCaptureFixture) -> None:
        """With no .env present, the 'using defaults' notice is logged at INFO."""
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        with caplog.at_level(logging.INFO, logger="NeuroSanRunner"):
            runner.load_env_variables()
        assert "No .env file found" in caplog.text

    def test_load_env_variables_logs_when_found(
        self, monkeypatch: MonkeyPatch, tmp_path: Path, caplog: LogCaptureFixture
    ) -> None:
        """With a .env present, the runner logs that it loaded variables at INFO."""
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        (tmp_path / ".env").write_text("FOO=bar\n", encoding="utf-8")
        monkeypatch.setattr(run_module, "load_dotenv", lambda *_a, **_k: True)
        with caplog.at_level(logging.INFO, logger="NeuroSanRunner"):
            runner.load_env_variables()
        assert "Loaded environment variables from:" in caplog.text

    def test_set_environment_variables_logs_each_setting(
        self, monkeypatch: MonkeyPatch, tmp_path: Path, caplog: LogCaptureFixture
    ) -> None:
        """Exported env vars are announced through the logger at INFO."""
        monkeypatch.setattr(os, "environ", os.environ.copy())
        runner = self._make_runner()
        runner.root_dir = str(tmp_path)
        runner.args = self._full_args(tmp_path)
        with caplog.at_level(logging.INFO, logger="NeuroSanRunner"):
            runner.set_environment_variables()
        assert "AGENT_MANIFEST_FILE set to:" in caplog.text
        assert "LOG_LEVEL set to:" in caplog.text

    def test_signal_handler_logs_and_exits(self, caplog: LogCaptureFixture) -> None:
        """signal_handler logs the shutdown at INFO and exits with status 0."""
        runner = self._make_runner()
        runner.is_windows = False
        runner.server_process = None
        runner.nsflow_process = None
        runner.plugins = []
        with caplog.at_level(logging.INFO, logger="NeuroSanRunner"):
            with pytest.raises(SystemExit) as exc_info:
                runner.signal_handler(2, None)
        assert exc_info.value.code == 0
        assert "Termination signal received" in caplog.text

    def test_kill_processes_on_ports_logs(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """_kill_processes_on_ports announces each port through the logger.

        ``subprocess.run`` is stubbed to report no listening process, so no real
        signal is sent; we only assert the logging behavior.
        """
        runner = self._make_runner()
        runner.is_windows = False
        monkeypatch.setattr(run_module.subprocess, "run", lambda *_a, **_k: SimpleNamespace(stdout=""))
        with caplog.at_level(logging.INFO, logger="NeuroSanRunner"):
            runner._kill_processes_on_ports([4173])
        assert "Attempting to kill process on port 4173" in caplog.text
        assert "No process found on port 4173" in caplog.text

    def test_invalid_input_logged_at_warning_level(self, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture) -> None:
        """Invalid interactive input is logged at WARNING, not INFO."""
        monkeypatch.setattr(run_module, "timedinput", self._scripted_input(["bad", "yes"]))
        with caplog.at_level(logging.WARNING, logger="NeuroSanRunner"):
            assert self._make_runner()._validate_yes_no_input("prompt: ") is True
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Invalid input" in message for message in warning_messages)
