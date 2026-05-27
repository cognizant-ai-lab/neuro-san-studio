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
from prompt_toolkit.keys import Keys

from neuro_san_studio.discovery.agent_network_registry import AgentNetworkRegistry
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer
from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter

CUSTOM = "__custom__"
ALL = "__all__"
BACK = "__back__"


class ImportCommand:  # pylint: disable=too-few-public-methods
    """Run the `ns import` flow: discover, prompt, resolve dependencies, copy, update manifest."""

    def __init__(
        self,
        networks_arg: Optional[str] = None,
        from_file: Optional[str] = None,
        force: bool = False,
    ):
        if networks_arg and from_file:
            raise ValueError("Cannot pass both 'networks' and '--from-file'; they are mutually exclusive.")
        self.networks_arg = networks_arg
        self.from_file = from_file
        self.force = force
        self.target_dir = os.getcwd()

    def run(self) -> None:
        """Discover, prompt, and import the requested networks; print a summary."""
        if not self._verify_project_initialized():
            print("\n❌ Project not initialized. Run 'ns init' first.\n")
            sys.exit(1)

        if self.from_file:
            self._run_from_file()
            return

        print("🔍 Discovering available agent networks...\n")
        try:
            source_dir = self._find_neuro_san_studio_installation()
            registry = AgentNetworkRegistry(source_dir=source_dir)
            networks_by_group = registry.discover()
        except FileNotFoundError as exc:
            print(f"❌ {exc}\n")
            sys.exit(1)

        if self.networks_arg:
            selected = self._parse_arg(self.networks_arg, networks_by_group)
        else:
            selected = self._prompt(networks_by_group)

        if not selected:
            print("\n📭 No networks selected. Exiting.\n")
            return

        if not self._confirm_import(selected):
            print("\n📭 Import cancelled.\n")
            return

        print(f"\n📦 Importing {len(selected)} network(s)...\n")
        self._import(selected, registry)

        print("\n✅ Import complete!")
        print("\n💡 Next steps:")
        print("   - Run 'ns run' to start the server")
        print("   - If neuro-san server is running, the manifest will auto-reload.\n")

    def _verify_project_initialized(self) -> bool:
        return os.path.exists(os.path.join(self.target_dir, "registries", "manifest.hocon"))

    def _run_from_file(self) -> None:
        """Import a single .hocon (self-contained) or a .zip bundle (path-preserving)."""
        source_path = os.path.abspath(os.path.expanduser(self.from_file))
        if not os.path.isfile(source_path):
            print(f"\n❌ File not found: {self.from_file}\n")
            sys.exit(1)
        suffix = os.path.splitext(source_path)[1].lower()
        if suffix not in (".hocon", ".zip"):
            print(f"\n❌ Unsupported file type: {suffix or '(none)'}. Expected .hocon or .zip\n")
            sys.exit(1)

        if not self._confirm_from_file(source_path, suffix):
            print("\n📭 Import cancelled.\n")
            return

        print(f"\n📦 Importing from {source_path}...\n")
        importer = AgentNetworkImporter(source_dir=self.target_dir, target_dir=self.target_dir)
        try:
            result = importer.import_from_path(source_path, force=self.force)
        except (OSError, ValueError) as exc:
            print(f"\n❌ {exc}\n")
            sys.exit(1)

        manifest_entries = self._registry_entries_from_result(result)
        if manifest_entries:
            print("   Updating manifest...")
            importer.update_manifest(manifest_entries)

        self._print_summary(
            copied=len(result.copied_files),
            skipped=len(result.skipped_files),
            warnings=result.warnings,
            errors=result.errors,
        )
        print("\n✅ Import complete!\n")

    def _confirm_from_file(self, source_path: str, suffix: str) -> bool:
        """Show a preview tailored to the file shape, then ask y/N."""
        if suffix == ".hocon":
            return self._confirm_import([os.path.basename(source_path)])

        try:
            with zipfile.ZipFile(source_path) as zf:
                names = [info.filename for info in zf.infolist() if not info.is_dir()]
        except zipfile.BadZipFile:
            print(f"\n❌ Not a valid zip archive: {source_path}\n")
            sys.exit(1)
        return self._confirm_zip_import(source_path, names)

    @staticmethod
    def _confirm_zip_import(source_path: str, names: List[str]) -> bool:
        """List registry HOCONs explicitly; collapse coded_tools/, middleware/, skills/ to counts."""
        # Filter out metadata so the preview matches what actually gets copied.
        real = [n for n in names if not AgentNetworkImporter._is_skippable_metadata(n)]
        registries = sorted(
            n[len("registries/") :] for n in real if n.startswith("registries/") and n.endswith(".hocon")
        )
        bucket_counts = {
            "coded_tools/": sum(1 for n in real if n.startswith("coded_tools/")),
            "middleware/": sum(1 for n in real if n.startswith("middleware/")),
            "skills/": sum(1 for n in real if n.startswith("skills/")),
        }
        print(f"\nFiles to import (from {os.path.basename(source_path)}):")
        if registries:
            print("  registries/")
            for rel in registries:
                print(f"    - {rel}")
        for bucket, count in bucket_counts.items():
            if count:
                print(f"  {bucket:<14}({count} files)")
        print(
            "\nNote:\n"
            "This will not overwrite any of the existing files.\n"
            "To overwrite, re-run with --force.\n"
        )
        if not sys.stdin.isatty():
            return True
        try:
            return questionary.confirm("Proceed with import?", default=True).ask() is True
        except (KeyboardInterrupt, EOFError):
            return False

    @staticmethod
    def _registry_entries_from_result(result) -> List[str]:
        """Pull manifest-relative paths from the importer's copied_files for `registries/**/*.hocon`."""
        entries: List[str] = []
        for path in result.copied_files:
            if path.startswith("registries/") and path.endswith(".hocon"):
                entries.append(path[len("registries/") :])
            elif path.endswith(".hocon") and "/" not in path:
                # Single-HOCON path: copied_files is just the basename.
                entries.append(path)
        return entries

    @staticmethod
    def _find_neuro_san_studio_installation() -> str:
        try:
            import registries  # pylint: disable=import-outside-toplevel

            if hasattr(registries, "__path__"):
                return os.path.dirname(registries.__path__[0])
        except ImportError:
            pass

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if os.path.exists(os.path.join(project_root, "registries")):
            return project_root

        raise FileNotFoundError(
            "Cannot find neuro-san-studio installation. Make sure neuro-san-studio is installed via pip."
        )

    @staticmethod
    def _parse_arg(arg: str, networks_by_group: Dict[str, List[str]]) -> List[str]:
        """Parse --networks argument: 'all', a group name, or specific network names/paths."""
        selected: List[str] = []
        for spec in (s.strip() for s in arg.split(",")):
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
                print(f"⚠️  Network '{spec}' not found, skipping.")
        return list(dict.fromkeys(selected))

    @classmethod
    def _prompt(cls, networks_by_group: Dict[str, List[str]]) -> List[str]:
        """Two-tier flow: pick a group / All / Custom; Custom drills into a network checkbox.
        Left arrow on a sub-screen returns to the top screen, discarding selections."""
        while True:
            top = cls._prompt_top(networks_by_group)
            if top is None:
                return []
            if top == ALL:
                return [path for paths in networks_by_group.values() for path in paths]
            if top == CUSTOM:
                confirmed = cls._custom_flow(networks_by_group)
                if confirmed is None:  # user pressed Left at the first custom step
                    continue
                return confirmed
            return list(networks_by_group.get(top, []))

    @staticmethod
    def _prompt_top(networks_by_group: Dict[str, List[str]]) -> Optional[str]:
        total = sum(len(paths) for paths in networks_by_group.values())
        choices = [
            questionary.Choice(title=f"{group.capitalize()} ({len(paths)})", value=group)
            for group, paths in networks_by_group.items()
        ]
        choices += [
            questionary.Separator(),
            questionary.Choice(title="Custom selection", value=CUSTOM),
            questionary.Choice(title=f"All ({total})", value=ALL),
        ]
        return questionary.select(
            "What do you want to import?",
            choices=choices,
        ).ask()

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
    def _confirm_import(selected: List[str]) -> bool:
        """Show the final list + a non-overwrite note, then ask y/N. Non-TTY auto-confirms."""
        print("\nNetworks to import:")
        for path in selected:
            print(f"  - {path}")
        print(
            "\nNote:\n"
            "This will not overwrite any of the existing files.\n"
            "To import the original agent-networks from studio, "
            "remove the ones on your current project.\n"
        )
        if not sys.stdin.isatty():
            return True
        try:
            return questionary.confirm("Proceed with import?", default=True).ask() is True
        except (KeyboardInterrupt, EOFError):
            return False

    @staticmethod
    def _ask_with_back(question):
        """Run a questionary checkbox with Left=exit-with-BACK sentinel."""

        @question.application.key_bindings.add(Keys.Left)
        def _back(event):
            event.app.exit(result=BACK)

        return question.ask()

    def _import(self, hocon_paths: List[str], registry: AgentNetworkRegistry) -> None:
        analyzer = DependencyAnalyzer(
            registry.registries_dir,
            os.path.join(registry.source_dir, "coded_tools"),
            os.path.join(registry.source_dir, "middleware"),
        )
        importer = AgentNetworkImporter(registry.source_dir, self.target_dir)
        results, top_errors = self._collect_results(hocon_paths, analyzer, importer, registry.registries_dir)

        imported = [r.hocon_path for r in results]
        if imported:
            print("\n   Updating manifest...")
            importer.update_manifest(imported)

        copied = sum(len(r.copied_files) for r in results)
        skipped = sum(len(r.skipped_files) for r in results)
        warnings = [w for r in results for w in r.warnings]
        errors = top_errors + [e for r in results for e in r.errors]
        self._print_summary(copied, skipped, warnings, errors)

    @staticmethod
    def _collect_results(
        hocon_paths: List[str],
        analyzer: DependencyAnalyzer,
        importer: AgentNetworkImporter,
        registries_dir: str,
    ):
        """Analyze and import each network; return successful ImportResults plus any top-level errors."""
        results = []
        errors: List[str] = []
        for hocon_path in hocon_paths:
            full_path = os.path.join(registries_dir, hocon_path)
            print(f"   Analyzing {hocon_path}...")
            try:
                deps = analyzer.get_transitive_dependencies(full_path)
            except (OSError, ValueError) as exc:
                errors.append(f"Failed to analyze {hocon_path}: {exc}")
                continue

            print(f"   Importing {hocon_path}...")
            try:
                results.append(importer.import_network(hocon_path, deps))
            except (OSError, ValueError) as exc:
                errors.append(f"Failed to import {hocon_path}: {exc}")
        return results, errors

    @staticmethod
    def _print_summary(copied: int, skipped: int, warnings: List[str], errors: List[str]) -> None:
        print("\n📊 Summary:")
        print(f"   ✅ Copied: {copied} files")
        if skipped:
            print(f"   ⏭️  Skipped: {skipped} files (already exist)")
        for label, items in (("⚠️  Warnings", warnings), ("❌ Errors", errors)):
            if not items:
                continue
            print(f"\n{label} ({len(items)}):")
            for item in items[:5]:
                print(f"   - {item}")
            if len(items) > 5:
                print(f"   ... and {len(items) - 5} more")
