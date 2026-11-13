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

import zipfile
from pathlib import Path

from pyhocon import ConfigFactory

from neuro_san_studio.exporter.agent_network_exporter import AgentNetworkExporter
from neuro_san_studio.exporter.export_metadata import ExportMetadataStamper

_EXPORT_KEYS = {"export_user", "export_time", "export_neuro_san_studio_version"}


class TestBuildExportMetadata:
    """The provenance keys assembled at export time."""

    def test_has_the_three_export_keys(self) -> None:
        """build() returns exactly the user, time, and version keys."""
        assert set(ExportMetadataStamper().build()) == _EXPORT_KEYS

    def test_time_uses_yyyymmdd_hhmmss_tz_format(self) -> None:
        """export_time is YYYYMMDD-hhmmss-TZ: 8 date digits, 6 time digits, non-empty tz label."""
        date_part, time_part, tz_part = ExportMetadataStamper().build()["export_time"].split("-", 2)
        assert len(date_part) == 8 and date_part.isdigit()
        assert date_part.startswith("20")  # YYYY leads (e.g. 2026...), not DD
        assert len(time_part) == 6 and time_part.isdigit()
        assert tz_part

    def test_version_is_non_empty(self) -> None:
        """export_neuro_san_studio_version carries the bare studio version string."""
        assert built_version(ExportMetadataStamper().build())


class TestStamp:
    """Injecting the provenance keys into a network's HOCON text."""

    def test_merges_into_existing_metadata_block(self) -> None:
        """Existing metadata keys survive and the export keys are added to the same block."""
        text = (
            "{\n"
            '    "metadata": {\n'
            '        "description": "orig",\n'
            '        "sample_queries": ["q1"]\n'
            "    },\n"
            '    "tools": []\n'
            "}\n"
        )
        stamped = ExportMetadataStamper().stamp(text)

        # Exactly one metadata block, and it parses.
        assert stamped.count('"metadata"') == 1
        config = ConfigFactory.parse_string(stamped)
        assert config["metadata"]["description"] == "orig"
        assert list(config["metadata"]["sample_queries"]) == ["q1"]
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))
        # Export keys are appended after the existing keys, not prepended.
        assert stamped.index('"sample_queries"') < stamped.index('"export_user"')

    def test_creates_metadata_block_when_absent(self) -> None:
        """A network without metadata gets a new block carrying the export keys."""
        text = '{\n    "tools": []\n}\n'
        stamped = ExportMetadataStamper().stamp(text)

        config = ConfigFactory.parse_string(stamped)
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))

    def test_brace_less_network_without_metadata_prepends_top_level_block(self) -> None:
        """A brace-less network (top-level ``key = ...``) gets metadata as a sibling key,
        not injected inside the first tool object."""
        text = 'tools = [\n    { "name": "frontman", "class": "openai" }\n]\n'
        stamped = ExportMetadataStamper().stamp(text)

        config = ConfigFactory.parse_string(stamped)
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))
        # The block lands at the network root, leaving the tool object untouched.
        assert len(list(config["tools"])) == 1
        assert config["tools"][0]["name"] == "frontman"
        assert "export_user" not in config["tools"][0]

    def test_brace_less_network_with_metadata_updates_in_place(self) -> None:
        """A brace-less network that already has a metadata block is updated in place."""
        text = 'metadata {\n    tags = ["a"]\n}\ntools = [\n    { "name": "f", "class": "openai" }\n]\n'
        stamped = ExportMetadataStamper().stamp(text)

        assert stamped.count("metadata {") == 1
        config = ConfigFactory.parse_string(stamped)
        assert list(config["metadata"]["tags"]) == ["a"]
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))

    def test_injects_explanatory_comment_above_keys(self) -> None:
        """A HOCON comment describing the keys is injected and does not break parsing."""
        text = '{\n    "tools": []\n}\n'
        stamped = ExportMetadataStamper().stamp(text)

        assert "# ns export metadata" in stamped
        comment_at = stamped.index("# ns export metadata")
        first_key_at = stamped.index('"export_user"')
        assert comment_at < first_key_at  # comment sits above the keys
        # Comment lines are HOCON-legal: the block still parses and yields the keys.
        config = ConfigFactory.parse_string(stamped)
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))

    def test_key_indent_follows_the_metadata_line(self) -> None:
        """Injected keys sit one level in from the ``metadata`` line, whatever its own indent."""
        # `metadata` at column 0 (unquoted, `=`-style): keys should land at one level (4 spaces).
        col0 = 'metadata {\n    tags = ["a"]\n}\ntools = []\n'
        stamped = ExportMetadataStamper().stamp(col0)
        assert '\n    "export_user":' in stamped
        assert '\n        "export_user":' not in stamped
        ConfigFactory.parse_string(stamped)

        # Nested `"metadata"` at one level: keys should land at two levels (8 spaces).
        nested = '{\n    "metadata": {\n        "tags": ["a"]\n    }\n}\n'
        stamped = ExportMetadataStamper().stamp(nested)
        assert '\n        "export_user":' in stamped
        ConfigFactory.parse_string(stamped)

    def test_nested_sub_dicts_and_tricky_values_are_handled(self) -> None:
        """Sub-dicts and braces/'#' inside string values must not break block detection."""
        text = (
            "{\n"
            '    "metadata": {\n'
            '        "description": "has { } and # inside",\n'
            '        "nested": { "deep": { "x": 1 }, "y": "z" },\n'
            '        "tags": ["a"]\n'
            "    },\n"
            '    "tools": []\n'
            "}\n"
        )
        stamped = ExportMetadataStamper().stamp(text)

        config = ConfigFactory.parse_string(stamped)
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))
        assert "export_user" not in config  # not leaked to the root
        assert config["metadata"]["nested"]["deep"]["x"] == 1  # sub-dict intact
        assert "{ } and # inside" in config["metadata"]["description"]

    def test_lists_and_brackets_in_values_do_not_break_detection(self) -> None:
        """Lists ([]), and stray brace/bracket characters inside query strings, are handled."""
        text = (
            "{\n"
            '    "metadata": {\n'
            '        "tags": ["a", "b"],\n'
            '        "sample_queries": [\n'
            '            "a closing brace } in text",\n'
            '            "an open bracket [ here"\n'
            "        ]\n"
            "    },\n"
            '    "tools": []\n'
            "}\n"
        )
        stamped = ExportMetadataStamper().stamp(text)

        config = ConfigFactory.parse_string(stamped)
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))
        assert "export_user" not in config  # not leaked past the metadata block
        assert len(list(config["metadata"]["sample_queries"])) == 2
        assert list(config["metadata"]["tags"]) == ["a", "b"]

    def test_restamping_updates_in_place_without_duplicating(self) -> None:
        """Re-stamping an already-stamped network refreshes values, never duplicates keys."""
        text = '{\n    "metadata": {\n        "description": "orig"\n    },\n    "tools": []\n}\n'
        stamper = ExportMetadataStamper()
        once = stamper.stamp(text)
        twice = stamper.stamp(once)

        for key in _EXPORT_KEYS:
            assert twice.count(f'"{key}"') == 1
        assert twice.count("# ns export metadata") == 1
        config = ConfigFactory.parse_string(twice)
        assert config["metadata"]["description"] == "orig"
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))

    def test_preserves_includes_and_substitutions(self) -> None:
        """Include directives and ${substitutions} outside metadata are left untouched."""
        text = (
            'include "registries/aaosa.hocon"\n'
            "{\n"
            '    "metadata": { "description": "orig" },\n'
            '    "instructions": ${aaosa_instructions}\n'
            "}\n"
        )
        stamped = ExportMetadataStamper().stamp(text)

        # The include line and the substitution are carried through verbatim, the original
        # metadata key stays, and the export keys are spliced in.
        assert 'include "registries/aaosa.hocon"' in stamped
        assert "${aaosa_instructions}" in stamped
        assert '"description": "orig"' in stamped
        for key in _EXPORT_KEYS:
            assert f'"{key}"' in stamped


class TestExportStampsMetadata:
    """End-to-end: every exported network carries the export keys in its top-level metadata."""

    @staticmethod
    def _write_network(project_dir: Path, body: str, *, group: str = "basic", name: str = "muse") -> None:
        """Lay out a minimal project with one network whose HOCON body is `body`."""
        registries = project_dir / "registries" / group
        registries.mkdir(parents=True)
        (project_dir / "registries" / "manifest.hocon").write_text("{}\n")
        (registries / f"{name}.hocon").write_text(body)

    def test_no_deps_export_stamps_metadata(self, tmp_path: Path) -> None:
        """A no-deps .hocon export gains the three export_* keys."""
        self._write_network(tmp_path / "project", '{\n    "tools": [{ "name": "f", "class": "openai" }]\n}\n')
        target = tmp_path / "muse.hocon"

        AgentNetworkExporter(project_dir=str(tmp_path / "project")).export("muse", output_path=str(target))

        config = ConfigFactory.parse_file(str(target))
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))

    def test_zip_export_stamps_metadata(self, tmp_path: Path) -> None:
        """The primary network inside a deps .zip gains the three export_* keys."""
        project = tmp_path / "project"
        self._write_network(
            project,
            '{\n    "tools": [{ "name": "f", "class": "openai" }, { "name": "t", "class": "lookup.Lookup" }]\n}\n',
        )
        coded = project / "coded_tools" / "basic" / "muse"
        coded.mkdir(parents=True)
        (coded / "__init__.py").write_text("")
        (coded / "lookup.py").write_text("class Lookup:\n    pass\n")
        target = tmp_path / "muse.zip"

        AgentNetworkExporter(project_dir=str(project)).export("muse", output_path=str(target))

        with zipfile.ZipFile(target) as zf:
            hocon_text = zf.read("registries/basic/muse.hocon").decode("utf-8")
        config = ConfigFactory.parse_string(hocon_text)
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))

    def test_existing_metadata_preserved_in_one_block(self, tmp_path: Path) -> None:
        """A network that already has metadata keeps those keys and stays a single block."""
        self._write_network(
            tmp_path / "project",
            "{\n"
            '    "metadata": {\n'
            '        "description": "orig",\n'
            '        "sample_queries": ["q1"]\n'
            "    },\n"
            '    "tools": [{ "name": "f", "class": "openai" }]\n'
            "}\n",
        )
        target = tmp_path / "muse.hocon"

        AgentNetworkExporter(project_dir=str(tmp_path / "project")).export("muse", output_path=str(target))

        text = target.read_text(encoding="utf-8")
        assert text.count('"metadata"') == 1
        config = ConfigFactory.parse_file(str(target))
        assert config["metadata"]["description"] == "orig"
        assert list(config["metadata"]["sample_queries"]) == ["q1"]
        assert _EXPORT_KEYS.issubset(set(config["metadata"]))


def built_version(built: dict) -> str:
    """Pull the version value out of a built-metadata dict (kept tiny for readability)."""
    return built["export_neuro_san_studio_version"]
