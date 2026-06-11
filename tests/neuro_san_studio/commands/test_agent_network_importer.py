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

import os
import zipfile
from pathlib import Path

import pytest
from neuro_san.internals.graph.persistence.raw_manifest_restorer import RawManifestRestorer

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.importer.agent_network_importer import AgentNetworkImporter


def _read_manifest_keys(manifest_path: Path) -> set:
    """Read a manifest.hocon (with possible includes) into a set of declared keys."""
    prev_cwd = os.getcwd()
    try:
        os.chdir(manifest_path.parent.parent)
        raw = RawManifestRestorer().restore(file_reference=str(manifest_path))
    finally:
        os.chdir(prev_cwd)
    return {key.strip('"') for key in raw if isinstance(key, str)}


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

    def test_sub_networks_are_registered_in_manifest_entries(self, tmp_path: Path) -> None:
        """import_network must record both the top-level network AND every sub-network for manifest registration.

        Regression case: an import of agent_network_designer (which has sub-networks) must
        end up registering the sub-networks in the receiver's manifest, not just the top-level.
        """
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        registries = source_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "agent_network_designer.hocon").write_text('{ "tools": [] }\n')
        (registries / "advanced_calculator.hocon").write_text('{ "tools": [] }\n')
        (registries / "agentforce_adapter.hocon").write_text('{ "tools": [] }\n')
        for shared in ("aaosa.hocon", "aaosa_basic.hocon", "aaosa_basic_debug.hocon"):
            (registries / shared).write_text("")

        importer = AgentNetworkImporter(str(source_dir), str(target_dir))
        deps = AgentNetworkDependencies(
            sub_networks=["/advanced_calculator", "/agentforce_adapter"],
        )
        result = importer.import_network("agent_network_designer.hocon", deps)

        assert "agent_network_designer.hocon" in result.manifest_entries
        assert "advanced_calculator.hocon" in result.manifest_entries
        assert "agentforce_adapter.hocon" in result.manifest_entries
        # Shared includes ride along on disk (line 86) but must NOT be registered as networks.
        assert "aaosa.hocon" not in result.manifest_entries
        assert "aaosa_basic.hocon" not in result.manifest_entries
        assert "aaosa_basic_debug.hocon" not in result.manifest_entries

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
        """update_manifest should add new entries while leaving existing ones intact."""
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        registries.mkdir(parents=True)
        manifest_path = registries / "manifest.hocon"
        manifest_path.write_text('{\n    "basic/coffee_finder.hocon": true\n}\n')

        importer = AgentNetworkImporter(str(tmp_path / "source"), str(target_dir))
        importer.update_manifest(["basic/music_nerd.hocon", "agent_network_designer.hocon"])

        merged = _read_manifest_keys(manifest_path)
        assert merged == {
            "agent_network_designer.hocon",
            "basic/coffee_finder.hocon",
            "basic/music_nerd.hocon",
        }

    def test_update_manifest_creates_when_missing(self, tmp_path: Path) -> None:
        """update_manifest should write a fresh manifest when none exists yet."""
        target_dir = tmp_path / "target"
        importer = AgentNetworkImporter(str(tmp_path / "source"), str(target_dir))
        importer.update_manifest(["basic/music_nerd.hocon"])

        manifest_path = target_dir / "registries" / "manifest.hocon"
        assert _read_manifest_keys(manifest_path) == {"basic/music_nerd.hocon"}

    def test_update_manifest_preserves_include_directive(self, tmp_path: Path) -> None:
        """The scaffolded `include "registries/generated/manifest.hocon"` line must survive imports.

        This is the regression case for the "import nukes my init scaffold" bug: an `ns init`
        manifest contains both a comment, an include directive, and a music_nerd entry, and a
        subsequent `ns import` must preserve all of that while adding new entries.
        """
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        registries.mkdir(parents=True)
        # Pre-create the included manifest so RawManifestRestorer doesn't choke on it.
        (registries / "generated").mkdir()
        (registries / "generated" / "manifest.hocon").write_text("{}\n")
        manifest_path = registries / "manifest.hocon"
        manifest_path.write_text(
            "{\n"
            "    # Networks created by `agent_network_designer` are written under registries/generated/.\n"
            "    # The include keeps them visible to the server without editing this file by hand.\n"
            '    include "registries/generated/manifest.hocon",\n'
            "\n"
            '    "music_nerd.hocon": true\n'
            "}\n"
        )

        importer = AgentNetworkImporter(str(tmp_path / "source"), str(target_dir))
        importer.update_manifest(["agent_network_designer.hocon", "advanced_calculator.hocon", "music_nerd.hocon"])

        text = manifest_path.read_text()
        # Verbatim preservation of the include + comments.
        assert 'include "registries/generated/manifest.hocon"' in text
        assert "# Networks created by `agent_network_designer`" in text
        # music_nerd.hocon was already declared — never duplicated, never re-emitted.
        assert text.count('"music_nerd.hocon"') == 1
        # Both new entries got registered.
        keys = _read_manifest_keys(manifest_path)
        assert "agent_network_designer.hocon" in keys
        assert "advanced_calculator.hocon" in keys
        assert "music_nerd.hocon" in keys

    def test_update_manifest_skips_entries_already_declared_via_include(self, tmp_path: Path) -> None:
        """An entry that's reachable through an `include` must not be re-added at the top level."""
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        (registries / "generated").mkdir(parents=True)
        # The included manifest declares one entry — the top-level merge must see it via the include.
        (registries / "generated" / "manifest.hocon").write_text('{\n    "generated/foo.hocon": true\n}\n')
        manifest_path = registries / "manifest.hocon"
        manifest_path.write_text('{\n    include "registries/generated/manifest.hocon"\n}\n')

        importer = AgentNetworkImporter(str(tmp_path / "source"), str(target_dir))
        importer.update_manifest(["generated/foo.hocon", "new_network.hocon"])

        text = manifest_path.read_text()
        # generated/foo.hocon must NOT be duplicated at the top — it's reachable via the include.
        assert text.count('"generated/foo.hocon"') == 0
        assert '"new_network.hocon": true' in text


class TestImportFromPath:
    """Tests for AgentNetworkImporter.import_from_path (single .hocon file)."""

    def test_import_lands_at_registries_root(self, tmp_path: Path) -> None:
        """A single .hocon file imports at <target>/registries/<basename>."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        source_file = tmp_path / "elsewhere" / "my_network.hocon"
        source_file.parent.mkdir()
        source_file.write_text('{ "tools": [] }\n')

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(source_file))

        landed = target_dir / "registries" / "my_network.hocon"
        assert landed.is_file()
        assert landed.read_text() == '{ "tools": [] }\n'
        assert result.copied_files == ["my_network.hocon"]
        assert result.hocon_path == "my_network.hocon"
        assert not result.errors

    def test_import_skips_when_target_exists(self, tmp_path: Path) -> None:
        """Existing target files are not overwritten and surface in skipped_files."""
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        registries.mkdir(parents=True)
        existing = registries / "my_network.hocon"
        existing.write_text("DO NOT OVERWRITE\n")
        source_file = tmp_path / "my_network.hocon"
        source_file.write_text('{ "new": true }\n')

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(source_file))

        assert existing.read_text() == "DO NOT OVERWRITE\n"
        assert result.skipped_files == ["my_network.hocon"]
        assert not result.copied_files

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        """A missing source path raises FileNotFoundError, not a silent skip."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        with pytest.raises(FileNotFoundError):
            importer.import_from_path(str(tmp_path / "missing.hocon"))

    def test_unsupported_suffix_raises(self, tmp_path: Path) -> None:
        """A non-.hocon source raises ValueError before any copy."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        source_file = tmp_path / "bundle.tar"
        source_file.write_text("not a hocon")

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        with pytest.raises(ValueError, match="Unsupported file type"):
            importer.import_from_path(str(source_file))


class TestImportFromZip:
    """Tests for AgentNetworkImporter.import_from_path with .zip bundles."""

    @staticmethod
    def _make_zip(zip_path: Path, entries: dict, *, symlink: tuple | None = None) -> None:
        """Build a zip from a {arcname: content_bytes} dict; optionally inject a symlink entry."""
        with zipfile.ZipFile(zip_path, "w") as zf:
            for arcname, content in entries.items():
                zf.writestr(arcname, content)
            if symlink is not None:
                arcname, target = symlink
                info = zipfile.ZipInfo(arcname)
                # 0o120000 = symlink mode bits in the high half of external_attr
                info.external_attr = (0o120777 & 0xFFFF) << 16
                zf.writestr(info, target)

    def test_zip_preserves_paths_and_lands_under_top_level_dirs(self, tmp_path: Path) -> None:
        """A well-formed zip extracts verbatim under registries/, coded_tools/, middleware/, skills/."""
        zip_path = tmp_path / "bundle.zip"
        self._make_zip(
            zip_path,
            {
                "registries/industry/airline_policy.hocon": b'{ "tools": [] }\n',
                "coded_tools/airline_policy/__init__.py": b"",
                "coded_tools/airline_policy/lookup.py": b"def lookup(): pass\n",
                "middleware/airline_policy/logger.py": b"class L: pass\n",
                "skills/airline_policy/skill.py": b"class S: pass\n",
            },
        )
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(zip_path))

        # Grouped registry paths stay grouped — the archive layout is the contract.
        assert (target_dir / "registries" / "industry" / "airline_policy.hocon").is_file()
        assert (target_dir / "coded_tools" / "airline_policy" / "lookup.py").is_file()
        assert (target_dir / "middleware" / "airline_policy" / "logger.py").is_file()
        assert (target_dir / "skills" / "airline_policy" / "skill.py").is_file()
        assert "registries/industry/airline_policy.hocon" in result.copied_files
        assert not result.errors

    def test_zip_does_not_register_shared_includes_in_manifest_entries(self, tmp_path: Path) -> None:
        """Shared registry fragments (aaosa.hocon, etc.) are substitution files, not networks.

        Regression case: a zip that ships aaosa.hocon alongside a real network must register
        only the network. Registering aaosa.hocon as an agent network would crash neuro-san at
        startup because the validator iterates the file expecting agent specs and finds a string.
        """
        zip_path = tmp_path / "bundle.zip"
        self._make_zip(
            zip_path,
            {
                "registries/generated/indie_bookshop_ops.hocon": b'{ "tools": [] }\n',
                "registries/aaosa.hocon": b'{ "aaosa_instructions": "..." }\n',
                "registries/aaosa_basic.hocon": b'{ "aaosa_call": {} }\n',
            },
        )
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(zip_path))

        assert "generated/indie_bookshop_ops.hocon" in result.manifest_entries
        assert "aaosa.hocon" not in result.manifest_entries
        assert "aaosa_basic.hocon" not in result.manifest_entries
        # Files still land on disk — they're needed for the include directives to resolve.
        assert (target_dir / "registries" / "aaosa.hocon").is_file()
        assert (target_dir / "registries" / "aaosa_basic.hocon").is_file()

    def test_single_hocon_shared_include_does_not_register_in_manifest(self, tmp_path: Path) -> None:
        """`ns import aaosa.hocon` should land the file but not pollute the manifest."""
        source = tmp_path / "aaosa.hocon"
        source.write_text('{ "aaosa_instructions": "..." }\n')
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(source))

        assert (target_dir / "registries" / "aaosa.hocon").is_file()
        assert "aaosa.hocon" not in result.manifest_entries

    def test_zip_slip_is_rejected_before_any_write(self, tmp_path: Path) -> None:
        """An entry with `..` path components must be rejected without leaving partial output."""
        zip_path = tmp_path / "evil.zip"
        self._make_zip(
            zip_path,
            {
                "registries/safe.hocon": b'{ "tools": [] }\n',
                "../../../../etc/pwn.txt": b"pwned\n",
            },
        )
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        with pytest.raises(ValueError, match="zip-slip"):
            importer.import_from_path(str(zip_path))
        # All-or-nothing: even the safe entry must not have been written.
        assert not (target_dir / "registries" / "safe.hocon").exists()

    def test_zip_rejects_entry_outside_whitelist(self, tmp_path: Path) -> None:
        """A path that isn't under registries/coded_tools/middleware/skills is rejected."""
        zip_path = tmp_path / "stray.zip"
        self._make_zip(zip_path, {"docs/README.md": b"# stray\n"})
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        with pytest.raises(ValueError, match="not in whitelist"):
            importer.import_from_path(str(zip_path))

    def test_zip_rejects_symlink_entries(self, tmp_path: Path) -> None:
        """A zip entry whose mode bits indicate a symlink must be refused."""
        zip_path = tmp_path / "linky.zip"
        self._make_zip(
            zip_path,
            {"registries/safe.hocon": b'{ "tools": [] }\n'},
            symlink=("registries/evil_link", "/etc/passwd"),
        )
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        with pytest.raises(ValueError, match="symlink"):
            importer.import_from_path(str(zip_path))

    def test_zip_skips_macos_metadata_and_pycache(self, tmp_path: Path) -> None:
        """__MACOSX/, .DS_Store, and __pycache__ entries must not pollute the receiver's tree."""
        zip_path = tmp_path / "noisy.zip"
        self._make_zip(
            zip_path,
            {
                "registries/basic/foo.hocon": b'{ "tools": [] }\n',
                "registries/.DS_Store": b"\x00mac",
                "__MACOSX/registries/._foo.hocon": b"\x00apple",
                "coded_tools/foo/__init__.py": b"",
                "coded_tools/foo/bar.py": b"def bar(): pass\n",
                "coded_tools/foo/__pycache__/bar.cpython-314.pyc": b"\x00bytecode",
            },
        )
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(zip_path))

        assert (target_dir / "registries" / "basic" / "foo.hocon").is_file()
        assert (target_dir / "coded_tools" / "foo" / "bar.py").is_file()
        # Metadata must not leak into the tree.
        assert not (target_dir / "registries" / ".DS_Store").exists()
        assert not (target_dir / "__MACOSX").exists()
        assert not (target_dir / "coded_tools" / "foo" / "__pycache__").exists()
        # And it shouldn't be reported as "copied" either — the count must reflect reality.
        assert all(".DS_Store" not in p and "__pycache__" not in p for p in result.copied_files)

    def test_zip_skips_existing_files(self, tmp_path: Path) -> None:
        """Pre-existing target files are not overwritten and surface in skipped_files."""
        zip_path = tmp_path / "bundle.zip"
        self._make_zip(zip_path, {"registries/foo.hocon": b'{ "new": true }\n'})
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "foo.hocon").write_text("DO NOT OVERWRITE\n")

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(zip_path))

        assert (registries / "foo.hocon").read_text() == "DO NOT OVERWRITE\n"
        assert "registries/foo.hocon" in result.skipped_files
        assert "registries/foo.hocon" not in result.copied_files


class TestMcpInfoMerge:
    """MCP info merging on import — both discovery-driven (import_network) and zip (import_from_path)."""

    def test_discovery_import_pulls_mcp_blocks_from_source(self, tmp_path: Path) -> None:
        """import_network with mcp_tools deps copies only those URL blocks from the source mcp_info."""
        source_dir = tmp_path / "source"
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (source_dir / "registries" / "basic").mkdir(parents=True)
        (source_dir / "registries" / "basic" / "mcp_user.hocon").write_text('{ "tools": [] }\n')
        for shared in ("aaosa.hocon", "aaosa_basic.hocon", "aaosa_basic_debug.hocon"):
            (source_dir / "registries" / shared).write_text("")
        (source_dir / "mcp").mkdir()
        (source_dir / "mcp" / "mcp_info.hocon").write_text(
            '{\n    "https://mcp.deepwiki.com/mcp": {\n        "tools": ["read_wiki_structure"]\n    }\n}\n'
        )

        importer = AgentNetworkImporter(str(source_dir), str(target_dir))
        deps = AgentNetworkDependencies(mcp_tools=["https://mcp.deepwiki.com/mcp"])
        result = importer.import_network("basic/mcp_user.hocon", deps)

        merged = (target_dir / "mcp" / "mcp_info.hocon").read_text()
        assert "https://mcp.deepwiki.com/mcp" in merged
        assert "https://mcp.deepwiki.com/mcp" in result.mcp_added

    def test_zip_import_merges_mcp_info_additively(self, tmp_path: Path) -> None:
        """A zip-bundled mcp_info.hocon is merged into the receiver — never replacing existing URLs."""
        zip_path = tmp_path / "bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("registries/foo.hocon", '{ "tools": [] }\n')
            zf.writestr(
                "mcp/mcp_info.hocon",
                '{\n    "https://new.example.com/mcp": { "tools": ["t"] }\n}\n',
            )
        target_dir = tmp_path / "target"
        (target_dir / "mcp").mkdir(parents=True)
        # Receiver already has one URL configured with an env-var header — must survive verbatim.
        existing = (
            "{\n"
            '    "https://existing.example.com/mcp": {\n'
            '        "http_headers": { "Authorization": "Bearer "${MY_TOKEN} }\n'
            "    }\n"
            "}\n"
        )
        (target_dir / "mcp" / "mcp_info.hocon").write_text(existing)

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(zip_path))

        merged = (target_dir / "mcp" / "mcp_info.hocon").read_text()
        assert "https://existing.example.com/mcp" in merged
        assert "${MY_TOKEN}" in merged  # env-var ref preserved verbatim
        assert "https://new.example.com/mcp" in merged
        assert "https://new.example.com/mcp" in result.mcp_added

    def test_zip_import_skips_already_present_mcp_url(self, tmp_path: Path) -> None:
        """A bundled mcp_info entry whose URL is already configured is skipped (no overwrite, ever)."""
        zip_path = tmp_path / "bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("registries/foo.hocon", '{ "tools": [] }\n')
            zf.writestr(
                "mcp/mcp_info.hocon",
                '{\n    "https://shared.example.com/mcp": { "tools": ["replacement"] }\n}\n',
            )
        target_dir = tmp_path / "target"
        (target_dir / "mcp").mkdir(parents=True)
        original = '{\n    "https://shared.example.com/mcp": { "tools": ["original"] }\n}\n'
        (target_dir / "mcp" / "mcp_info.hocon").write_text(original)

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        # Force=True must NOT override the additive contract for mcp_info — the receiver's
        # existing URL config wins, even on force.
        result = importer.import_from_path(str(zip_path), force=True)

        merged = (target_dir / "mcp" / "mcp_info.hocon").read_text()
        assert '"original"' in merged
        assert '"replacement"' not in merged
        assert "https://shared.example.com/mcp" in result.mcp_skipped


class TestForceOverwrite:
    """Tests for the --force flag, which makes import_network and import_from_path overwrite existing files."""

    @staticmethod
    def _make_zip(zip_path: Path, entries: dict) -> None:
        """Build a zip from a {arcname: content_bytes} dict."""
        with zipfile.ZipFile(zip_path, "w") as zf:
            for arcname, content in entries.items():
                zf.writestr(arcname, content)

    def test_force_overwrites_existing_single_hocon(self, tmp_path: Path) -> None:
        """import_from_path with force=True replaces existing single-hocon files."""
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "my_network.hocon").write_text("OLD\n")
        source_file = tmp_path / "my_network.hocon"
        source_file.write_text("NEW\n")

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(source_file), force=True)

        assert (registries / "my_network.hocon").read_text() == "NEW\n"
        assert "my_network.hocon" in result.copied_files
        assert not result.skipped_files

    def test_force_overwrites_existing_zip_entries(self, tmp_path: Path) -> None:
        """import_from_path on a zip with force=True overwrites pre-existing target files."""
        zip_path = tmp_path / "bundle.zip"
        self._make_zip(zip_path, {"registries/foo.hocon": b"NEW\n"})
        target_dir = tmp_path / "target"
        registries = target_dir / "registries"
        registries.mkdir(parents=True)
        (registries / "foo.hocon").write_text("OLD\n")

        importer = AgentNetworkImporter(str(target_dir), str(target_dir))
        result = importer.import_from_path(str(zip_path), force=True)

        assert (registries / "foo.hocon").read_text() == "NEW\n"
        assert "registries/foo.hocon" in result.copied_files
        assert "registries/foo.hocon" not in result.skipped_files

    def test_force_overwrites_in_discovery_driven_import(self, tmp_path: Path) -> None:
        """import_network with force=True replaces an existing HOCON in the registry-driven flow."""
        source_dir = tmp_path / "source"
        registries = source_dir / "registries" / "basic"
        registries.mkdir(parents=True)
        (registries / "music_nerd.hocon").write_text("NEW\n")
        # SHARED_INCLUDES are always copied; create empty stand-ins so import_network doesn't warn.
        for shared in ("aaosa.hocon", "aaosa_basic.hocon", "aaosa_basic_debug.hocon"):
            (source_dir / "registries" / shared).write_text("")

        target_dir = tmp_path / "target"
        target_basic = target_dir / "registries" / "basic"
        target_basic.mkdir(parents=True)
        (target_basic / "music_nerd.hocon").write_text("OLD\n")

        importer = AgentNetworkImporter(str(source_dir), str(target_dir))
        result = importer.import_network("basic/music_nerd.hocon", AgentNetworkDependencies(), force=True)

        assert (target_basic / "music_nerd.hocon").read_text() == "NEW\n"
        assert "basic/music_nerd.hocon" in result.copied_files
        assert "basic/music_nerd.hocon" not in result.skipped_files
