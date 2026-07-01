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
from neuro_san_studio.commands import import_networks as import_networks_module
from neuro_san_studio.commands import init as init_module
from neuro_san_studio.commands import internalize_agents as internalize_agents_module
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
        # typer <0.26 exits 0 after printing help (swallowed by main()); typer >=0.26
        # raises NoArgsIsHelpError -> SystemExit(2). Both are clean help-display outcomes.
        try:
            main()
        except SystemExit as exc:
            assert exc.code in (0, 2)
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

    def test_main_with_import_positional_passes_tokens_and_force(self, monkeypatch: MonkeyPatch) -> None:
        """`neuro-san-studio import a.hocon b.zip --force` forwards space-separated tokens + force."""
        captured: list = []

        class FakeImport:  # pylint: disable=too-few-public-methods
            """Stand-in for ImportCommand that records constructor kwargs."""

            def __init__(
                self,
                networks_arg: list | None = None,
                force: bool = False,
            ) -> None:
                captured.append({"networks_arg": networks_arg, "force": force})

            def run(self) -> None:
                """No-op."""

        monkeypatch.setattr(import_networks_module, "ImportCommand", FakeImport)
        monkeypatch.setattr(sys, "argv", ["neuro-san-studio", "import", "a.hocon", "b.zip", "--force"])
        main()
        assert captured == [{"networks_arg": ["a.hocon", "b.zip"], "force": True}]

    def test_main_with_internalize_agents_passes_args_through(self, monkeypatch: MonkeyPatch) -> None:
        """`internalize-agents <in> -o <out> --search-paths <p>` forwards all three kwargs."""
        captured: list[dict] = []

        class FakeInternalize:  # pylint: disable=too-few-public-methods
            """Stand-in for InternalizeAgentsCommand that records constructor kwargs."""

            def __init__(
                self,
                input_path: str,
                output_path: str,
                search_paths: str | None = None,
            ) -> None:
                captured.append(
                    {
                        "input_path": input_path,
                        "output_path": output_path,
                        "search_paths": search_paths,
                    }
                )

            def run(self) -> int:
                """Return success so main() does not raise."""
                return 0

        monkeypatch.setattr(internalize_agents_module, "InternalizeAgentsCommand", FakeInternalize)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "neuro-san-studio",
                "internalize-agents",
                "in.hocon",
                "--output",
                "out.hocon",
                "--search-paths",
                "registries:other",
            ],
        )
        main()
        assert captured == [
            {
                "input_path": "in.hocon",
                "output_path": "out.hocon",
                "search_paths": "registries:other",
            }
        ]

    def test_main_with_internalize_agents_propagates_exit_code(self, monkeypatch: MonkeyPatch) -> None:
        """A non-zero return from InternalizeAgentsCommand.run() should reach SystemExit."""

        class FakeInternalize:  # pylint: disable=too-few-public-methods
            """Stand-in whose run() returns a failure exit code."""

            def __init__(self, **_kwargs) -> None:
                """Accept any kwargs; we only care about the exit code."""

            def run(self) -> int:
                """Return a non-zero exit code to verify it propagates through main()."""
                return 1

        monkeypatch.setattr(internalize_agents_module, "InternalizeAgentsCommand", FakeInternalize)
        monkeypatch.setattr(
            sys,
            "argv",
            ["neuro-san-studio", "internalize-agents", "in.hocon", "-o", "out.hocon"],
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

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

    @pytest.mark.parametrize("flag", ["--version", "-V"])
    def test_version_flag_prints_version_and_exits(
        self, flag: str, monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`ns --version` / `-V` prints the resolved version and exits without starting the server."""
        call_order = self._install_fake_runner(monkeypatch)
        monkeypatch.setattr(
            "neuro_san_studio.utils.version.resolve_version",
            lambda: ("1.2.3", "installed"),
        )
        monkeypatch.setattr(sys, "argv", ["neuro-san-studio", flag])
        # The eager callback raises typer.Exit(0); main() swallows clean exits.
        main()
        assert "neuro-san-studio 1.2.3 (installed)" in capsys.readouterr().out
        assert not call_order
