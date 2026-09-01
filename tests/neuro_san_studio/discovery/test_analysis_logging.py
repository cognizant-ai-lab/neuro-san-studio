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

"""Dependency analysis must not spam the console with pyhocon include warnings.

A pip-installed source tree ships no `config/` directory, so nearly every network's
`include "config/llm_config.hocon"` fails to resolve during analysis. That is expected —
the analyzer tolerates unresolved includes by design — but pyhocon logs
"Cannot include file ..." once per parse, which interleaved noise into every
`ns init` / `ns import` run on a pip install.
"""

import logging
from pathlib import Path
from typing import List

import pytest

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer


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


class TestAnalysisLogging:
    """`get_transitive_dependencies` must keep pyhocon quiet and put its logger back."""

    def test_unresolvable_include_logs_nothing(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """An include that cannot resolve must not reach the console, and analysis must still work.

        :param tmp_path: pytest-provided temporary directory for the synthetic source tree.
        :param caplog: pytest's log capture, used to detect pyhocon's include complaints.
        """
        source: Path = tmp_path / "source"
        hocon: Path = _build_source_with_missing_include(source)

        with caplog.at_level(logging.WARNING, logger="pyhocon.config_parser"):
            deps: AgentNetworkDependencies = _analyzer(source).get_transitive_dependencies(str(hocon))

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
        hocon: Path = _build_source_with_missing_include(source)
        pyhocon_logger: logging.Logger = logging.getLogger("pyhocon.config_parser")
        prev_level: int = pyhocon_logger.level
        try:
            pyhocon_logger.setLevel(logging.DEBUG)

            _analyzer(source).get_transitive_dependencies(str(hocon))

            assert pyhocon_logger.level == logging.DEBUG
        finally:
            # Never leak a DEBUG pyhocon logger into the rest of the suite.
            pyhocon_logger.setLevel(prev_level)
