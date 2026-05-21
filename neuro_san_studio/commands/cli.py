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

"""Typer CLI dispatcher for the neuro-san-studio package."""

import sys
from typing import Any
from typing import List
from typing import Optional
from typing import Tuple

import typer

from neuro_san_studio.commands.run import NeuroSanRunner


class NeuroSanStudioCli:  # pylint: disable=too-few-public-methods
    """Typer CLI dispatcher: routes `neuro-san-studio <subcommand>` invocations."""

    app = typer.Typer(
        name="neuro-san-studio",
        help="Neuro SAN Studio CLI.",
        no_args_is_help=True,
        add_completion=False,
    )

    @staticmethod
    def _invoke_run(extra_args: List[str]) -> None:
        """Run the server, exposing `extra_args` to NeuroSanRunner.parse_args() via sys.argv."""
        sys.argv = [sys.argv[0], *extra_args]
        NeuroSanRunner().run()

    @staticmethod
    def _build_run_forward_args(valued: List[Tuple[str, Any]], booleans: List[Tuple[str, bool]]) -> List[str]:
        """Build the forwarded-args list from Typer-parsed valued and boolean flags."""
        forwarded: List[str] = []
        for flag, value in valued:
            if value is not None:
                forwarded.extend([flag, str(value)])
        for flag, value in booleans:
            if value:
                forwarded.append(flag)
        return forwarded

    @staticmethod
    @app.command(
        "run",
        help="Start the Neuro SAN server and client (default).",
        context_settings={
            # Forward unknown options (e.g. plugin-injected flags via
            # plugin.update_parser_args) through to NeuroSanRunner's argparse layer.
            "allow_extra_args": True,
            "ignore_unknown_options": True,
        },
    )
    def _run_command(  # pylint: disable=too-many-arguments
        ctx: typer.Context,
        *,
        server_host: Optional[str] = typer.Option(
            None, "--server-host", help="Host address for the Neuro SAN server."
        ),
        server_http_port: Optional[int] = typer.Option(
            None, "--server-http-port", help="Port number for the Neuro SAN server http endpoint."
        ),
        nsflow_port: Optional[int] = typer.Option(None, "--nsflow-port", help="Port number for the nsflow client."),
        log_level: Optional[str] = typer.Option(None, "--log-level", help="Log level for all processes."),
        thinking_file: Optional[str] = typer.Option(None, "--thinking-file", help="Path to the agent thinking file."),
        client_only: bool = typer.Option(
            False, "--client-only", help="Run only the nsflow client without the NeuroSan server."
        ),
        server_only: bool = typer.Option(
            False, "--server-only", help="Run only the NeuroSan server without the default nsflow client."
        ),
    ) -> None:
        """Forward declared flags + any plugin extras to NeuroSanRunner's argparse layer.

        Typer parses the known flags so they appear in `--help` with Typer styling.
        Only user-supplied values are forwarded; unset options stay `None` so the
        runner's env-var-driven defaults still apply. Plugin-injected flags arrive
        via `ctx.args` and are forwarded verbatim.
        """
        forwarded = NeuroSanStudioCli._build_run_forward_args(
            [
                ("--server-host", server_host),
                ("--server-http-port", server_http_port),
                ("--nsflow-port", nsflow_port),
                ("--log-level", log_level),
                ("--thinking-file", thinking_file),
            ],
            [
                ("--client-only", client_only),
                ("--server-only", server_only),
            ],
        )
        forwarded.extend(ctx.args)
        NeuroSanStudioCli._invoke_run(forwarded)

    @staticmethod
    @app.command("init", help="Scaffold a starter project in the current directory.")
    def _init_command(
        providers: Optional[str] = typer.Option(
            None,
            "--providers",
            help="Comma-separated providers to enable (openai,anthropic,google). Skips the interactive prompt.",
        ),
    ) -> None:
        """Scaffold a starter neuro-san-studio project."""
        from neuro_san_studio.commands.init import InitCommand  # pylint: disable=import-outside-toplevel

        InitCommand(providers_arg=providers).run()

    @staticmethod
    @app.command("check-llm-keys", help="Validate LLM API keys and other critical environment variables.")
    def _check_llm_keys_command(
        tier: int = typer.Option(
            3,
            "--tier",
            min=1,
            max=3,
            help="Validation tier: 1=placeholder check, 2=format check, 3=live API call.",
        ),
    ) -> None:
        """Run the LLM-key validation command and propagate its exit code."""
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio.commands.check_llm_keys import CheckLlmKeysCommand

        raise typer.Exit(code=CheckLlmKeysCommand(tier=tier).run())

    @staticmethod
    @app.command("check-config", help="Validate LLM configurations in a HOCON file.")
    def _check_config_command(
        hocon_path: Optional[str] = typer.Option(
            None,
            "--hocon-path",
            help="Path to the HOCON file to validate. Defaults to config/llm_config.hocon.",
        ),
    ) -> None:
        """Run the HOCON LLM-config validation and propagate its exit code."""
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio.commands.check_config import CheckConfigCommand

        raise typer.Exit(code=CheckConfigCommand(hocon_path=hocon_path).run())


def main() -> None:
    """Entry point for the `neuro-san-studio` console script."""
    # Typer/click exit with SystemExit(0) on success; let clean exits return normally
    # so main() can be driven from tests and embedded callers.
    try:
        NeuroSanStudioCli.app()
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise


if __name__ == "__main__":
    main()
