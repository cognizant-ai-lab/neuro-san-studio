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

"""Import agent networks from the installed neuro-san-studio package into the current project."""

import os
import sys
import zipfile
from typing import Dict
from typing import List
from typing import Optional

import questionary

from neuro_san_studio.discovery.agent_network_registry import AgentNetworkRegistry
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer
from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter
from neuro_san_studio.importer.agent_network_importer import is_skippable_metadata
from neuro_san_studio.utils.cli_prompt import CliPrompt
from neuro_san_studio.utils.cli_status import CliStatus
from neuro_san_studio.utils.package_paths import PackagePaths

CUSTOM = "__custom__"
ALL = "__all__"
FROM_FILE = "__from_file__"
BACK = "__back__"


class ImportCommand:  # pylint: disable=too-few-public-methods
    """Run the `ns import` flow: discover, prompt, resolve dependencies, copy, update manifest."""

    def __init__(
        self,
        networks_arg: Optional[List[str]] = None,
        force: bool = False,
    ):
        # Typer hands us a list of space-separated tokens (or None when omitted).
        self.networks_arg = networks_arg or []
        self.force = force
        self.target_dir = os.getcwd()

    def run(self) -> None:
        """Discover, prompt, and import the requested networks; print a summary."""
        if not self._verify_project_initialized():
            print()
            CliStatus.err("Project not initialized. Run 'ns init' first.")
            print()
            sys.exit(1)

        # A positional arg of .hocon/.zip paths is a local-file import (one or more,
        # space-separated). Registry names never carry those extensions. A mix of files
        # and registry names in one call is rejected; they take different import paths.
        if self.networks_arg:
            file_paths = self._split_file_args(self.networks_arg)
            if file_paths is not None:
                self._run_from_files(file_paths)
                return

        CliStatus.info("Discovering available agent networks...")
        print()
        try:
            source_dir = PackagePaths.installed_library_root()
            registry = AgentNetworkRegistry(source_dir=source_dir)
            networks_by_group = registry.discover()
        except FileNotFoundError as exc:
            CliStatus.err(str(exc))
            print()
            sys.exit(1)

        if self.networks_arg:
            selected = self._parse_arg(self.networks_arg, networks_by_group)
        else:
            selected = self._prompt(networks_by_group)

        # "From File" picked interactively — first slot is the FROM_FILE marker, second
        # is the user-typed path. Same end behavior as `ns import <path>`.
        if selected and selected[0] == FROM_FILE:
            self._run_from_files([selected[1]])
            return

        if not selected:
            print()
            CliStatus.info("No networks selected. Exiting.")
            print()
            return

        if not self._confirm_import(selected, force=self.force):
            print()
            CliStatus.info("Import cancelled.")
            print()
            return

        print()
        CliStatus.info(f"Importing {len(selected)} network(s)...")
        print()
        self._import(selected, registry)

        print()
        CliStatus.ok(f"Done with importing {len(selected)} agent network(s) from studio registry.")
        print()
        CliStatus.info("Next steps:")
        print("        - Run 'ns run' to start the server")
        print("        - If neuro-san server is running, the manifest will auto-reload.")
        print()

    def _verify_project_initialized(self) -> bool:
        return os.path.exists(os.path.join(self.target_dir, "registries", "manifest.hocon"))

    @staticmethod
    def _looks_like_agent_network_file(token: str) -> bool:
        """A token ending in .hocon/.zip is a local file path, not a registry name."""
        return token.lower().endswith((".hocon", ".zip"))

    @classmethod
    def _split_file_args(cls, tokens: List[str]) -> Optional[List[str]]:
        """Classify the space-separated tokens as a local-file import or a registry import.

        Returns the list of file paths when every token is a .hocon/.zip path (resolved
        relative to the current directory). Returns ``None`` when no token is a file path,
        so the caller falls through to registry resolution. Exits with an error on a mix
        of files and registry names; the two use different import paths.
        """
        tokens = [t.strip() for t in tokens if t.strip()]
        files = [t for t in tokens if cls._looks_like_agent_network_file(t)]
        if not files:
            return None
        if len(files) != len(tokens):
            names = [t for t in tokens if not cls._looks_like_agent_network_file(t)]
            print()
            CliStatus.err(
                "Cannot mix file paths and registry names in one import: "
                f"files={files}, names={names}. Run them as separate imports."
            )
            print()
            sys.exit(1)
        return files

    def _run_from_files(self, file_paths: List[str]) -> None:
        """Import one or more local .hocon/.zip files, then print a combined summary."""
        importer = AgentNetworkImporter(source_dir=self.target_dir, target_dir=self.target_dir)
        results = [r for r in (self._import_one_file(fp, importer) for fp in file_paths) if r is not None]
        if not results:
            return

        manifest_entries = [name for r in results for name in r.manifest_entries]
        if manifest_entries:
            print()
            CliStatus.info("Updating manifest...")
            importer.update_manifest(manifest_entries)

        self._print_summary(
            copied=sum(len(r.copied_files) for r in results),
            skipped=sum(len(r.skipped_files) for r in results),
            warnings=[w for r in results for w in r.warnings],
            errors=[e for r in results for e in r.errors],
        )
        self._print_mcp_summary(results)
        print()
        CliStatus.ok(f"Done with importing {len(results)} agent network(s) from local storage.")
        print()

    def _import_one_file(self, file_path: str, importer: AgentNetworkImporter):
        """Validate, confirm, and import a single local file. Returns the ImportResult,
        or ``None`` if the user declined the confirmation for this file."""
        source_path = os.path.abspath(os.path.expanduser(file_path))
        if not os.path.isfile(source_path):
            print()
            CliStatus.err(f"File not found: {file_path}")
            print()
            sys.exit(1)
        suffix = os.path.splitext(source_path)[1].lower()
        if suffix not in (".hocon", ".zip"):
            print()
            CliStatus.err(f"Unsupported file type: {suffix or '(none)'}. Expected .hocon or .zip")
            print()
            sys.exit(1)

        if not self._confirm_from_file(source_path, suffix):
            print()
            CliStatus.info(f"Skipped {os.path.basename(source_path)} (not confirmed).")
            print()
            return None

        print()
        CliStatus.info(f"Importing from {source_path}...")
        print()
        try:
            return importer.import_from_path(source_path, force=self.force)
        except (OSError, ValueError) as exc:
            print()
            CliStatus.err(str(exc))
            print()
            sys.exit(1)

    def _confirm_from_file(self, source_path: str, suffix: str) -> bool:
        """Show a preview tailored to the file shape, then ask y/N."""
        if suffix == ".hocon":
            return self._confirm_import([os.path.basename(source_path)], force=self.force)

        try:
            with zipfile.ZipFile(source_path) as zf:
                names = [info.filename for info in zf.infolist() if not info.is_dir()]
        except zipfile.BadZipFile:
            print()
            CliStatus.err(f"Not a valid zip archive: {source_path}")
            print()
            sys.exit(1)
        return self._confirm_zip_import(source_path, names, force=self.force)

    @staticmethod
    def _confirm_zip_import(source_path: str, names: List[str], force: bool = False) -> bool:
        """List registry HOCONs explicitly; collapse coded_tools/, middleware/, skills/ to counts."""
        # Filter out metadata so the preview matches what actually gets copied.
        real = [n for n in names if not is_skippable_metadata(n)]
        registries = sorted(
            n[len("registries/") :] for n in real if n.startswith("registries/") and n.endswith(".hocon")
        )
        bucket_counts = {
            "coded_tools/": sum(1 for n in real if n.startswith("coded_tools/")),
            "middleware/": sum(1 for n in real if n.startswith("middleware/")),
            "skills/": sum(1 for n in real if n.startswith("skills/")),
        }
        print()
        CliStatus.info(f"Files to import (from {os.path.basename(source_path)}):")
        if registries:
            print("  registries/")
            for rel in registries:
                print(f"    - {rel}")
        for bucket, count in bucket_counts.items():
            if count:
                print(f"  {bucket:<14}({count} files)")
        print()
        if force:
            CliStatus.warn("--force is set: existing files in the target will be OVERWRITTEN.")
        else:
            CliStatus.info("This will not overwrite any of the existing files. To overwrite, re-run with --force.")
        print()
        if not sys.stdin.isatty():
            return True
        try:
            question = questionary.confirm("Proceed with import?", default=True)
            answer = CliPrompt.bind_exit_on_esc(question).ask()
        except (KeyboardInterrupt, EOFError):
            return False
        return answer is True

    @staticmethod
    def _parse_arg(tokens: List[str], networks_by_group: Dict[str, List[str]]) -> List[str]:
        """Parse the positional tokens: 'all', group names, or specific network names/paths."""
        selected: List[str] = []
        for spec in (s.strip() for s in tokens):
            if not spec:
                continue
            if spec == "all":
                for paths in networks_by_group.values():
                    selected.extend(paths)
                continue
            if spec in networks_by_group:
                selected.extend(networks_by_group[spec])
                continue

            spec_clean = spec.removesuffix(".hocon")
            match = next(
                (
                    path
                    for paths in networks_by_group.values()
                    for path in paths
                    if path.removesuffix(".hocon") == spec_clean
                    or os.path.basename(path).removesuffix(".hocon") == spec_clean
                ),
                None,
            )
            if match:
                selected.append(match)
            else:
                CliStatus.warn(f"Network '{spec}' not found, skipping.")
        return list(dict.fromkeys(selected))

    @classmethod
    def _prompt(cls, networks_by_group: Dict[str, List[str]]) -> List[str]:
        """Two-tier flow: pick a group / All / Custom / From File; Custom drills into a
        network checkbox. Left/Esc on a sub-screen returns to the top screen, discarding
        selections. From File is signalled by returning :data:`FROM_FILE`; the caller
        diverts to the file-import path instead of resolving names against the registry."""
        while True:
            top = cls._prompt_top(networks_by_group)
            if top is None or top == CliPrompt.EXIT:
                return []
            if top == ALL:
                return [path for paths in networks_by_group.values() for path in paths]
            if top == FROM_FILE:
                picked = cls._prompt_for_file_path()
                if picked is None:  # ←/Esc on path prompt → back to top menu
                    continue
                return [FROM_FILE, picked]
            if top == CUSTOM:
                confirmed = cls._custom_flow(networks_by_group)
                if confirmed is None:  # user pressed ←/Esc at the first custom step
                    continue
                return confirmed
            return list(networks_by_group.get(top, []))

    @staticmethod
    def _prompt_top(networks_by_group: Dict[str, List[str]]) -> Optional[str]:
        """Top-menu picker. Group rows first (data), then a separator, then action rows
        (All / Custom selection / From File) — actions are styled distinctly so they
        read as commands rather than just another bucket."""
        total = sum(len(paths) for paths in networks_by_group.values())
        choices: List = [
            questionary.Choice(title=f"{group.capitalize()} ({len(paths)})", value=group)
            for group, paths in networks_by_group.items()
        ]
        choices += [
            questionary.Separator(),
            questionary.Choice(title=[("class:action", f"All ({total})")], value=ALL),
            questionary.Choice(title=[("class:action", "Custom selection")], value=CUSTOM),
            questionary.Separator(),
            questionary.Choice(title=[("class:from-file", "From File")], value=FROM_FILE),
        ]
        question = questionary.select(
            "What do you want to import?",
            choices=choices,
            style=questionary.Style([("action", "fg:#5fafd7"), ("from-file", "fg:#d7875f")]),
        )
        return CliPrompt.bind_exit_on_esc(question).ask()

    @staticmethod
    def _prompt_for_file_path() -> Optional[str]:
        """Ask for a .hocon or .zip path; ←/Esc returns None so the caller pops back to
        the top menu (same back-semantics as the other sub-screens). Validation is left
        to ``_run_from_file`` so messages match the positional file-path flow."""
        try:
            question = questionary.path("Path to .hocon or .zip:", only_directories=False)
            answer = CliPrompt.bind_back_keys(question, BACK).ask()
        except (KeyboardInterrupt, EOFError):
            return None
        if answer is None or answer == BACK:
            return None
        answer = answer.strip()
        return answer or None

    @classmethod
    def _custom_flow(cls, networks_by_group: Dict[str, List[str]]) -> Optional[List[str]]:
        """Custom = pick groups (multi-select) → pick networks within those groups.
        Left at any step backs up one screen; Left at the first step returns None
        so the caller pops back to the top menu. If no groups are toggled, fall
        through to the network picker showing all groups (Enter-without-Space ≠
        silent exit). Final confirmation is handled uniformly by the caller."""
        while True:
            groups = cls._prompt_groups(networks_by_group)
            if groups is None:
                return None  # back to top menu
            subset = {g: networks_by_group[g] for g in groups} if groups else networks_by_group
            picked = cls._prompt_networks(subset)
            if picked is None:
                continue  # back to group-filter
            return picked

    @classmethod
    def _prompt_groups(cls, networks_by_group: Dict[str, List[str]]) -> Optional[List[str]]:
        """Multi-select picker for which groups to narrow by. Empty selection = all groups."""
        choices = [
            questionary.Choice(title=f"{group.capitalize()} ({len(paths)})", value=group)
            for group, paths in networks_by_group.items()
        ]
        question = questionary.checkbox(
            "Pick groups to narrow the network list:",
            choices=choices,
            instruction="(Space=select groups · Enter=continue · ←=back · Enter with none = all groups)",
        )
        result = cls._ask_with_back(question)
        if result == BACK:
            return None
        return result or []

    @classmethod
    def _prompt_networks(cls, networks_by_group: Dict[str, List[str]]) -> Optional[List[str]]:
        choices: List = []
        for group, paths in networks_by_group.items():
            choices.append(questionary.Separator(f"─── {group.upper()} ({len(paths)}) ───"))
            for path in sorted(paths):
                name = os.path.basename(path).removesuffix(".hocon")
                choices.append(questionary.Choice(title=name, value=path))

        question = questionary.checkbox(
            "Toggle networks with SPACE, then press ENTER (A=toggle all, ←=back):",
            choices=choices,
            instruction="(Space=toggle · A=toggle all · Enter=continue)",
        )
        result = cls._ask_with_back(question)
        if result == BACK:
            return None
        return result or []

    @staticmethod
    def _confirm_import(selected: List[str], force: bool = False) -> bool:
        """Show the final list + a non-overwrite note, then ask y/N. Non-TTY auto-confirms."""
        print()
        CliStatus.info("Networks to import:")
        for path in selected:
            print(f"  - {path}")
        print()
        if force:
            CliStatus.warn("--force is set: existing files in the target will be OVERWRITTEN.")
        else:
            CliStatus.info("This will not overwrite any of the existing files. To overwrite, re-run with --force.")
        print()
        if not sys.stdin.isatty():
            return True
        try:
            question = questionary.confirm("Proceed with import?", default=True)
            answer = CliPrompt.bind_exit_on_esc(question).ask()
        except (KeyboardInterrupt, EOFError):
            return False
        return answer is True

    @staticmethod
    def _ask_with_back(question):
        """Run a questionary checkbox with ← / Esc → BACK sentinel (intuitive return-to-prev-screen)."""
        return CliPrompt.bind_back_keys(question, BACK).ask()

    def _import(self, hocon_paths: List[str], registry: AgentNetworkRegistry) -> None:
        analyzer = DependencyAnalyzer(
            registry.registries_dir,
            os.path.join(registry.source_dir, "coded_tools"),
            os.path.join(registry.source_dir, "middleware"),
        )
        importer = AgentNetworkImporter(registry.source_dir, self.target_dir)
        results, top_errors = self._collect_results(
            hocon_paths, analyzer, importer, registry.registries_dir, force=self.force
        )

        # Use manifest_entries (not hocon_path) so transitively-imported sub-networks are
        # registered too — agent_network_designer pulls in three sub-networks; without this
        # they'd land on disk but never get served.
        imported = [name for r in results for name in r.manifest_entries]
        if imported:
            print()
            CliStatus.info("Updating manifest...")
            importer.update_manifest(imported)

        copied = sum(len(r.copied_files) for r in results)
        skipped = sum(len(r.skipped_files) for r in results)
        warnings = [w for r in results for w in r.warnings]
        errors = top_errors + [e for r in results for e in r.errors]
        self._print_summary(copied, skipped, warnings, errors)
        self._print_mcp_summary(results)

    @staticmethod
    def _collect_results(
        hocon_paths: List[str],
        analyzer: DependencyAnalyzer,
        importer: AgentNetworkImporter,
        registries_dir: str,
        force: bool = False,
    ):
        """Analyze and import each network; return successful ImportResults plus any top-level errors."""
        results = []
        errors: List[str] = []
        for hocon_path in hocon_paths:
            full_path = os.path.join(registries_dir, hocon_path)
            CliStatus.info(f"Analyzing {hocon_path}...")
            try:
                deps = analyzer.get_transitive_dependencies(full_path)
            except (OSError, ValueError) as exc:
                errors.append(f"Failed to analyze {hocon_path}: {exc}")
                continue

            CliStatus.info(f"Importing {hocon_path}...")
            try:
                results.append(importer.import_network(hocon_path, deps, force=force))
            except (OSError, ValueError) as exc:
                errors.append(f"Failed to import {hocon_path}: {exc}")
        return results, errors

    @staticmethod
    def _print_mcp_summary(results) -> None:
        """List MCP servers merged into <project>/mcp/mcp_info.hocon, plus any skipped (already-present) URLs."""
        added = [u for r in results for u in r.mcp_added]
        skipped = [u for r in results for u in r.mcp_skipped]
        if not (added or skipped):
            return
        if added:
            print()
            CliStatus.info(f"MCP servers added to mcp/mcp_info.hocon ({len(added)}):")
            for url in added:
                print(f"        - {url}")
        if skipped:
            print()
            CliStatus.info(f"MCP servers already configured, left untouched ({len(skipped)}):")
            for url in skipped:
                print(f"        - {url}")

    @staticmethod
    def _print_summary(copied: int, skipped: int, warnings: List[str], errors: List[str]) -> None:
        print()
        CliStatus.info("Summary:")
        CliStatus.ok(f"Copied: {copied} files")
        if skipped:
            CliStatus.skip(f"Skipped: {skipped} files (already exist)")
        if warnings:
            print()
            CliStatus.warn(f"Warnings ({len(warnings)}):")
            for item in warnings[:5]:
                print(f"        - {item}")
            if len(warnings) > 5:
                print(f"        ... and {len(warnings) - 5} more")
        if errors:
            print()
            CliStatus.err(f"Errors ({len(errors)}):")
            for item in errors[:5]:
                print(f"        - {item}")
            if len(errors) > 5:
                print(f"        ... and {len(errors) - 5} more")
