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
import zipfile
from pathlib import Path

import pytest

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
