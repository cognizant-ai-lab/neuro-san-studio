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
"""
Tests for the ProcessGlobals registry of process-wide caches.

Collecting this module needs no neuro-san: it imports only the standard library
and ProcessGlobals. The registry mechanics are tested with a fake owner module,
and one test imports the real owner modules to check the names the registry holds.
"""

import importlib
import sys
import types
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_designer.common.globals import ProcessGlobals


class TestProcessGlobals(TestCase):
    """Tests for the registry triples and the clear-all helper."""

    def test_clear_all_clears_imported_owners_and_skips_unimported(self):
        """The registry clears imported owners and skips unimported ones."""
        cleared: list[str] = []

        class FakeOwner:  # pylint: disable=too-few-public-methods
            """Stand-in owner class exposing a clear method like the real caches."""

            @classmethod
            def clear_fake_for_testing(cls):
                """Record that the registry reached this clear method."""
                cleared.append("cleared")

        fake_module = types.ModuleType("fake_process_globals_owner_module")
        fake_module.FakeOwner = FakeOwner
        registry = [
            ("fake_process_globals_owner_module", "FakeOwner", "clear_fake_for_testing"),
            # Never imported: must be skipped silently (an unimported module
            # cannot have a populated cache), not raise.
            ("module_that_was_never_imported_for_test", "Nope", "clear_nope_for_testing"),
        ]
        with patch.dict(sys.modules, {"fake_process_globals_owner_module": fake_module}):
            with patch.object(ProcessGlobals, "REGISTRY", registry):
                ProcessGlobals.clear_all_for_testing()
        self.assertEqual(cleared, ["cleared"])

    def test_registry_entries_resolve_when_imported(self):
        """Registry triples must resolve against any imported owner module."""
        for module_name, class_name, clear_method_name in ProcessGlobals.REGISTRY:
            self.assertTrue(module_name.startswith("neuro_san_studio.agent_network_designer."))
            # Owner modules need neuro-san, so only validate the ones this test
            # run happens to have imported; a typo'd class or method name in an
            # imported module must fail here rather than being skipped silently.
            module = sys.modules.get(module_name)
            if module is not None:
                self.assertTrue(callable(getattr(getattr(module, class_name), clear_method_name)))

    def test_registry_names_the_module_that_defines_each_owner(self) -> None:
        """
        Each registry entry names the module that defines its class, and the class has the clear method.

        clear_all_for_testing() finds a class through sys.modules under the name the registry holds. If that
        name is only an alias or a re-export of the defining module, the lookup can miss, and the cache then
        stays filled between tests without any error.
        """
        for module_name, class_name, clear_method_name in ProcessGlobals.REGISTRY:
            with self.subTest(module=module_name, owner=class_name):
                owner: type = getattr(importlib.import_module(module_name), class_name)
                self.assertEqual(owner.__module__, module_name)
                self.assertTrue(callable(getattr(owner, clear_method_name)))
