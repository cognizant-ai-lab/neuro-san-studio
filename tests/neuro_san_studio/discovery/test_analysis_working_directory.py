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

"""Dependency analysis must not depend on the caller's working directory.

Networks pull shared prompt fragments in with `include "registries/<name>.hocon"` and then
substitute them (`${aaosa_instructions}`). pyhocon resolves a relative include against the
process CWD, and `analyze_network` swallows the resulting ValueError -- so analyzing from
the wrong directory used to return an *empty* dependency set with no error at all, and the
network landed in the target project with none of its coded tools.
"""

import os
from pathlib import Path

import pytest

from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer


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
