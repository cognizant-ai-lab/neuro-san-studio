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

"""Tests for ImportCommand argument handling: _parse_arg and file inference."""

import pytest

from neuro_san_studio.commands.import_networks import ImportCommand


@pytest.fixture(name="networks_by_group")
def _networks_by_group() -> dict:
    """A small registry-shape mapping used by the _parse_arg tests."""
    return {
        "basic": ["basic/music_nerd.hocon", "basic/coffee_finder.hocon"],
        "industry": ["industry/airline_policy.hocon"],
        "root": ["agent_network_designer.hocon"],
    }


class TestParseArg:
    """Tests for ImportCommand._parse_arg."""

    def test_all_expands_to_every_network(self, networks_by_group: dict) -> None:
        """'all' should expand to the union of every group's paths."""
        # pylint: disable=protected-access
        assert ImportCommand._parse_arg(["all"], networks_by_group) == [
            "basic/music_nerd.hocon",
            "basic/coffee_finder.hocon",
            "industry/airline_policy.hocon",
            "agent_network_designer.hocon",
        ]

    def test_single_group(self, networks_by_group: dict) -> None:
        """A bare group name should expand to all its networks."""
        # pylint: disable=protected-access
        assert ImportCommand._parse_arg(["basic"], networks_by_group) == [
            "basic/music_nerd.hocon",
            "basic/coffee_finder.hocon",
        ]

    def test_multiple_groups_space_separated(self, networks_by_group: dict) -> None:
        """Multiple groups should be concatenated in argument order."""
        # pylint: disable=protected-access
        assert ImportCommand._parse_arg(["industry", "basic"], networks_by_group) == [
            "industry/airline_policy.hocon",
            "basic/music_nerd.hocon",
            "basic/coffee_finder.hocon",
        ]

    def test_single_network_bare_name(self, networks_by_group: dict) -> None:
        """A bare network name should match by basename across any group."""
        # pylint: disable=protected-access
        assert ImportCommand._parse_arg(["music_nerd"], networks_by_group) == ["basic/music_nerd.hocon"]

    def test_single_network_with_group_prefix(self, networks_by_group: dict) -> None:
        """A group/name path should match the exact network."""
        # pylint: disable=protected-access
        assert ImportCommand._parse_arg(["basic/music_nerd"], networks_by_group) == ["basic/music_nerd.hocon"]

    def test_root_network_bare_name(self, networks_by_group: dict) -> None:
        """Root-level networks should be reachable by bare name too."""
        # pylint: disable=protected-access
        assert ImportCommand._parse_arg(["agent_network_designer"], networks_by_group) == [
            "agent_network_designer.hocon",
        ]

    def test_unknown_spec_warns_and_skips(self, networks_by_group: dict, capsys: pytest.CaptureFixture[str]) -> None:
        """Unknown specs should print a warning and be dropped from the result."""
        # pylint: disable=protected-access
        result = ImportCommand._parse_arg(["music_nerd", "bogus"], networks_by_group)
        assert result == ["basic/music_nerd.hocon"]
        assert "Network 'bogus' not found" in capsys.readouterr().out

    def test_dedupe_preserves_first_occurrence(self, networks_by_group: dict) -> None:
        """A spec mix that yields duplicates should be deduplicated, first occurrence wins."""
        # pylint: disable=protected-access
        result = ImportCommand._parse_arg(["basic", "music_nerd"], networks_by_group)
        assert result == ["basic/music_nerd.hocon", "basic/coffee_finder.hocon"]

    def test_whitespace_stripped(self, networks_by_group: dict) -> None:
        """Whitespace around individual specs should be tolerated."""
        # pylint: disable=protected-access
        assert ImportCommand._parse_arg([" basic ", " industry "], networks_by_group) == [
            "basic/music_nerd.hocon",
            "basic/coffee_finder.hocon",
            "industry/airline_policy.hocon",
        ]


class TestLooksLikeAgentNetworkFile:
    """Tests for ImportCommand._looks_like_agent_network_file (file-vs-registry inference)."""

    @pytest.mark.parametrize(
        "arg",
        [
            "music_nerd.hocon",
            "bundle.zip",
            "path/to/network.hocon",
            "MyNetwork.HOCON",
            "archive.ZIP",
        ],
    )
    def test_file_extensions_route_to_file_flow(self, arg: str) -> None:
        """A .hocon/.zip arg (any case, with or without a path) is treated as a file."""
        # pylint: disable=protected-access
        assert ImportCommand._looks_like_agent_network_file(arg) is True

    @pytest.mark.parametrize(
        "arg",
        [
            "music_nerd",
            "basic",
            "industry/airline_policy",
            "all",
        ],
    )
    def test_extensionless_args_stay_registry_lookups(self, arg: str) -> None:
        """A bare name/group/path with no file extension is a registry lookup, not a file."""
        # pylint: disable=protected-access
        assert ImportCommand._looks_like_agent_network_file(arg) is False


class TestSplitFileArgs:
    """Tests for ImportCommand._split_file_args (space-separated file-vs-registry routing)."""

    def test_single_file_returns_one_path(self) -> None:
        """A lone .hocon/.zip token yields a one-element file list."""
        # pylint: disable=protected-access
        assert ImportCommand._split_file_args(["music_nerd.hocon"]) == ["music_nerd.hocon"]

    def test_list_of_files_returns_all_paths(self) -> None:
        """An all-file token list yields every path, whitespace trimmed."""
        # pylint: disable=protected-access
        assert ImportCommand._split_file_args(["a.hocon", " b.zip ", "c.hocon"]) == ["a.hocon", "b.zip", "c.hocon"]

    @pytest.mark.parametrize(
        "tokens",
        [["basic"], ["music_nerd"], ["basic", "music_nerd"], ["industry/airline_policy"]],
    )
    def test_registry_args_return_none(self, tokens: list) -> None:
        """No file extensions → None, so the caller falls through to registry resolution."""
        # pylint: disable=protected-access
        assert ImportCommand._split_file_args(tokens) is None

    def test_mixed_files_and_names_exits(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Mixing a file path with a registry name aborts with a clear error, not a silent miss."""
        with pytest.raises(SystemExit) as exc:
            # pylint: disable=protected-access
            ImportCommand._split_file_args(["basic", "music_nerd.hocon"])
        assert exc.value.code == 1
        assert "Cannot mix" in capsys.readouterr().out
