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

"""Tests for the `ns test` command."""

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from neuro_san_studio.commands.cli import NeuroSanStudioCli
from neuro_san_studio.commands.test import TestCommand


class TestBuildArgv:
    """Unit tests for TestCommand._build_argv."""

    @staticmethod
    def _marker_value(argv: list) -> str:
        """Return the value after the last -m flag in an argv list (skipping python -m pytest)."""
        # argv = [python, "-m", "pytest", ...flags..., "-m", "<marker>", ...]
        # We want the -m that is a pytest flag, not the one in "python -m pytest".
        # Search from index 3 (past python, -m, pytest) to find the pytest -m flag.
        idx = next(i for i in range(3, len(argv)) if argv[i] == "-m")
        return argv[idx + 1]

    def test_default_uses_unit_marker(self) -> None:
        """Default run excludes integration and smoke markers."""
        argv = TestCommand()._build_argv()  # pylint: disable=protected-access
        marker = self._marker_value(argv)
        assert "not integration" in marker
        assert "not smoke" in marker

    def test_integration_flag_uses_integration_marker(self) -> None:
        """--integration switches the marker to 'integration'."""
        argv = TestCommand(integration=True)._build_argv()  # pylint: disable=protected-access
        assert self._marker_value(argv) == "integration"

    def test_integration_flag_adds_s_flag(self) -> None:
        """--integration adds -s for live output (mirrors make test-integration)."""
        argv = TestCommand(integration=True)._build_argv()  # pylint: disable=protected-access
        assert "-s" in argv[3:]

    def test_verbose_flag_adds_verbose(self) -> None:
        """--verbose adds --verbose to the pytest invocation."""
        argv = TestCommand(verbose=True)._build_argv()  # pylint: disable=protected-access
        assert "--verbose" in argv

    def test_no_verbose_by_default(self) -> None:
        """--verbose is absent by default."""
        argv = TestCommand()._build_argv()  # pylint: disable=protected-access
        assert "--verbose" not in argv

    def test_default_path_is_tests(self) -> None:
        """Without a path argument the run targets 'tests'."""
        argv = TestCommand()._build_argv()  # pylint: disable=protected-access
        assert argv[-1] == "tests"

    def test_custom_path_is_forwarded(self) -> None:
        """A supplied path replaces the default 'tests' target."""
        argv = TestCommand(path="tests/neuro_san_studio/coded_tools/")._build_argv()  # pylint: disable=protected-access
        assert argv[-1] == "tests/neuro_san_studio/coded_tools/"

    def test_extra_args_are_appended(self) -> None:
        """Extra pytest arguments are appended after the path."""
        argv = TestCommand(extra_args=["-k", "test_my_case", "--tb=short"])._build_argv()  # pylint: disable=protected-access
        assert "-k" in argv
        assert "test_my_case" in argv
        assert "--tb=short" in argv

    def test_argv_starts_with_python_m_pytest(self) -> None:
        """The argv always starts with the current interpreter and -m pytest."""
        argv = TestCommand()._build_argv()  # pylint: disable=protected-access
        assert argv[0] == sys.executable
        assert argv[1] == "-m"
        assert argv[2] == "pytest"


class TestRun:
    """Tests for TestCommand.run()."""

    def test_returns_subprocess_exit_code_on_success(self, tmp_path: Path) -> None:
        """run() propagates pytest's exit code of 0."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("neuro_san_studio.commands.test.subprocess.run", return_value=mock_result) as mock_run:
            with patch("neuro_san_studio.commands.test.ProjectEnvironment") as mock_env_cls:
                mock_env_cls.return_value.apply = MagicMock()
                code = TestCommand(root_dir=str(tmp_path)).run()
        assert code == 0
        mock_run.assert_called_once()

    def test_returns_subprocess_exit_code_on_failure(self, tmp_path: Path) -> None:
        """run() propagates pytest's non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("neuro_san_studio.commands.test.subprocess.run", return_value=mock_result):
            with patch("neuro_san_studio.commands.test.ProjectEnvironment") as mock_env_cls:
                mock_env_cls.return_value.apply = MagicMock()
                code = TestCommand(root_dir=str(tmp_path)).run()
        assert code == 1

    def test_applies_project_environment(self, tmp_path: Path) -> None:
        """run() calls ProjectEnvironment.apply() to set agent env vars."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("neuro_san_studio.commands.test.subprocess.run", return_value=mock_result):
            with patch("neuro_san_studio.commands.test.ProjectEnvironment") as mock_env_cls:
                mock_apply = MagicMock()
                mock_env_cls.return_value.apply = mock_apply
                TestCommand(root_dir=str(tmp_path)).run()
        mock_apply.assert_called_once()

    def test_runs_in_root_dir(self, tmp_path: Path) -> None:
        """run() launches pytest with cwd=root_dir."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("neuro_san_studio.commands.test.subprocess.run", return_value=mock_result) as mock_run:
            with patch("neuro_san_studio.commands.test.ProjectEnvironment") as mock_env_cls:
                mock_env_cls.return_value.apply = MagicMock()
                TestCommand(root_dir=str(tmp_path)).run()
        _, kwargs = mock_run.call_args
        assert kwargs.get("cwd") == str(tmp_path)

    def test_check_false_prevents_exception_on_nonzero(self, tmp_path: Path) -> None:
        """subprocess.run is called with check=False so pytest failures don't raise."""
        mock_result = MagicMock()
        mock_result.returncode = 5
        with patch("neuro_san_studio.commands.test.subprocess.run", return_value=mock_result) as mock_run:
            with patch("neuro_san_studio.commands.test.ProjectEnvironment") as mock_env_cls:
                mock_env_cls.return_value.apply = MagicMock()
                TestCommand(root_dir=str(tmp_path)).run()
        _, kwargs = mock_run.call_args
        assert kwargs.get("check") is False


class TestCliRegistration:
    """Smoke-test that `ns test --help` is wired up in the CLI."""

    @staticmethod
    def _plain_output(output: str) -> str:
        """Strip ANSI escape codes from Rich/Typer CLI output."""
        return re.sub(r"\x1b\[[0-9;]*m", "", output)

    def test_test_subcommand_appears_in_help(self) -> None:
        """The 'test' subcommand is registered and visible in the CLI."""
        runner = CliRunner()
        result = runner.invoke(NeuroSanStudioCli.app, ["--help"])
        assert result.exit_code in (0, 2)
        assert "test" in self._plain_output(result.output)

    def test_test_help_shows_integration_option(self) -> None:
        """The 'ns test --help' output lists the --integration option."""
        runner = CliRunner()
        result = runner.invoke(NeuroSanStudioCli.app, ["test", "--help"])
        assert result.exit_code in (0, 2)
        assert "--integration" in self._plain_output(result.output)

    @pytest.mark.parametrize("flag", ["--verbose"])
    def test_test_help_shows_flags(self, flag: str) -> None:
        """The 'ns test --help' output lists the expected flags."""
        runner = CliRunner()
        result = runner.invoke(NeuroSanStudioCli.app, ["test", "--help"])
        assert flag in self._plain_output(result.output)
