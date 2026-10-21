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
import sys
import warnings


class ModuleAlias:  # pylint: disable=too-few-public-methods
    """
    Keeps an old module path working after its module has moved.

    The module left at the old path calls alias() with its own name. The old name then refers to the moved
    module itself, so an import of the old path, a class name in a network file and a mock.patch target all
    reach the same module and the same classes. The first import of an old path warns that it is deprecated.

    The old name is only an alias, so the moved modules never run again through it: use importlib.reload to
    re-read a moved module, and stub a moved module under its new name.
    """

    @staticmethod
    def alias(old_name: str, new_name: str) -> None:
        """
        Make an old module name refer to the module that now has a new name.

        :param old_name: The old module name: the __name__ of the module left at the old path
        :param new_name: The module's new name
        """
        # Old names are mostly in network files, which users edit, so the warning is a FutureWarning: Python
        # shows those by default. For an import statement, stacklevel 3 names the line that imported the old path.
        warnings.warn(
            f"{old_name} has moved to {new_name}. Use the new name, because the old one will be removed.",
            FutureWarning,
            stacklevel=3,
        )
        # Once the old module has run, Python hands the importer whatever sys.modules holds for the old name.
        sys.modules[old_name] = importlib.import_module(new_name)
