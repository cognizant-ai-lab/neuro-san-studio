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

"""Expand a set of project-local Python files to everything they import."""

import ast
import os
from collections import deque
from typing import Deque
from typing import Dict
from typing import List
from typing import Optional
from typing import Set


class LocalImportWalker:
    """Close a set of ``coded_tools/`` / ``middleware/`` files under their own imports.

    ``DependencyAnalyzer`` maps each HOCON ``class`` field to exactly one module file. That is
    only the entry point: a coded tool routinely imports helper modules that no HOCON ever names
    (``constants.py``, ``and_logger.py``, a persistor factory), and those helpers are just as
    required at runtime. Importing or exporting a network without them lands a tree that raises
    ``ModuleNotFoundError`` the first time the tool is instantiated.

    Following imports statically — rather than copying each entry point's whole containing
    package — keeps the closure precise in both directions. Whole-package copying is too coarse
    (``coded_tools/basic/`` holds tools for a dozen unrelated networks) and too narrow (the
    designer's helpers cross packages: ``coded_tools/agent_network_test_generator/*.py`` all
    import ``coded_tools.agent_network_editor.and_logger``).
    """

    def __init__(self, roots: Dict[str, str]):
        """Initialize the walker.

        Args:
            roots: Maps a top-level package name to the directory holding it, e.g.
                ``{"coded_tools": "/proj/coded_tools", "middleware": "/proj/middleware"}``.
                Imports whose first segment is not a key here are treated as third-party or
                stdlib and dropped.
        """
        self.roots = roots

    def expand(self, relative_paths: List[str]) -> List[str]:
        """Return ``relative_paths`` plus every project-local module reachable from them.

        Args:
            relative_paths: Root-prefixed paths as produced by
                ``DependencyAnalyzer.resolve_coded_tool_path``, e.g.
                ``"coded_tools/agent_network_editor/add_agent.py"``. Directory entries (a coded
                tool referenced as a package) are kept as-is and scanned for imports.

        Returns:
            The same path shape, input order first and discovered modules appended, de-duplicated.
            Breadth-first so a network's own entry points stay ahead of their helpers.
        """
        ordered: List[str] = []
        seen: Set[str] = set()
        queue: Deque[str] = deque(relative_paths)
        while queue:
            relative_path = queue.popleft()
            if relative_path in seen:
                continue
            seen.add(relative_path)
            ordered.append(relative_path)
            for discovered in self._imports_of(relative_path):
                if discovered not in seen:
                    queue.append(discovered)
        return ordered

    def _imports_of(self, relative_path: str) -> List[str]:
        """Return the project-local modules imported by ``relative_path``, as relative paths."""
        absolute_path = self._to_absolute(relative_path)
        if absolute_path is None:
            return []

        if os.path.isdir(absolute_path):
            sources = [
                (os.path.join(dirpath, name), self._relative_of(os.path.join(dirpath, name)))
                for dirpath, _dirs, files in os.walk(absolute_path)
                for name in files
                if name.endswith(".py")
            ]
        elif os.path.isfile(absolute_path) and absolute_path.endswith(".py"):
            sources = [(absolute_path, relative_path)]
        else:
            return []

        found: List[str] = []
        for source, source_relative in sources:
            if source_relative is None:
                continue
            for module in self._modules_imported_by(source, source_relative):
                resolved = self.module_to_relative_path(module)
                if resolved is not None:
                    found.append(resolved)
        return found

    @staticmethod
    def _modules_imported_by(source: str, source_relative: str) -> List[str]:
        """Parse ``source`` and return every dotted module name it imports.

        A file that cannot be read or parsed contributes nothing rather than failing the walk —
        a syntax error in one coded tool should not abort an import of an unrelated network.
        """
        try:
            with open(source, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            return []

        modules: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = LocalImportWalker._import_from_base(node, source_relative)
                if base is None:
                    continue
                if base:
                    modules.append(base)
                # `from pkg import name` may import a submodule rather than an attribute, and
                # only the dotted form resolves to a file. Unresolvable attribute names are
                # dropped later by module_to_relative_path.
                modules.extend(f"{base}.{alias.name}" if base else alias.name for alias in node.names)
        return modules

    @staticmethod
    def _import_from_base(node: ast.ImportFrom, source_relative: str) -> Optional[str]:
        """Return the absolute dotted package an ``ImportFrom`` resolves against.

        Absolute imports (``level == 0``) are just ``node.module``. A relative import walks up
        ``level - 1`` packages from the importing module's own package, mirroring CPython.
        Returns ``None`` when the relative import climbs above the root.
        """
        if node.level == 0:
            return node.module or ""

        # Both `pkg/__init__.py` and `pkg/mod.py` sit in package `pkg`, so dropping the
        # filename yields the anchor package either way.
        package_parts = source_relative.split("/")[:-1]
        climb = node.level - 1
        if climb > len(package_parts):
            return None
        anchor = package_parts[: len(package_parts) - climb] if climb else package_parts
        if not anchor:
            return None
        base = ".".join(anchor)
        return f"{base}.{node.module}" if node.module else base

    def module_to_relative_path(self, module: str) -> Optional[str]:
        """Map a dotted module name to a root-prefixed relative path, or ``None`` if not local.

        Resolves ``pkg.mod`` to ``pkg/mod.py`` when that file exists, else to
        ``pkg/mod/__init__.py`` when ``pkg/mod`` is a package. Anything else — stdlib,
        third-party, or an attribute name appended by ``from ... import`` — returns ``None``.
        """
        parts = module.split(".")
        root_dir = self.roots.get(parts[0])
        if root_dir is None:
            return None
        tail = parts[1:]
        if os.path.isfile(os.path.join(root_dir, *tail) + ".py"):
            return "/".join(parts) + ".py"
        if os.path.isfile(os.path.join(root_dir, *tail, "__init__.py")):
            return "/".join(parts + ["__init__.py"])
        return None

    def _to_absolute(self, relative_path: str) -> Optional[str]:
        """Map a root-prefixed relative path back to an absolute path, or ``None`` if not local."""
        parts = relative_path.split("/")
        root_dir = self.roots.get(parts[0])
        if root_dir is None:
            return None
        return os.path.join(root_dir, *parts[1:])

    def _relative_of(self, absolute_path: str) -> Optional[str]:
        """Map an absolute path under one of the roots back to its root-prefixed relative form."""
        for root_name, root_dir in self.roots.items():
            if absolute_path.startswith(root_dir + os.sep):
                tail = os.path.relpath(absolute_path, root_dir).replace(os.sep, "/")
                return f"{root_name}/{tail}"
        return None
