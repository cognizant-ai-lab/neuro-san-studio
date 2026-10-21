# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

import importlib
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest import TestCase
from unittest.mock import patch

# A package name no other test uses, so its modules can be dropped from sys.modules after each test.
PACKAGE: str = "module_alias_test_package"


class TestModuleAlias(TestCase):
    """
    Tests for ModuleAlias.
    """

    def setUp(self) -> None:
        """
        Write a package with a moved module and the module left at its old path, and make it importable.
        """
        temp_dir: str = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir, True)
        package_dir: Path = Path(temp_dir) / PACKAGE
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "moved.py").write_text("VALUE = 1\n\n\nclass Thing:\n    pass\n", encoding="utf-8")
        (package_dir / "old.py").write_text(
            "from neuro_san_studio.utils.module_alias import ModuleAlias\n\n"
            f'ModuleAlias.alias(__name__, "{PACKAGE}.moved")\n',
            encoding="utf-8",
        )
        sys.path.insert(0, temp_dir)
        importlib.invalidate_caches()
        self.addCleanup(sys.path.remove, temp_dir)
        self.addCleanup(self._forget_package)

    @staticmethod
    def _forget_package() -> None:
        """
        Remove the test package's modules from sys.modules, so the next test imports them afresh.
        """
        for name in list(sys.modules):
            if name == PACKAGE or name.startswith(f"{PACKAGE}."):
                del sys.modules[name]

    def _import_old(self) -> ModuleType:
        """
        Import the module at the old path, and check that the import warns that the path is deprecated.

        :return: What the import of the old path gave
        """
        with self.assertWarns(FutureWarning) as caught:
            old: ModuleType = importlib.import_module(f"{PACKAGE}.old")
        self.assertIn(f"{PACKAGE}.old has moved to {PACKAGE}.moved", str(caught.warning))
        return old

    def test_old_name_is_the_moved_module(self) -> None:
        """
        Importing the old path gives the moved module itself, also as an attribute of the package.
        """
        old: ModuleType = self._import_old()

        moved: ModuleType = importlib.import_module(f"{PACKAGE}.moved")
        self.assertIs(old, moved)
        self.assertIs(sys.modules.get(f"{PACKAGE}.old"), moved)
        self.assertIs(getattr(sys.modules.get(PACKAGE), "old"), moved)

    def test_class_named_by_the_old_path_is_the_moved_class(self) -> None:
        """
        A class looked up through the old path is the moved module's class, so isinstance checks and
        subclasses keep working.
        """
        old_thing: type = getattr(self._import_old(), "Thing")

        self.assertIs(old_thing, getattr(importlib.import_module(f"{PACKAGE}.moved"), "Thing"))

    def test_patching_through_the_old_path_patches_the_moved_module(self) -> None:
        """
        A mock.patch target that names the old path patches the moved module.
        """
        self._import_old()
        moved: ModuleType = importlib.import_module(f"{PACKAGE}.moved")

        with patch(f"{PACKAGE}.old.VALUE", 2):
            self.assertEqual(getattr(moved, "VALUE"), 2)
        self.assertEqual(getattr(moved, "VALUE"), 1)
