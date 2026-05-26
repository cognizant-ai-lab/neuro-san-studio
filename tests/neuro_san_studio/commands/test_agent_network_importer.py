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

"""Integration tests for AgentNetworkImporter against a synthetic source dir."""

import json
from pathlib import Path

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter


class TestImportNetwork:
    """Integration tests for AgentNetworkImporter."""

    @staticmethod
    def _build_fake_source(source_dir: Path) -> None:
        """Lay out a minimal source repo: one network plus one coded tool plus one middleware file."""
        registries = source_dir / "registries"
        (registries / "basic").mkdir(parents=True)
        (registries / "basic" / "music_nerd.hocon").write_text('{ "tools": [] }\n')
        # Shared registry includes that the importer always copies.
        for shared in ("aaosa.hocon", "aaosa_basic.hocon", "aaosa_basic_debug.hocon"):
            (registries / shared).write_text(f"# {shared}\n")

        coded_tools = source_dir / "coded_tools" / "music_nerd"
        coded_tools.mkdir(parents=True)
        (coded_tools / "__init__.py").write_text("")
        (coded_tools / "lookup.py").write_text("def lookup():\n    pass\n")

        middleware = source_dir / "middleware" / "music_nerd"
        middleware.mkdir(parents=True)
        (middleware / "__init__.py").write_text("")
        (middleware / "logger.py").write_text("class Logger:\n    pass\n")

    def test_import_copies_hocon_coded_tools_and_middleware(self, tmp_path: Path) -> None:
        """A successful import should land the network HOCON, its coded tool, and its middleware."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        self._build_fake_source(source_dir)

        importer = AgentNetworkImporter(str(source_dir), str(target_dir))
        deps = AgentNetworkDependencies(
            coded_tools=["coded_tools/music_nerd/lookup.py"],
            middleware=["middleware/music_nerd/logger.py"],
        )

        result = importer.import_network("basic/music_nerd.hocon", deps)

        assert (target_dir / "registries" / "basic" / "music_nerd.hocon").is_file()
        assert (target_dir / "coded_tools" / "music_nerd" / "lookup.py").is_file()
        assert (target_dir / "middleware" / "music_nerd" / "logger.py").is_file()
        # Parent __init__.py files are copied so the package stays importable.
        assert (target_dir / "coded_tools" / "music_nerd" / "__init__.py").is_file()
        assert (target_dir / "middleware" / "music_nerd" / "__init__.py").is_file()
        # Shared registry includes ride along.
        assert (target_dir / "registries" / "aaosa.hocon").is_file()
        assert not result.errors

    def test_import_skips_existing_files(self, tmp_path: Path) -> None:
        """Pre-existing target files must not be overwritten and should be reported as skipped."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        self._build_fake_source(source_dir)

        existing = target_dir / "registries" / "basic" / "music_nerd.hocon"
        existing.parent.mkdir(parents=True)
        existing.write_text("DO NOT OVERWRITE\n")

        importer = AgentNetworkImporter(str(source_dir), str(target_dir))
        result = importer.import_network("basic/music_nerd.hocon", AgentNetworkDependencies())

        assert existing.read_text() == "DO NOT OVERWRITE\n"
        assert "basic/music_nerd.hocon" in result.skipped_files

    def test_update_manifest_merges_into_existing_json(self, tmp_path: Path) -> None:
        """update_manifest should merge new entries into a sorted JSON manifest."""
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        registries.mkdir(parents=True)
        manifest_path = registries / "manifest.hocon"
        manifest_path.write_text(json.dumps({"basic/coffee_finder.hocon": True}, indent=4) + "\n")

        importer = AgentNetworkImporter(str(tmp_path / "source"), str(target_dir))
        importer.update_manifest(["basic/music_nerd.hocon", "agent_network_designer.hocon"])

        merged = json.loads(manifest_path.read_text())
        assert merged == {
            "agent_network_designer.hocon": True,
            "basic/coffee_finder.hocon": True,
            "basic/music_nerd.hocon": True,
        }
        # Sorted on disk, not just by Python dict insertion.
        assert list(merged.keys()) == sorted(merged.keys())

    def test_update_manifest_creates_when_missing(self, tmp_path: Path) -> None:
        """update_manifest should write a fresh manifest when none exists yet."""
        target_dir = tmp_path / "target"
        importer = AgentNetworkImporter(str(tmp_path / "source"), str(target_dir))
        importer.update_manifest(["basic/music_nerd.hocon"])

        manifest_path = target_dir / "registries" / "manifest.hocon"
        assert json.loads(manifest_path.read_text()) == {"basic/music_nerd.hocon": True}
