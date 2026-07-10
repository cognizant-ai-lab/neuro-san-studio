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

from typing import List
from typing import Optional

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
    def _version_callback(value: bool) -> bool:
        """Print the neuro-san-studio version (and where it resolved from) and exit."""
        if value:
            # pylint: disable-next=import-outside-toplevel
            from neuro_san_studio.utils.version import resolve_version

            version, source = resolve_version()
            typer.echo(f"neuro-san-studio {version} ({source})")
            raise typer.Exit()
        return value

    @staticmethod
    @app.callback()
    def _main(
        _version: bool = typer.Option(
            False,
            "--version",
            "-V",
            help="Show the installed neuro-san-studio version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ) -> None:
        """Neuro SAN Studio CLI."""

    @staticmethod
    def _validate_run_flags(overrides: dict) -> None:
        """Reject mutually-exclusive run-flag combinations before starting anything.

        Only user-supplied flags are present in ``overrides`` (booleans appear only when true),
        so membership tests double as "did the user pass this flag?".
        """
        client_only = "client_only" in overrides
        server_only = "server_only" in overrides
        if client_only and server_only:
            raise typer.BadParameter("You cannot specify both --client-only and --server-only at the same time.")
        if client_only and ("server_host" in overrides or "server_http_port" in overrides):
            raise typer.BadParameter(
                "You cannot specify --server-host or --server-http-port when using --client-only mode."
            )
        if server_only and "nsflow_port" in overrides:
            raise typer.BadParameter("You cannot specify --nsflow-port when using --server-only mode.")

    @staticmethod
    @app.command(
        "run",
        help="Start the Neuro SAN server and client (default).",
        context_settings={
            # Tolerate unknown options (e.g. plugin-injected flags) without erroring; they are
            # collected in ctx.args and handed to the runner. Made Typer-native in a follow-up.
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
        """Pass Typer-parsed run flags straight to NeuroSanRunner (single CLI framework: Typer).

        Only user-supplied flags become cli_overrides, so unset options keep the runner's
        env-var-driven defaults. Unknown/plugin flags arrive via ctx.args and are forwarded
        verbatim for the runner to handle.
        """
        # Map each self.args key to the flag the user supplied. Valued flags default to None and
        # booleans to False when unset; forwarding only truthy/non-None values means unset flags
        # keep the runner's env-var-driven defaults.
        run_flags: dict = {
            "server_host": server_host,
            "server_http_port": server_http_port,
            "nsflow_port": nsflow_port,
            "log_level": log_level,
            "thinking_file": thinking_file,
            "client_only": client_only,
            "server_only": server_only,
        }
        overrides = {key: value for key, value in run_flags.items() if value not in (None, False)}

        NeuroSanStudioCli._validate_run_flags(overrides)
        NeuroSanRunner(cli_overrides=overrides, extra_args=list(ctx.args)).run()

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
    @app.command("import", help="Import agent networks into existing project.")
    def _import_command(
        networks: Optional[List[str]] = typer.Argument(
            None,
            help=(
                "Space-separated group names, network names, or 'all'. "
                "Paths ending in .hocon or .zip are imported as local files "
                "(one or more); don't mix files with registry names. "
                "Omit for interactive mode."
            ),
        ),
        force: bool = typer.Option(
            False,
            "--force",
            help="Overwrite existing files in the target project.",
        ),
    ) -> None:
        """Import agent networks into an existing neuro-san-studio project."""
        from neuro_san_studio.commands.import_networks import ImportCommand  # pylint: disable=import-outside-toplevel

        ImportCommand(networks_arg=networks, force=force).run()

    @staticmethod
    @app.command("export", help="Export an agent network from the current project into a shareable file.")
    def _export_command(
        network: Optional[str] = typer.Argument(
            None,
            help="Network name (e.g. 'music_nerd') or path under registries/ (e.g. 'basic/music_nerd').",
        ),
        output: Optional[str] = typer.Option(
            None,
            "--output",
            "-o",
            help="Output file path. Defaults to '<network>.hocon' (no deps) or '<network>.zip' (deps).",
        ),
    ) -> None:
        """Bundle a network from the current project for sharing with another project."""
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio.commands.export_networks import ExportCommand

        ExportCommand(network=network, output=output).run()

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

    @staticmethod
    @app.command(
        "chat",
        help=(
            "Chat with an agent network directly (without starting nsflow).\n\n"
            "Pass the agent name as AGENT, e.g. ns chat music_nerd"
        ),
        no_args_is_help=True,
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
        },
    )
    def _chat_command(  # pylint: disable=too-many-arguments
        ctx: typer.Context,
        *,
        connection: str = typer.Option(
            "direct",
            "--connection",
            help="Connection type: 'direct' (library call, default), 'http', or 'https'.",
        ),
        host: Optional[str] = typer.Option(
            None,
            "--host",
            help="Hostname of the neuro-san server (for http/https connections).",
        ),
        port: Optional[int] = typer.Option(
            None,
            "--port",
            help="Port of the neuro-san server.",
        ),
        one_shot: bool = typer.Option(
            False,
            "--one-shot",
            help="Send one prompt and exit (non-interactive mode).",
        ),
        list_agents: bool = typer.Option(
            False,
            "--list",
            help="List all available agents and exit.",
        ),
    ) -> None:
        """Chat with an agent network, forwarding extra options to AgentCli."""
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio.commands.chat import ChatCommand

        extra = list(ctx.args)
        agent = None
        if extra and not extra[0].startswith("--"):
            agent = extra.pop(0)

        raise typer.Exit(
            code=ChatCommand(
                agent=agent,
                connection=connection,
                host=host,
                port=port,
                one_shot=one_shot,
                list_agents=list_agents,
                extra_args=extra,
            ).run()
        )

    @staticmethod
    @app.command("validate", help="Validate the structure of an agent network HOCON file.")
    def _validate_command(
        hocon_path: str = typer.Argument(
            ...,
            help="Path to the agent network HOCON file to validate.",
        ),
        verbose: bool = typer.Option(
            False,
            "--verbose",
            help="Print an agent network summary when validation passes.",
        ),
        external_agents: Optional[str] = typer.Option(
            None,
            "--external-agents",
            help="Comma-separated external agent references to treat as valid (e.g. '/agent1,/agent2').",
        ),
        mcp_servers: Optional[str] = typer.Option(
            None,
            "--mcp-servers",
            help="Comma-separated MCP server URLs to treat as valid.",
        ),
        registry_dir: Optional[str] = typer.Option(
            None,
            "--registry-dir",
            help="Base directory for resolving HOCON includes. Defaults to the current directory.",
        ),
    ) -> None:
        """Run the agent network HOCON validation and propagate its exit code."""
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio.commands.validate import ValidateCommand

        raise typer.Exit(
            code=ValidateCommand(
                hocon_path=hocon_path,
                verbose=verbose,
                external_agents=external_agents,
                mcp_servers=mcp_servers,
                registry_dir=registry_dir,
            ).run()
        )

    @staticmethod
    @app.command(
        "internalize-agents",
        help="Inline external-agent references in a HOCON file into one self-contained file.",
    )
    def _internalize_agents_command(
        input_path: str = typer.Argument(
            ...,
            help="Path to the parent HOCON file containing /-prefixed external-agent references.",
        ),
        output_path: str = typer.Option(
            ...,
            "--output",
            "-o",
            help=(
                "Path to write the self-contained HOCON output. The output is fully resolved "
                "(no includes, no /-prefixed external refs) and formatted as HOCON (JSON-like with "
                "quoted keys/commas; multi-line strings use HOCON triple quotes)."
            ),
        ),
        search_paths: Optional[str] = typer.Option(
            None,
            "--search-paths",
            help=(
                "Colon-separated directories to look up external HOCON files. Each `/<ref>` "
                "is joined as `<search_path>/<ref>.hocon`, so refs containing `/` (e.g. "
                "`/industry/banking_ops`) reach subdirectories naturally without listing "
                "them here. Defaults to 'registries'."
            ),
        ),
    ) -> None:
        """Run the internalize-agents command and propagate its exit code."""
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio.commands.internalize_agents import InternalizeAgentsCommand

        raise typer.Exit(
            code=InternalizeAgentsCommand(
                input_path=input_path,
                output_path=output_path,
                search_paths=search_paths,
            ).run()
        )


def main() -> None:
    """Entry point for the `neuro-san-studio` console script."""
    # Typer/click exit with SystemExit(0) on success and SystemExit(2) for
    # no-args-is-help; let clean exits return normally so main() can be
    # driven from tests and embedded callers.
    try:
        NeuroSanStudioCli.app()
    except SystemExit as exc:
        if exc.code not in (None, 0, 2):
            raise


if __name__ == "__main__":
    main()
