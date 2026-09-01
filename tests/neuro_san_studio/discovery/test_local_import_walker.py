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

"""Tests for LocalImportWalker, which closes a dependency set under its own Python imports."""

from pathlib import Path

from neuro_san_studio.discovery.local_import_walker import LocalImportWalker


def _walker(tmp_path: Path) -> LocalImportWalker:
    """A walker over coded_tools/ and middleware/ trees rooted at tmp_path."""
    for root in ("coded_tools", "middleware"):
        (tmp_path / root).mkdir(exist_ok=True)
        (tmp_path / root / "__init__.py").write_text("")
    return LocalImportWalker(
        {
            "coded_tools": str(tmp_path / "coded_tools"),
            "middleware": str(tmp_path / "middleware"),
        }
    )


def _write(tmp_path: Path, relative_path: str, body: str = "") -> None:
    """Create a module at relative_path (root-prefixed) with the given source."""
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


class TestExpand:
    """The closure LocalImportWalker.expand produces."""

    def test_same_package_sibling_is_pulled_in(self, tmp_path: Path) -> None:
        """The helper modules a coded tool imports are as required as the tool itself.

        This is the bug the walker exists for: a HOCON names add_agent.py, nothing names
        constants.py, and an import that copies only the former lands a broken tree.
        """
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/constants.py", "NAME = 'x'\n")
        _write(tmp_path, "coded_tools/pkg/add_agent.py", "from coded_tools.pkg.constants import NAME\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/add_agent.py"])

        assert result == ["coded_tools/pkg/add_agent.py", "coded_tools/pkg/constants.py"]

    def test_transitive_chain_is_followed(self, tmp_path: Path) -> None:
        """Helpers of helpers come along too; one hop is not enough."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/third.py", "VALUE = 3\n")
        _write(tmp_path, "coded_tools/pkg/second.py", "from coded_tools.pkg.third import VALUE\n")
        _write(tmp_path, "coded_tools/pkg/first.py", "from coded_tools.pkg.second import VALUE\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/first.py"])

        assert set(result) == {
            "coded_tools/pkg/first.py",
            "coded_tools/pkg/second.py",
            "coded_tools/pkg/third.py",
        }

    def test_crosses_packages_and_roots(self, tmp_path: Path) -> None:
        """A dependency may live in another package, or under the other root entirely.

        Mirrors the real designer: coded_tools/agent_network_test_generator/*.py import
        coded_tools.agent_network_editor.and_logger, and the designer middleware imports coded
        tools. Copying each entry point's own package directory would miss both directions.
        """
        _write(tmp_path, "coded_tools/editor/__init__.py")
        _write(tmp_path, "coded_tools/editor/logger.py", "class Logger: pass\n")
        _write(tmp_path, "middleware/designer/__init__.py")
        _write(tmp_path, "middleware/designer/persist.py", "from coded_tools.editor.logger import Logger\n")
        _write(tmp_path, "coded_tools/generator/__init__.py")
        _write(
            tmp_path,
            "coded_tools/generator/read.py",
            "from coded_tools.editor.logger import Logger\nfrom middleware.designer.persist import Logger as L\n",
        )

        result = _walker(tmp_path).expand(["coded_tools/generator/read.py"])

        assert set(result) == {
            "coded_tools/generator/read.py",
            "coded_tools/editor/logger.py",
            "middleware/designer/persist.py",
        }

    def test_from_package_import_submodule(self, tmp_path: Path) -> None:
        """`from pkg import mod` imports a module, not an attribute, so it must resolve."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/constants.py", "NAME = 'x'\n")
        _write(tmp_path, "coded_tools/pkg/tool.py", "from coded_tools.pkg import constants\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/tool.py"])

        assert "coded_tools/pkg/constants.py" in result

    def test_plain_import_statement(self, tmp_path: Path) -> None:
        """`import coded_tools.pkg.constants` is followed as well as the `from` form."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/constants.py", "NAME = 'x'\n")
        _write(tmp_path, "coded_tools/pkg/tool.py", "import coded_tools.pkg.constants\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/tool.py"])

        assert "coded_tools/pkg/constants.py" in result

    def test_package_reference_resolves_to_init(self, tmp_path: Path) -> None:
        """Importing a package brings its __init__.py, which may itself import more.

        `from coded_tools import pkg` also names the root package, so coded_tools/__init__.py
        comes along — which is wanted: without it the project's coded_tools is a namespace
        portion and loses to the installed package on sys.path.
        """
        _write(tmp_path, "coded_tools/pkg/__init__.py", "from coded_tools.pkg.constants import NAME\n")
        _write(tmp_path, "coded_tools/pkg/constants.py", "NAME = 'x'\n")
        _write(tmp_path, "coded_tools/other.py", "from coded_tools import pkg\n")

        result = _walker(tmp_path).expand(["coded_tools/other.py"])

        assert set(result) == {
            "coded_tools/other.py",
            "coded_tools/__init__.py",
            "coded_tools/pkg/__init__.py",
            "coded_tools/pkg/constants.py",
        }

    def test_relative_imports_resolve(self, tmp_path: Path) -> None:
        """`from .sibling import X` inside a package __init__ resolves to the sibling.

        coded_tools/tools/now_agents/__init__.py is the real instance of this shape.
        """
        _write(tmp_path, "coded_tools/pkg/__init__.py", "from .sibling import Thing\n")
        _write(tmp_path, "coded_tools/pkg/sibling.py", "class Thing: pass\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/__init__.py"])

        assert result == ["coded_tools/pkg/__init__.py", "coded_tools/pkg/sibling.py"]

    def test_parent_relative_import_resolves(self, tmp_path: Path) -> None:
        """A `..` import climbs one package, matching CPython's resolution."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/shared.py", "VALUE = 1\n")
        _write(tmp_path, "coded_tools/pkg/inner/__init__.py")
        _write(tmp_path, "coded_tools/pkg/inner/tool.py", "from ..shared import VALUE\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/inner/tool.py"])

        assert "coded_tools/pkg/shared.py" in result

    def test_third_party_and_stdlib_imports_are_dropped(self, tmp_path: Path) -> None:
        """Only project-local modules are bundled; everything else is a pip dependency."""
        _write(
            tmp_path,
            "coded_tools/pkg/tool.py",
            "import os\nimport logging\nfrom neuro_san.interfaces.coded_tool import CodedTool\n",
        )

        result = _walker(tmp_path).expand(["coded_tools/pkg/tool.py"])

        assert result == ["coded_tools/pkg/tool.py"]

    def test_import_cycle_terminates(self, tmp_path: Path) -> None:
        """Mutually importing modules must not loop forever."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/a.py", "from coded_tools.pkg.b import B\n")
        _write(tmp_path, "coded_tools/pkg/b.py", "from coded_tools.pkg.a import A\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/a.py"])

        assert set(result) == {"coded_tools/pkg/a.py", "coded_tools/pkg/b.py"}

    def test_unparseable_file_contributes_nothing(self, tmp_path: Path) -> None:
        """A syntax error in one coded tool must not abort an unrelated network's import."""
        _write(tmp_path, "coded_tools/pkg/broken.py", "def (((\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/broken.py"])

        assert result == ["coded_tools/pkg/broken.py"]

    def test_missing_file_is_kept_and_skipped(self, tmp_path: Path) -> None:
        """A dependency that no longer exists stays in the list for the importer to warn about."""
        result = _walker(tmp_path).expand(["coded_tools/pkg/gone.py"])

        assert result == ["coded_tools/pkg/gone.py"]

    def test_directory_dependency_is_scanned_and_preserved(self, tmp_path: Path) -> None:
        """A coded tool referenced as a package keeps its directory entry and pulls its imports."""
        _write(tmp_path, "coded_tools/pkg/__init__.py", "from coded_tools.helper import Helper\n")
        _write(tmp_path, "coded_tools/helper.py", "class Helper: pass\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg"])

        assert result == ["coded_tools/pkg", "coded_tools/helper.py"]

    def test_package_init_reexports_are_followed(self, tmp_path: Path) -> None:
        """A re-export made only in a package __init__.py joins the closure.

        Importing pkg.helper_a at runtime executes pkg/__init__.py first, so helper_b is as
        required as helper_a even though no HOCON and no scanned module ever names it. The
        init file itself stays out of the closure: the importer's parent-init chain and the
        exporter's parent-init bundling already deliver it for every member.

        :param tmp_path: pytest-provided temporary directory holding the synthetic roots.
        """
        _write(tmp_path, "coded_tools/pkg/__init__.py", "from .helper_a import A\nfrom .helper_b import B\n")
        _write(tmp_path, "coded_tools/pkg/helper_a.py", "class A: pass\n")
        _write(tmp_path, "coded_tools/pkg/helper_b.py", "class B: pass\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/helper_a.py"])

        assert "coded_tools/pkg/helper_b.py" in result
        assert "coded_tools/pkg/__init__.py" not in result

    def test_every_ancestor_init_is_scanned(self, tmp_path: Path) -> None:
        """Imports made at any level of the containing-package chain are discovered.

        Importing pkg.sub.mod executes pkg/__init__.py AND pkg/sub/__init__.py, so a
        dependency named only in the outer init is required too — including one that lives
        in a different package entirely.

        :param tmp_path: pytest-provided temporary directory holding the synthetic roots.
        """
        _write(tmp_path, "coded_tools/other/__init__.py")
        _write(tmp_path, "coded_tools/other/shared.py", "VALUE = 1\n")
        _write(tmp_path, "coded_tools/pkg/__init__.py", "from coded_tools.other.shared import VALUE\n")
        _write(tmp_path, "coded_tools/pkg/sub/__init__.py", "from .mod import Tool\n")
        _write(tmp_path, "coded_tools/pkg/sub/mod.py", "class Tool: pass\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/sub/mod.py"])

        assert "coded_tools/other/shared.py" in result

    def test_directory_member_ancestor_init_is_scanned(self, tmp_path: Path) -> None:
        """A directory dependency's *ancestor* inits are scanned like a file member's.

        The directory's own __init__.py is inside the copied tree and scanned by the
        directory walk; the root package's __init__.py above it is neither, so an import
        made only there used to be missed.

        :param tmp_path: pytest-provided temporary directory holding the synthetic roots.
        """
        walker = _walker(tmp_path)
        _write(tmp_path, "coded_tools/util.py", "VALUE = 1\n")
        _write(tmp_path, "coded_tools/pkg/__init__.py", "class Tool: pass\n")
        # After _walker(): it scaffolds the root __init__.py empty, and this test needs the
        # root init to carry a real import.
        (tmp_path / "coded_tools" / "__init__.py").write_text("from coded_tools.util import VALUE\n")

        result = walker.expand(["coded_tools/pkg"])

        assert "coded_tools/util.py" in result

    def test_input_order_preserved_and_deduplicated(self, tmp_path: Path) -> None:
        """Entry points stay ahead of their helpers, and nothing is listed twice."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/shared.py", "VALUE = 1\n")
        _write(tmp_path, "coded_tools/pkg/one.py", "from coded_tools.pkg.shared import VALUE\n")
        _write(tmp_path, "coded_tools/pkg/two.py", "from coded_tools.pkg.shared import VALUE\n")

        result = _walker(tmp_path).expand(["coded_tools/pkg/one.py", "coded_tools/pkg/two.py"])

        assert result == ["coded_tools/pkg/one.py", "coded_tools/pkg/two.py", "coded_tools/pkg/shared.py"]


class TestModuleToRelativePath:
    """Mapping a dotted module name onto a file under one of the roots."""

    def test_module_file(self, tmp_path: Path) -> None:
        """A module resolves to its .py file."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/mod.py")
        assert _walker(tmp_path).module_to_relative_path("coded_tools.pkg.mod") == "coded_tools/pkg/mod.py"

    def test_package_resolves_to_init(self, tmp_path: Path) -> None:
        """A package resolves to its __init__.py."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        assert _walker(tmp_path).module_to_relative_path("coded_tools.pkg") == "coded_tools/pkg/__init__.py"

    def test_root_itself_resolves(self, tmp_path: Path) -> None:
        """`import coded_tools` resolves to the root package's own __init__.py."""
        assert _walker(tmp_path).module_to_relative_path("coded_tools") == "coded_tools/__init__.py"

    def test_unknown_root_is_none(self, tmp_path: Path) -> None:
        """A module outside the configured roots is not a project dependency."""
        assert _walker(tmp_path).module_to_relative_path("neuro_san.interfaces") is None

    def test_attribute_name_is_none(self, tmp_path: Path) -> None:
        """`from pkg.mod import CONSTANT` appends a name that is not a module; it must not resolve."""
        _write(tmp_path, "coded_tools/pkg/__init__.py")
        _write(tmp_path, "coded_tools/pkg/mod.py", "CONSTANT = 1\n")
        assert _walker(tmp_path).module_to_relative_path("coded_tools.pkg.mod.CONSTANT") is None
