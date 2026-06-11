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

"""Tests for AgentNetworkExporter (no-deps single-HOCON and zip output paths)."""

import zipfile
from pathlib import Path

import pytest

from neuro_san_studio.exporter.agent_network_exporter import AgentNetworkExporter


class TestExportNoDeps:
    """Single-HOCON export: networks whose 'tools' array references no coded tools / middleware."""

    @staticmethod
    def _build_no_deps_project(project_dir: Path, *, group: str = "basic", name: str = "music_nerd") -> Path:
        """Lay out a minimal project with one no-deps network. Returns the network's full path."""
        registries = project_dir / "registries"
        (registries / group).mkdir(parents=True)
        manifest = registries / "manifest.hocon"
        manifest.write_text("{}\n")
        # An LLM-only `tools` entry — `openai` is in LLM_CLASSES so the analyzer treats
        # it as a model reference rather than a coded-tool dependency.
        hocon = registries / group / f"{name}.hocon"
        hocon.write_text('{\n    "tools": [\n        { "name": "frontman", "class": "openai" }\n    ]\n}\n')
        return hocon

    def test_export_writes_hocon_to_default_cwd_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No -o → write to <cwd>/<basename>.hocon."""
        self._build_no_deps_project(tmp_path / "project")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.chdir(out_dir)

        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        result = exporter.export("music_nerd")

        landed = out_dir / "music_nerd.hocon"
        assert landed.is_file()
        assert result.output_path == str(landed)
        assert result.network_name == "music_nerd"

    def test_export_respects_explicit_output_path(self, tmp_path: Path) -> None:
        """-o foo.hocon → write to that exact path."""
        self._build_no_deps_project(tmp_path / "project")
        target = tmp_path / "shared" / "my_export.hocon"

        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        result = exporter.export("music_nerd", output_path=str(target))

        assert target.is_file()
        assert result.output_path == str(target)

    def test_export_resolves_grouped_relative_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Passing 'basic/music_nerd' resolves directly without the bare-name walk."""
        self._build_no_deps_project(tmp_path / "project")
        monkeypatch.chdir(tmp_path)

        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        result = exporter.export("basic/music_nerd")

        assert (tmp_path / "music_nerd.hocon").is_file()
        assert result.network_name == "music_nerd"

    def test_export_strips_registries_prefix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A repo-root-style 'registries/basic/music_nerd.hocon' resolves like 'basic/music_nerd'."""
        self._build_no_deps_project(tmp_path / "project")
        monkeypatch.chdir(tmp_path)

        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        result = exporter.export("registries/basic/music_nerd.hocon")

        assert (tmp_path / "music_nerd.hocon").is_file()
        assert result.network_name == "music_nerd"
        # The stripped path stays registries-relative — the bundled-files key must not
        # double up the prefix (would be 'registries/registries/...' if stripping leaked).
        assert result.bundled_files == ["registries/basic/music_nerd.hocon"]

    def test_export_strips_dot_slash_registries_prefix(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A './registries/...' spelling normalizes to the same registries-relative path."""
        self._build_no_deps_project(tmp_path / "project")
        monkeypatch.chdir(tmp_path)

        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        result = exporter.export("./registries/basic/music_nerd.hocon")

        assert (tmp_path / "music_nerd.hocon").is_file()
        assert result.network_name == "music_nerd"

    def test_missing_network_raises_filenotfound(self, tmp_path: Path) -> None:
        """An unknown network name surfaces FileNotFoundError, not a silent empty export."""
        self._build_no_deps_project(tmp_path / "project")
        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        with pytest.raises(FileNotFoundError, match="not found"):
            exporter.export("nonexistent_network")

    def test_zip_suffix_rejected_when_no_deps(self, tmp_path: Path) -> None:
        """A no-deps network with -o foo.zip is rejected — zip is for the deps case."""
        self._build_no_deps_project(tmp_path / "project")
        target = tmp_path / "out.zip"
        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        with pytest.raises(ValueError, match="no dependencies"):
            exporter.export("music_nerd", output_path=str(target))


class TestExportWithDeps:
    """Networks with deps export as a .zip carrying network + sub-networks + coded_tools + middleware."""

    @staticmethod
    def _build_project_with_coded_tool(project_dir: Path) -> None:
        """Lay out a project with a single network that references one coded tool."""
        registries = project_dir / "registries" / "basic"
        registries.mkdir(parents=True)
        (project_dir / "registries" / "manifest.hocon").write_text("{}\n")
        # Analyzer's context_dir for registries/basic/music_nerd.hocon is "basic/music_nerd".
        coded_tools = project_dir / "coded_tools" / "basic" / "music_nerd"
        coded_tools.mkdir(parents=True)
        (coded_tools / "__init__.py").write_text("")
        (coded_tools / "lookup.py").write_text("class Lookup:\n    pass\n")
        (registries / "music_nerd.hocon").write_text(
            "{\n"
            '    "tools": [\n'
            '        { "name": "frontman", "class": "openai" },\n'
            '        { "name": "lookup", "class": "lookup.Lookup" }\n'
            "    ]\n"
            "}\n"
        )

    def test_zip_bundles_network_and_coded_tool(self, tmp_path: Path) -> None:
        """A network with one coded tool produces a zip carrying both files plus parent __init__.py."""
        project_dir = tmp_path / "project"
        self._build_project_with_coded_tool(project_dir)
        target = tmp_path / "out" / "music_nerd.zip"

        exporter = AgentNetworkExporter(project_dir=str(project_dir))
        result = exporter.export("music_nerd", output_path=str(target))

        assert target.is_file()
        with zipfile.ZipFile(target) as zf:
            names = set(zf.namelist())
        assert "registries/basic/music_nerd.hocon" in names
        assert "coded_tools/basic/music_nerd/lookup.py" in names
        # Parent __init__.py rides along so the package imports cleanly in the receiver.
        assert "coded_tools/basic/music_nerd/__init__.py" in names
        assert result.dependencies.coded_tools == ["coded_tools/basic/music_nerd/lookup.py"]
        assert not result.warnings

    def test_default_output_is_zip_when_deps_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Omitting -o on a deps network defaults to <name>.zip in cwd."""
        self._build_project_with_coded_tool(tmp_path / "project")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        monkeypatch.chdir(out_dir)

        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        result = exporter.export("music_nerd")

        landed = out_dir / "music_nerd.zip"
        assert landed.is_file()
        assert result.output_path == str(landed)
        with zipfile.ZipFile(landed) as zf:
            assert any(n.endswith("music_nerd.hocon") for n in zf.namelist())

    def test_hocon_suffix_rejected_when_deps_exist(self, tmp_path: Path) -> None:
        """A deps network with -o foo.hocon is rejected up front, no partial output."""
        self._build_project_with_coded_tool(tmp_path / "project")
        target = tmp_path / "music_nerd.hocon"
        exporter = AgentNetworkExporter(project_dir=str(tmp_path / "project"))
        with pytest.raises(ValueError, match="cannot export to '.hocon'"):
            exporter.export("music_nerd", output_path=str(target))
        assert not target.exists()

    def test_zip_includes_sub_networks(self, tmp_path: Path) -> None:
        """A network referencing a sub-network bundles both hocons under registries/."""
        project_dir = tmp_path / "project"
        registries = project_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "manifest.hocon").write_text("{}\n")
        # Parent network points to a sub-network at registries/sub_helper.hocon.
        (registries / "parent_net.hocon").write_text(
            "{\n"
            '    "tools": [\n'
            '        { "name": "frontman", "class": "openai", "tools": ["/sub_helper"] }\n'
            "    ]\n"
            "}\n"
        )
        (registries / "sub_helper.hocon").write_text(
            '{\n    "tools": [\n        { "name": "helper", "class": "openai" }\n    ]\n}\n'
        )

        exporter = AgentNetworkExporter(project_dir=str(project_dir))
        target = tmp_path / "parent_net.zip"
        result = exporter.export("parent_net", output_path=str(target))

        with zipfile.ZipFile(target) as zf:
            names = set(zf.namelist())
        assert "registries/parent_net.hocon" in names
        assert "registries/sub_helper.hocon" in names
        assert "/sub_helper" in result.dependencies.sub_networks

    def test_zip_walks_hocon_includes_for_aaosa(self, tmp_path: Path) -> None:
        """A network with `include "registries/aaosa.hocon"` bundles the include verbatim."""
        project_dir = tmp_path / "project"
        registries = project_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "manifest.hocon").write_text("{}\n")
        (registries / "aaosa.hocon").write_text("# aaosa shared\n")
        # Network references aaosa via include directive AND has a coded-tool dep so
        # we end up on the zip path.
        (project_dir / "coded_tools" / "tooled").mkdir(parents=True)
        (project_dir / "coded_tools" / "tooled" / "lookup.py").write_text("class Lookup: pass\n")
        (registries / "tooled.hocon").write_text(
            'include "registries/aaosa.hocon"\n'
            "{\n"
            '    "tools": [\n'
            '        { "name": "frontman", "class": "openai" },\n'
            '        { "name": "lookup", "class": "tooled.lookup.Lookup" }\n'
            "    ]\n"
            "}\n"
        )

        exporter = AgentNetworkExporter(project_dir=str(project_dir))
        target = tmp_path / "tooled.zip"
        result = exporter.export("tooled", output_path=str(target))

        with zipfile.ZipFile(target) as zf:
            names = set(zf.namelist())
        assert "registries/aaosa.hocon" in names
        assert "aaosa.hocon" in result.shared_includes

    def test_zip_walks_recursive_sub_networks(self, tmp_path: Path) -> None:
        """Sub-network → sub-sub-network chains: the analyzer recurses, the exporter bundles all hops."""
        project_dir = tmp_path / "project"
        registries = project_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "manifest.hocon").write_text("{}\n")
        # parent → mid → leaf, with `leaf` carrying its own coded_tool.
        (registries / "parent.hocon").write_text(
            '{ "tools": [{ "name": "f", "class": "openai", "tools": ["/mid"] }] }\n'
        )
        (registries / "mid.hocon").write_text(
            '{ "tools": [{ "name": "f", "class": "openai", "tools": ["/leaf"] }] }\n'
        )
        leaf_tools = project_dir / "coded_tools" / "leaf"
        leaf_tools.mkdir(parents=True)
        (leaf_tools / "lookup.py").write_text("class Lookup: pass\n")
        (registries / "leaf.hocon").write_text(
            "{\n"
            '    "tools": [\n'
            '        { "name": "f", "class": "openai" },\n'
            '        { "name": "lookup", "class": "leaf.lookup.Lookup" }\n'
            "    ]\n"
            "}\n"
        )

        exporter = AgentNetworkExporter(project_dir=str(project_dir))
        target = tmp_path / "parent.zip"
        result = exporter.export("parent", output_path=str(target))

        with zipfile.ZipFile(target) as zf:
            names = set(zf.namelist())
        # Every hop in the chain rides along.
        assert "registries/parent.hocon" in names
        assert "registries/mid.hocon" in names
        assert "registries/leaf.hocon" in names
        # Leaf's coded_tool comes too — proving transitive resolution worked end-to-end.
        assert "coded_tools/leaf/lookup.py" in names
        assert "/mid" in result.dependencies.sub_networks
        assert "/leaf" in result.dependencies.sub_networks

    def test_zip_bundles_mcp_info(self, tmp_path: Path) -> None:
        """A network referencing MCP URLs gets a mcp/mcp_info.hocon in the zip with the
        URLs the network actually uses."""
        project_dir = tmp_path / "project"
        registries = project_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "manifest.hocon").write_text("{}\n")
        (registries / "mcp_user.hocon").write_text(
            "{\n"
            '    "tools": [\n'
            '        { "name": "frontman", "class": "openai", "tools": ["https://mcp.deepwiki.com/mcp"] }\n'
            "    ]\n"
            "}\n"
        )
        (project_dir / "mcp").mkdir()
        (project_dir / "mcp" / "mcp_info.hocon").write_text(
            "{\n"
            '    "https://mcp.deepwiki.com/mcp": {\n'
            '        "tools": ["read_wiki_structure", "ask_question"]\n'
            "    }\n"
            "}\n"
        )

        exporter = AgentNetworkExporter(project_dir=str(project_dir))
        target = tmp_path / "mcp_user.zip"
        result = exporter.export("mcp_user", output_path=str(target))

        with zipfile.ZipFile(target) as zf:
            names = set(zf.namelist())
            mcp_payload = zf.read("mcp/mcp_info.hocon").decode("utf-8")
        assert "mcp/mcp_info.hocon" in names
        assert "https://mcp.deepwiki.com/mcp" in mcp_payload
        assert result.bundled_mcp_urls == ["https://mcp.deepwiki.com/mcp"]
        assert "https://mcp.deepwiki.com/mcp" in result.dependencies.mcp_tools

    def test_export_with_only_mcp_dep_produces_zip(self, tmp_path: Path) -> None:
        """An MCP-only network still exports as .zip so we can ship the filtered mcp_info."""
        project_dir = tmp_path / "project"
        registries = project_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "manifest.hocon").write_text("{}\n")
        (registries / "mcp_only.hocon").write_text(
            "{\n"
            '    "tools": [\n'
            '        { "name": "frontman", "class": "openai", "tools": ["https://mcp.deepwiki.com/mcp"] }\n'
            "    ]\n"
            "}\n"
        )
        (project_dir / "mcp").mkdir()
        (project_dir / "mcp" / "mcp_info.hocon").write_text(
            '{\n    "https://mcp.deepwiki.com/mcp": { "tools": ["x"] }\n}\n'
        )

        exporter = AgentNetworkExporter(project_dir=str(project_dir))
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = exporter.export("mcp_only", output_path=str(out_dir / "mcp_only.zip"))

        landed = out_dir / "mcp_only.zip"
        assert landed.is_file()
        assert result.output_path == str(landed)

    def test_round_trip_via_import_from_path(self, tmp_path: Path) -> None:
        """Exported zip imports cleanly into a fresh project and lands every file."""
        # pylint: disable-next=import-outside-toplevel
        from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter

        project_dir = tmp_path / "src_project"
        self._build_project_with_coded_tool(project_dir)
        bundle = tmp_path / "music_nerd.zip"
        AgentNetworkExporter(project_dir=str(project_dir)).export("music_nerd", output_path=str(bundle))

        # Receiver project — only an empty manifest, nothing else.
        recv = tmp_path / "recv_project"
        (recv / "registries").mkdir(parents=True)
        (recv / "registries" / "manifest.hocon").write_text("{}\n")

        importer = AgentNetworkImporter(str(recv), str(recv))
        result = importer.import_from_path(str(bundle))

        assert (recv / "registries" / "basic" / "music_nerd.hocon").is_file()
        assert (recv / "coded_tools" / "basic" / "music_nerd" / "lookup.py").is_file()
        assert (recv / "coded_tools" / "basic" / "music_nerd" / "__init__.py").is_file()
        assert "registries/basic/music_nerd.hocon" in result.copied_files
