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

"""Tests for neuro_san_studio.discovery.dependency_analyzer.DependencyAnalyzer.

Tests for DependencyAnalyzer.resolve_coded_tool_path short-form hierarchy resolution.

Dependency analysis must not spam the console with pyhocon include warnings.

A pip-installed source tree ships no `config/` directory, so nearly every network's
`include "config/llm_config.hocon"` fails to resolve during analysis. That is expected —
the analyzer tolerates unresolved includes by design — but pyhocon logs
"Cannot include file ..." once per parse, which interleaved noise into every
`ns init` / `ns import` run on a pip install.

Tests for DependencyAnalyzer's URL-tool classifier.

Calls ``_extract_from_config`` directly with a hand-built dict so we don't need hocon
fixtures or filesystem state. URL strings are assembled from individual pieces so no
URL-shaped substring sits contiguously in the source — keeps the link-checker quiet.

Dependency analysis must not depend on the caller's working directory.

Networks pull shared prompt fragments in with `include "registries/<name>.hocon"` and then
substitute them (`${aaosa_instructions}`). pyhocon resolves a relative include against the
process CWD, and `analyze_network` swallows the resulting ValueError -- so analyzing from
the wrong directory used to return an *empty* dependency set with no error at all, and the
network landed in the target project with none of its coded tools.
"""

# pylint: disable=protected-access

import logging
import os
from pathlib import Path
from typing import List

import pytest

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer


class TestShortFormResolution:
    """A short-form ``module.Class`` ref resolves up the group hierarchy, like neuro-san."""

    def test_resolves_tool_in_per_network_dir(self, tmp_path: Path) -> None:
        """A tool under coded_tools/<group>/<network>/ is found via context_dir."""
        tool = tmp_path / "coded_tools" / "basic" / "music_nerd" / "lookup.py"
        tool.parent.mkdir(parents=True)
        tool.write_text("class Lookup: pass\n")

        result = _analyzer(tmp_path).resolve_coded_tool_path("lookup.Lookup", context_dir="basic/music_nerd")
        assert result == "coded_tools/basic/music_nerd/lookup.py"

    def test_resolves_group_level_tool(self, tmp_path: Path) -> None:
        """A tool at the group level coded_tools/<group>/ is found when not in the network dir.

        Regression for issue #1147: music_nerd_pro's ``accountant.Accountant`` lives at
        coded_tools/basic/accountant.py, not coded_tools/basic/music_nerd_pro/accountant.py.
        """
        tool = tmp_path / "coded_tools" / "basic" / "accountant.py"
        tool.parent.mkdir(parents=True)
        tool.write_text("class Accountant: pass\n")

        result = _analyzer(tmp_path).resolve_coded_tool_path(
            "accountant.Accountant", context_dir="basic/music_nerd_pro"
        )
        assert result == "coded_tools/basic/accountant.py"


class TestAnalysisLogging:
    """`get_transitive_dependencies` must keep pyhocon quiet and put its logger back."""

    @staticmethod
    def _build_source_with_missing_include(source_dir: Path) -> Path:
        """
        Lay out a source tree whose network includes a file that does not exist there.

        Mirrors the pip layout: the network references `config/llm_config.hocon`, which the
        installed package never ships. No `${substitution}` is used, so the parse itself
        succeeds and the class reference below stays extractable.

        :param source_dir: Root directory to build the synthetic source tree under.
        :return: The full path of the network HOCON to analyze.
        """
        registries: Path = source_dir / "registries"
        registries.mkdir(parents=True)
        hocon: Path = registries / "demo.hocon"
        hocon.write_text(
            """{
    include "config/llm_config.hocon",
    "tools": [
        { "name": "demo", "class": "demo_tool.DemoTool" }
    ]
}
"""
        )
        coded_tools: Path = source_dir / "coded_tools"
        coded_tools.mkdir(parents=True)
        (coded_tools / "__init__.py").write_text("")
        (coded_tools / "demo_tool.py").write_text("class DemoTool:\n    pass\n")
        (source_dir / "middleware").mkdir(parents=True)
        return hocon

    @staticmethod
    def _analyzer(source_dir: Path) -> DependencyAnalyzer:
        """
        Build an analyzer rooted at `source_dir`.

        :param source_dir: Root of the synthetic source tree.
        :return: A DependencyAnalyzer over that tree's registries/coded_tools/middleware roots.
        """
        return DependencyAnalyzer(
            str(source_dir / "registries"),
            str(source_dir / "coded_tools"),
            str(source_dir / "middleware"),
        )

    def test_unresolvable_include_logs_nothing(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """An include that cannot resolve must not reach the console, and analysis must still work.

        :param tmp_path: pytest-provided temporary directory for the synthetic source tree.
        :param caplog: pytest's log capture, used to detect pyhocon's include complaints.
        """
        source: Path = tmp_path / "source"
        hocon: Path = self._build_source_with_missing_include(source)

        with caplog.at_level(logging.WARNING, logger="pyhocon.config_parser"):
            deps: AgentNetworkDependencies = self._analyzer(source).get_transitive_dependencies(str(hocon))

        # The failed include must not have cost us the actual dependency extraction.
        assert deps.coded_tools == ["coded_tools/demo_tool.py"]
        pyhocon_complaints: List[str] = []
        for record in caplog.records:
            if record.name == "pyhocon.config_parser":
                pyhocon_complaints.append(record.getMessage())
        assert not pyhocon_complaints, f"pyhocon noise leaked through: {pyhocon_complaints}"

    def test_pyhocon_logger_level_is_restored(self, tmp_path: Path) -> None:
        """The demotion is scoped to the walk; a caller's own pyhocon level must survive.

        :param tmp_path: pytest-provided temporary directory for the synthetic source tree.
        """
        source: Path = tmp_path / "source"
        hocon: Path = self._build_source_with_missing_include(source)
        pyhocon_logger: logging.Logger = logging.getLogger("pyhocon.config_parser")
        prev_level: int = pyhocon_logger.level
        try:
            pyhocon_logger.setLevel(logging.DEBUG)

            self._analyzer(source).get_transitive_dependencies(str(hocon))

            assert pyhocon_logger.level == logging.DEBUG
        finally:
            # Never leak a DEBUG pyhocon logger into the rest of the suite.
            pyhocon_logger.setLevel(prev_level)


class TestToolClassifier:  # pylint: disable=too-few-public-methods
    """One pass over each branch of the tool-ref classifier."""

    @staticmethod
    def _join(scheme: str, host: str, *path_parts: str) -> str:
        """Build a URL from non-URL fragments (avoids any literal URL in source)."""
        return scheme + "://" + host + "/" + "/".join(path_parts)

    def test_classifier_routes_each_ref_to_the_correct_bucket(self) -> None:
        """Sub-network goes to ``sub_networks``; ``/mcp``-suffix URL goes to ``mcp_tools``;
        plain external HTTP-agent URL is dropped (runtime-only, not a bundled dep)."""
        external_url = self._join("http", "host-a.invalid", "agent")
        mcp_url = self._join("https", "host-b.invalid", "tool", "mcp")

        config = {
            "tools": [
                {
                    "name": "frontman",
                    "class": "openai",
                    "tools": ["/sub_helper", external_url, mcp_url],
                }
            ]
        }
        deps = AgentNetworkDependencies()
        DependencyAnalyzer._extract_from_config(config, deps)

        assert deps.sub_networks == ["/sub_helper"]
        assert deps.mcp_tools == [mcp_url]
        assert external_url not in deps.mcp_tools


def _build_source(source_dir: Path) -> None:
    """Lay out a source tree whose network includes and substitutes a shared fragment."""
    registries = source_dir / "registries"
    registries.mkdir(parents=True)
    (registries / "shared.hocon").write_text('{ "shared_instructions": "be helpful" }\n')
    (registries / "demo.hocon").write_text(
        """{
    include "registries/shared.hocon",
    "tools": [
        {
            "name": "demo",
            "instructions": ${shared_instructions},
            "class": "demo_tool.DemoTool"
        }
    ]
}
"""
    )

    coded_tools = source_dir / "coded_tools"
    coded_tools.mkdir(parents=True)
    (coded_tools / "__init__.py").write_text("")
    (coded_tools / "demo_tool.py").write_text("class DemoTool:\n    pass\n")
    (source_dir / "middleware").mkdir(parents=True)


def _analyzer(source_dir: Path) -> DependencyAnalyzer:
    """Build an analyzer rooted at `source_dir`."""
    return DependencyAnalyzer(
        str(source_dir / "registries"),
        str(source_dir / "coded_tools"),
        str(source_dir / "middleware"),
    )


class TestAnalysisIsWorkingDirectoryIndependent:
    """`get_transitive_dependencies` must resolve includes relative to the analyzed tree."""

    def test_includes_resolve_from_an_unrelated_cwd(self, tmp_path: Path) -> None:
        """The dependency set must be identical whether or not CWD happens to hold the includes.

        This is the regression guard for `ns import`, which ran the analysis with CWD set to
        the user's project while parsing HOCONs out of the installed studio package.
        """
        source = tmp_path / "source"
        _build_source(source)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        analyzer = _analyzer(source)
        target = str(source / "registries" / "demo.hocon")

        from_source = analyzer.get_transitive_dependencies(target)
        os.chdir(elsewhere)
        from_elsewhere = analyzer.get_transitive_dependencies(target)

        assert from_source.coded_tools == ["coded_tools/demo_tool.py"]
        assert from_elsewhere.coded_tools == from_source.coded_tools

    def test_working_directory_is_restored(self, tmp_path: Path) -> None:
        """A caller's CWD must survive the analysis, including when the network is unparseable."""
        source = tmp_path / "source"
        _build_source(source)
        (source / "registries" / "broken.hocon").write_text("{ not valid hocon ${\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        os.chdir(elsewhere)
        before = os.getcwd()

        analyzer = _analyzer(source)
        analyzer.get_transitive_dependencies(str(source / "registries" / "demo.hocon"))
        assert os.getcwd() == before

        analyzer.get_transitive_dependencies(str(source / "registries" / "broken.hocon"))
        assert os.getcwd() == before

    def test_relative_hocon_path_is_resolved_before_the_chdir(self, tmp_path: Path) -> None:
        """A path relative to the caller's CWD must still resolve once analysis chdirs away."""
        source = tmp_path / "source"
        _build_source(source)
        os.chdir(source / "registries")

        analyzer = _analyzer(source)
        deps = analyzer.get_transitive_dependencies("demo.hocon")

        assert deps.coded_tools == ["coded_tools/demo_tool.py"]


@pytest.fixture(autouse=True)
def _restore_cwd():
    """Tests here chdir on purpose; put the process back so later tests are unaffected."""
    prev = os.getcwd()
    yield
    os.chdir(prev)
