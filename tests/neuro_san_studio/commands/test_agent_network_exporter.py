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

"""Tests for AgentNetworkExporter (Phase 4: no-deps single-HOCON export)."""

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
        hocon.write_text(
            "{\n"
            '    "tools": [\n'
            '        { "name": "frontman", "class": "openai" }\n'
            "    ]\n"
            "}\n"
        )
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


class TestExportWithDepsErrors:
    """Phase 4 only handles the no-deps path; networks with deps must error cleanly."""

    def test_network_with_coded_tool_raises_until_zip_support_lands(self, tmp_path: Path) -> None:
        """A network referencing a coded tool can't be exported as a single hocon."""
        project_dir = tmp_path / "project"
        registries = project_dir / "registries" / "basic"
        registries.mkdir(parents=True)
        (project_dir / "registries" / "manifest.hocon").write_text("{}\n")
        # Network at registries/basic/music_nerd.hocon → analyzer's context_dir is
        # 'basic/music_nerd', so a short-form class ref like 'lookup.Lookup' is
        # resolved against coded_tools/basic/music_nerd/lookup.py.
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

        exporter = AgentNetworkExporter(project_dir=str(project_dir))
        with pytest.raises(ValueError, match="dependencies"):
            exporter.export("music_nerd")
