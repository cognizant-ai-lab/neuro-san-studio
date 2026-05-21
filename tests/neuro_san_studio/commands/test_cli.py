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

"""Tests for the Typer CLI dispatcher and `main()` entry point."""

import sys

import pytest
from pytest import MonkeyPatch

from neuro_san_studio.commands import cli as cli_module
from neuro_san_studio.commands import init as init_module
from neuro_san_studio.commands.cli import main


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

        monkeypatch.setattr(cli_module, "NeuroSanRunner", FakeRunner)
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

        monkeypatch.setattr(cli_module, "NeuroSanRunner", ExplodingRunner)
        monkeypatch.setattr(sys, "argv", ["neuro-san-studio", "run"])
        with pytest.raises(RuntimeError, match="boom"):
            main()
