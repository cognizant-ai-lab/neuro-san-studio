"""Regression guard for the removal of executable langchain-community references."""

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE_DIRS = ("neuro_san_studio", "coded_tools")


def test_python_sources_do_not_import_langchain_community() -> None:
    """Packaged Python sources must not import the sunset package."""
    violations: list[str] = []
    for source_dir in SOURCE_DIRS:
        for path in (ROOT / source_dir).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                if any(
                    module == "langchain_community" or module.startswith("langchain_community.") for module in modules
                ):
                    violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"langchain-community imports remain in: {sorted(set(violations))}"


def test_hocon_does_not_load_langchain_community_classes() -> None:
    """Dynamic toolbox classes must not resolve into the sunset package."""
    violations = [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*.hocon")
        if '"class": "langchain_community.' in path.read_text(encoding="utf-8")
    ]
    assert not violations, f"langchain-community HOCON classes remain in: {violations}"
