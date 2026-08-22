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

"""Implementation of the `neuro-san-studio init` command."""

import importlib.resources
import os
import shutil
import sys
from typing import Dict
from typing import List
from typing import Optional

from pyhocon import ConfigFactory
from rich.console import Console
from rich.table import Table
from timedinput import timedinput

from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter
from neuro_san_studio.utils.cli_status import CliStatus
from neuro_san_studio.utils.import_reporter import ImportReporter
from neuro_san_studio.utils.package_paths import PackagePaths
from neuro_san_studio.utils.shared_registries import SHARED_REGISTRY_INCLUDES

PROVIDERS: Dict[str, Dict[str, str]] = {
    "openai": {"label": "OpenAI", "model_name": "gpt-5.2"},
    "anthropic": {"label": "Anthropic", "model_name": "claude-sonnet"},
    "google": {"label": "Google Gemini", "model_name": "gemini-3-flash"},
}

TEMPLATES_PACKAGE = "neuro_san_studio.templates"
MANIFEST_TEMPLATE = "manifest.hocon"

# The line that includes "generated" networks: we want to ignore them when we install
# the default agent networks. See _default_network_hocons().
GENERATED_MANIFEST_INCLUDE = 'include "registries/generated/manifest.hocon"'

# Long enough to never bite a real user; finite so timedinput is happy and so a
# detached terminal can't hang the process forever.
INPUT_TIMEOUT_SECONDS = 300

_console = Console()


class InitCommand:  # pylint: disable=too-few-public-methods
    """Scaffold a starter neuro-san-studio project in the current directory."""

    def __init__(self, providers_arg: Optional[str] = None, root_dir: Optional[str] = None):
        """Initialize the command.

        Args:
            providers_arg: Comma-separated provider keys (e.g. "openai,anthropic").
                When provided, skips the interactive prompt.
            root_dir: Directory to scaffold into. Defaults to the current working directory.
        """
        self.providers_arg = providers_arg
        self.root_dir = root_dir or os.getcwd()

    def run(self) -> None:
        """Resolve providers and write starter files."""
        providers = self._resolve_providers()
        provider_labels = ", ".join(PROVIDERS[p]["label"] for p in providers)
        _console.print(f"[bold]Selected providers:[/bold] {provider_labels}\n")

        self._copy_template(MANIFEST_TEMPLATE, os.path.join("registries", MANIFEST_TEMPLATE))
        # Pre-create registries/generated/ so the include in the main manifest resolves the
        # first time the server reads it, even before agent_network_designer has produced
        # any files. Empty `{}` is a valid manifest — neuro-san just sees no extra networks.
        self._copy_template("generated_manifest.hocon", os.path.join("registries", "generated", "manifest.hocon"))
        # Shared registry-level HOCONs that networks include. Most networks in the
        # basic/industry/experimental groups depend on at least one of these, so
        # scaffolding them up front means `ns import <group>` works without surprises.
        for shared in SHARED_REGISTRY_INCLUDES:
            self._copy_template(shared, os.path.join("registries", shared), package="registries")
        # The designer reads this to learn which networks it may compose into a design.
        # Separate from the served manifest above so the two lists can diverge.
        self._copy_template("manifest_and.hocon", os.path.join("registries", "manifest_and.hocon"))
        self._copy_template("mcp_info.hocon", os.path.join("mcp", "mcp_info.hocon"), package="neuro_san_studio.mcp")
        self._copy_template("plugins.hocon", os.path.join("config", "plugins.hocon"))
        self._write_file(os.path.join("config", "llm_config.hocon"), self._render_llm_config(providers))

        # Last, so the dependency walker sees a project that already has the shared HOCON
        # fragments and llm_config.hocon the networks include.
        self._install_default_networks()

        self._print_next_steps()

    @staticmethod
    def _default_network_hocons() -> List[str]:
        """Return the registry-relative networks `ns init` installs, per the manifest template
        `neuro_san_studio/templates/manifest.hocon`.

        Ignores the GENERATED_MANIFEST_INCLUDE line. It exists so the running *server* picks up
        networks agent_network_designer writes later.
        """
        source = importlib.resources.files(TEMPLATES_PACKAGE) / MANIFEST_TEMPLATE
        declared = "\n".join(
            line for line in source.read_text(encoding="utf-8").splitlines() if GENERATED_MANIFEST_INCLUDE not in line
        )
        config = ConfigFactory.parse_string(declared)
        # as_plain_ordered_dict() strips the quotes pyhocon bakes into keys that had to be quoted in
        # the source; the raw ConfigTree hands back '"basic/music_nerd.hocon"', quote characters and all.
        return list(config.as_plain_ordered_dict())

    def _install_default_networks(self) -> None:
        """Copy the default agent networks and their dependencies into the project.

        Runs the same `AgentNetworkImporter.import_networks` batch that `ns import` runs,
        rather than a second hand-maintained copy of the analyze-then-copy loop, so the two
        commands cannot drift about what a network actually depends on. The list of networks
        is likewise derived from the manifest template (see `_default_network_hocons`), so the
        file that decides what is served is the same file that decides what is copied.

        The manifest entries are NOT written here: `manifest.hocon` is scaffolded from a
        template that already declares each of these with the right flags. Registering them
        through `AgentNetworkImporter.update_manifest` would write a flat `"x": true` and lose
        the `serve/public` distinction the support networks need.
        """
        try:
            source_dir = PackagePaths.installed_library_root()
        except FileNotFoundError as exc:
            CliStatus.warn(f"Skipping default agent networks: {exc}")
            return

        _console.print()
        CliStatus.info("Installing the Agent Network Designer...")
        importer = AgentNetworkImporter(source_dir, self.root_dir)
        bulk = importer.import_networks(self._default_network_hocons(), on_network=ImportReporter.announce)

        # Python resolves a directory without __init__.py as a namespace *portion* and keeps
        # searching sys.path, so the studio's own installed coded_tools package would win over
        # the project's. The importer copies these along with each dependency; assert it rather
        # than leave a silently-shadowed project if that ever regresses.
        self._ensure_package_roots(source_dir)

        ImportReporter.report(bulk)

    def _ensure_package_roots(self, source_dir: str) -> None:
        """Guarantee coded_tools/__init__.py and middleware/__init__.py exist in the project."""
        for package in ("coded_tools", "middleware"):
            target = os.path.join(self.root_dir, package, "__init__.py")
            if os.path.exists(target) or not os.path.isdir(os.path.dirname(target)):
                continue
            source = os.path.join(source_dir, package, "__init__.py")
            if os.path.isfile(source):
                shutil.copy2(source, target)
            else:
                with open(target, "w", encoding="utf-8"):
                    pass
            CliStatus.ok(os.path.join(package, "__init__.py"))

    def _resolve_providers(self) -> List[str]:
        """Return the ordered list of provider keys to enable."""
        if self.providers_arg is not None:
            return self._parse_providers_arg(self.providers_arg)
        if not sys.stdin.isatty():
            _console.print("[dim]No --providers flag and non-interactive terminal. Defaulting to OpenAI.[/dim]\n")
            return ["openai"]
        return self._prompt_providers()

    @staticmethod
    def _parse_providers_arg(raw: str) -> List[str]:
        """Parse a comma-separated list of provider keys, preserving order and de-duplicating."""
        seen: List[str] = []
        for token in raw.split(","):
            key = token.strip().lower()
            if not key:
                continue
            if key not in PROVIDERS:
                valid = ", ".join(PROVIDERS.keys())
                raise ValueError(f"Unknown provider '{key}'. Valid providers: {valid}.")
            if key not in seen:
                seen.append(key)
        if not seen:
            raise ValueError("--providers must list at least one provider.")
        return seen

    @staticmethod
    def _prompt_providers() -> List[str]:
        """Prompt the user interactively for provider selection."""
        keys = list(PROVIDERS.keys())
        _console.print("\n[bold cyan]Which LLM providers do you want to enable?[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
        table.add_column("#", justify="right", style="dim")
        table.add_column("Provider", style="bold")
        table.add_column("Default model", style="cyan")
        for idx, key in enumerate(keys, start=1):
            info = PROVIDERS[key]
            model_cell = info["model_name"]
            if key == "openai":
                model_cell = f"{model_cell} [green](default)[/green]"
            table.add_row(str(idx), info["label"], model_cell)
        _console.print(table)
        _console.print()

        raw = timedinput(
            "Enter numbers separated by commas (default: 1): ",
            timeout=INPUT_TIMEOUT_SECONDS,
            default="1",
        ).strip()
        if not raw:
            return ["openai"]
        selected: List[str] = []
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                idx = int(token)
            except ValueError as exc:
                raise ValueError(f"'{token}' is not a number.") from exc
            if idx < 1 or idx > len(keys):
                raise ValueError(f"Choice {idx} is out of range (1-{len(keys)}).")
            key = keys[idx - 1]
            if key not in selected:
                selected.append(key)
        if not selected:
            return ["openai"]
        return selected

    @staticmethod
    def _render_llm_config(providers: List[str]) -> str:
        """Render config/llm_config.hocon for the selected providers.

        Providers are emitted in user-selected order: the first provider becomes
        the primary model, and any subsequent providers become its fallbacks in
        the order the user listed them. With a single provider, a flat
        ``model_name`` block is rendered instead of a ``fallbacks`` list.

        Runtime semantics: this matches the shape of
        ``registries/basic/music_nerd_llm_fallbacks.hocon``. The neuro-san agent
        chain reads it via ``langchain_run_context.create_agent_with_fallbacks``,
        which extracts the ``fallbacks`` list and iterates it in order. The first
        entry resolves as the primary model; subsequent entries are tried in
        order on failure. See ``docs/examples/basic/music_nerd_llm_fallbacks.md``.

        Raises:
            ValueError: If ``providers`` is empty. An empty list would render an
                empty ``fallbacks`` array, which the runtime rejects with "No
                fully-specified LLM found". Every caller path already guarantees
                at least one provider; this guard makes the contract explicit so
                a future caller cannot scaffold an unbootable project.
        """
        if not providers:
            raise ValueError("_render_llm_config requires at least one provider.")

        if len(providers) == 1:
            model = PROVIDERS[providers[0]]["model_name"]
            return '{\n    "llm_config": {\n        "model_name": "' + model + '"\n    }\n}\n'

        lines = ["{", '    "llm_config": {', '        "fallbacks": [']
        for i, key in enumerate(providers):
            model = PROVIDERS[key]["model_name"]
            comma = "," if i < len(providers) - 1 else ""
            lines.append(f'            {{ "model_name": "{model}" }}{comma}')
        lines.extend(["        ]", "    }", "}", ""])
        return "\n".join(lines)

    def _copy_template(self, template_name: str, dest_rel: str, package: str = TEMPLATES_PACKAGE) -> None:
        """Copy a packaged file into the project.

        Args:
            template_name: Filename inside the source package.
            dest_rel: Destination path relative to the project root.
            package: Source package to read from. Defaults to neuro_san_studio.templates.
        """
        dest_abs = os.path.join(self.root_dir, dest_rel)
        if os.path.exists(dest_abs):
            CliStatus.skip(f"{dest_rel} (already exists)")
            return
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        source = importlib.resources.files(package) / template_name
        with source.open("rb") as src, open(dest_abs, "wb") as dst:
            shutil.copyfileobj(src, dst)
        CliStatus.ok(dest_rel)

    def _write_file(self, rel_path: str, content: str) -> None:
        """Write content to rel_path under root_dir, skipping if the file already exists."""
        dest_abs = os.path.join(self.root_dir, rel_path)
        if os.path.exists(dest_abs):
            CliStatus.skip(f"{rel_path} (already exists)")
            return
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        with open(dest_abs, "w", encoding="utf-8") as fh:
            fh.write(content)
        CliStatus.ok(rel_path)

    def _print_next_steps(self) -> None:
        """Print the final instructions shown after scaffolding completes."""
        _console.print()
        _console.print("=" * 60, style="dim")
        _console.print("[bold green]Project initialized.[/bold green]")
        _console.print()
        _console.print("[bold cyan]Next steps:[/bold cyan]")
        _console.print("  1. Set the API keys for the providers you enabled (e.g. in a .env file).")
        _console.print(
            "  2. Start the server:  [bold red]neuro-san-studio run[/bold red] or [bold red]ns run[/bold red]"
        )
        _console.print(
            "  3. Design your own agent network: click [bold]NEW[/bold] in the nsflow UI to open the "
            "Agent Network Designer."
        )
        _console.print()
        _console.print("[dim]Add more of the networks that ship with neuro-san-studio with 'ns import'.[/dim]")
        _console.print("=" * 60, style="dim")
