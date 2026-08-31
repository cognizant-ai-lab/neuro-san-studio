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

"""Shared test double for the ProcessGlobals registry tests. Stdlib-only, like
the tests that use it."""


class FakeProcessGlobalsOwner:  # pylint: disable=too-few-public-methods
    """Stand-in owner class exposing a clear method like the real caches.

    ProcessGlobals reaches owners through sys.modules by module path, so this
    fake lives in a real importable module: the test importing this class is
    exactly what makes the module "imported" from the registry's point of view.

    `cleared` is a class-level record (tests clear it before use) because a
    module-level class cannot close over a test-local list the way the nested
    class it replaced did.
    """

    cleared: list[str] = []

    @classmethod
    def clear_fake_for_testing(cls):
        """Record that the registry reached this clear method."""
        cls.cleared.append("cleared")
