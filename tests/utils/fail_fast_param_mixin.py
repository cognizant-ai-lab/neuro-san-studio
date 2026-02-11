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

# This file defines everything necessary for a data-driven test.
# The schema specifications for this file are documented here:
# https://github.com/cognizant-ai-lab/neuro-san/blob/main/docs/test_case_hocon_reference.md
#
# You can run this test by doing the following:
# https://github.dev/cognizant-ai-lab/neuro-san-studio/blob/355_add_smoke_test_using_music_pro_hocon/CONTRIBUTING.md#testing-guidelines

import re

import pytest


class FailFastParamMixin:
    """
    Mixin that provides fail-fast behavior for parameterized, HOCON-driven E2E tests.

    What it does
    ------------
    - For a single parameterized test *group* (i.e., all cases generated from one base
    test method), if any case fails, all remaining cases in that same group are skipped.
    This avoids cascading failures and saves runtime.

    How it works
    ------------
    - Uses shared per-class state (_fail_fast_flags) so that later parameterized cases
    can observe failures from earlier cases within the same group.
    - Derives a stable "group key" from the base test method name (from unittest's
    generated self._testMethodName created by parameterized.expand).
    - Calls pytest.skip(...) to skip remaining cases after the first failure.

    Important notes
    ---------------
    - This is not a global "stop pytest" feature; it only affects test methods that
    explicitly use this mixin helper (e.g., run_hocon_fail_fast / _fail_fast_skip_if_failed).
    - Designed for unittest.TestCase + parameterized.expand style tests (not pure pytest
    parametrize fixtures).
    """

    # Shared state per test class (NOT per instance):
    # key = group name string
    # val = True if any case in that group has failed
    _fail_fast_flags = {}

    def _fail_fast_skip_if_failed(self, key: str):
        """
        If a previous case failed for this group, skip this case.
        """
        if self.__class__._fail_fast_flags.get(key, False):  # noqa: SLF001
            pytest.skip(f"Earlier case failed for fail-fast group '{key}'")

    def _fail_fast_mark_failed(self, key: str):
        """
        Mark a group as having failed so future cases skip.
        """
        self.__class__._fail_fast_flags[key] = True  # noqa: SLF001

    def run_hocon_group_fail_fast_case(self, test_name: str, test_hocon: str):
        """
        Run one HOCON-driven E2E test case with FAIL-FAST behavior for the *parameterized group*.

        This helper is intended for end-to-end (E2E) integration tests where:
        - Each .hocon file represents one full scenario/case.
        - If one scenario fails, running the remaining scenarios is often not useful
            (it usually causes cascading failures and wastes runtime).

        How grouping works:
        - parameterized.expand generates a unique unittest-style method name per case, e.g.
            test_hocon_xxx_e2e_7_some_description
        - We derive the *base* method name by stripping "_<index>_<rest...>"
            so all cases from the same original test method share ONE group key.
        - Once any case in the group fails, remaining cases in that group are skipped.
        """

        # Base method name for the current parameterized group
        group = re.sub(r"_\d+_.*$", "", self._testMethodName)

        # ------------------------------------------------------------
        # FAIL-FAST GROUP (base test method name)
        # ------------------------------------------------------------
        self._fail_fast_skip_if_failed(group)

        try:
            # Run your existing dynamic driver
            self.DYNAMIC.one_test_hocon(self, test_name, test_hocon)
        except Exception:
            # Mark group as failed so remaining cases skip
            self._fail_fast_mark_failed(group)
            raise
