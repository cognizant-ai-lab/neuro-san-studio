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

"""Regression test: the repo must not depend on the sunset langchain-community package."""

import ast
import os
import unittest

# Directories that are never part of the shipped source tree: VCS metadata,
# virtual environments (every name .gitignore anticipates), worktrees, build
# output, and caches.
SKIPPED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "ENV",
        "env.bak",
        "venv.bak",
        ".claude",
        "node_modules",
        "build",
        "dist",
        "__pycache__",
    }
)
# Marker files/dirs found at the top of a Python environment whatever it is named:
# pyvenv.cfg for venv/virtualenv/uv, conda-meta for conda. Any directory holding
# one is an installed environment whose site-packages must not be scanned.
ENVIRONMENT_MARKERS: tuple[str, ...] = ("pyvenv.cfg", "conda-meta")
FORBIDDEN_MODULE: str = "langchain_community"
FORBIDDEN_DISTRIBUTIONS: tuple[str, ...] = ("langchain-community", "langchain_community")
# Every requirements file pyproject.toml consumes ([tool.setuptools.dynamic]).
REQUIREMENTS_FILES: tuple[str, ...] = (
    "requirements.txt",
    "requirements-build.txt",
    os.path.join("neuro_san_studio", "plugins", "langfuse", "requirements.txt"),
)


class TestNoLangchainCommunity(unittest.TestCase):
    """
    Guard against langchain-community creeping back into the repo.

    Issue #1242 removed the dependency on langchain-community, whose integrations
    were sunset upstream and which pulled a large, slow-moving dependency tree
    into every install. Its last user, the agentic_rag example's custom PDF tool,
    was replaced by the shared toolbox pdf_rag tool (PdfRag), which fetches and
    parses PDFs through the in-repo SafeFetch/PdfUtils helpers. This test scans
    every Python module for an import of langchain_community and every
    requirements file for a pin on it, so a future change cannot quietly
    reintroduce the dependency.
    """

    @staticmethod
    def _repo_root() -> str:
        """
        Locate the repository root relative to this test file.

        :return: The absolute path of the repository root (tests/ lives directly under it).
        """
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def _python_files(root: str) -> list[str]:
        """
        Collect every .py file under root, pruning directories that are not source.

        :param root: The directory to walk.
        :return: Absolute paths of the Python files found, in walk order.
        """
        python_files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune in place so os.walk never descends into skipped directories
            # (os.walk honours mutation of dirnames only when topdown=True, the default).
            kept_dirnames: list[str] = []
            for dirname in dirnames:
                if dirname in SKIPPED_DIR_NAMES or dirname.startswith("."):
                    continue
                # An environment under an unanticipated name (e.g. "myenv") would
                # otherwise drag its site-packages into the scan, where third-party
                # modules legitimately import langchain_community.
                if TestNoLangchainCommunity._is_environment_dir(os.path.join(dirpath, dirname)):
                    continue
                kept_dirnames.append(dirname)
            dirnames[:] = kept_dirnames
            for filename in filenames:
                if filename.endswith(".py"):
                    python_files.append(os.path.join(dirpath, filename))
        return python_files

    @staticmethod
    def _is_environment_dir(path: str) -> bool:
        """
        Tell whether a directory is the root of an installed Python environment.

        :param path: The directory to inspect.
        :return: True when one of ENVIRONMENT_MARKERS exists directly inside it.
        """
        for marker in ENVIRONMENT_MARKERS:
            if os.path.exists(os.path.join(path, marker)):
                return True
        return False

    @staticmethod
    def _is_forbidden_module(module_name: str | None) -> bool:
        """
        Tell whether an imported module name is langchain_community or a submodule of it.

        :param module_name: The dotted module name from an Import/ImportFrom node (None for
            relative imports with no module, e.g. ``from . import x``).
        :return: True when the module is the forbidden package or lives inside it.
        """
        if module_name is None:
            return False
        return module_name == FORBIDDEN_MODULE or module_name.startswith(FORBIDDEN_MODULE + ".")

    @staticmethod
    def _forbidden_imports(path: str, source: str) -> list[str]:
        """
        Find every import of the forbidden package in one module's source.

        :param path: The file path, used to label findings.
        :param source: The module's source text.
        :return: 'path:line' entries, one per offending import statement.
        :raises SyntaxError: When the source cannot be parsed as Python.
        """
        findings: list[str] = []
        tree: ast.Module = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if TestNoLangchainCommunity._is_forbidden_module(alias.name):
                        findings.append(f"{path}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                # A relative import (level > 0) can never name an installed top-level
                # package, so only absolute imports are checked.
                if node.level == 0 and TestNoLangchainCommunity._is_forbidden_module(node.module):
                    findings.append(f"{path}:{node.lineno}")
        return findings

    def test_no_python_module_imports_langchain_community(self) -> None:
        """No Python module in the repo imports langchain_community or any of its submodules."""
        root: str = self._repo_root()
        python_files: list[str] = self._python_files(root)
        # If the walk found nothing, the root computation is wrong and a passing
        # result would be meaningless; fail loudly instead of "passing" vacuously.
        self.assertTrue(python_files, f"No Python files found under {root}")

        findings: list[str] = []
        unparseable: list[str] = []
        for path in python_files:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                source: str = handle.read()
            try:
                findings.extend(self._forbidden_imports(path, source))
            except SyntaxError as error:
                # A file this interpreter cannot parse (e.g. a deliberately broken
                # fixture) is noted, not silently dropped, so a review can tell
                # whether coverage was lost.
                unparseable.append(f"{path}: {error.msg} (line {error.lineno})")

        if unparseable:
            print("Skipped unparseable Python files:\n  " + "\n  ".join(unparseable))

        self.assertEqual(
            findings,
            [],
            "langchain-community was removed in #1242; these modules import it:\n  " + "\n  ".join(findings),
        )

    def test_requirements_do_not_pin_langchain_community(self) -> None:
        """No requirements file consumed by pyproject.toml lists langchain-community as a dependency."""
        root: str = self._repo_root()
        offenders: list[str] = []
        for requirements_name in REQUIREMENTS_FILES:
            requirements_path: str = os.path.join(root, requirements_name)
            self.assertTrue(os.path.isfile(requirements_path), f"Missing {requirements_path}")
            with open(requirements_path, "r", encoding="utf-8") as handle:
                lines: list[str] = handle.readlines()
            for line_number, raw_line in enumerate(lines, start=1):
                line: str = raw_line.strip().lower()
                # Comments and blank lines cannot pin anything.
                if not line or line.startswith("#"):
                    continue
                for distribution in FORBIDDEN_DISTRIBUTIONS:
                    if line.startswith(distribution):
                        offenders.append(f"{requirements_name}:{line_number}: {raw_line.strip()}")
                        break

        self.assertEqual(
            offenders,
            [],
            "langchain-community was removed in #1242; these requirement lines pin it:\n  " + "\n  ".join(offenders),
        )
