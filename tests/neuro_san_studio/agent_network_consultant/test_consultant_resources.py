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

"""Tests for Consultant cleanup resources."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_resources import ConsultantResources


class TestConsultantResources(TestCase):
    """Verify cleanup resources are updated only through their interface."""

    def test_returns_an_isolated_copy_of_success_ratio_overrides(self) -> None:
        """Prevent callers from mutating stored fixture execution overrides."""
        resources = ConsultantResources()
        resources.remember_success_ratio_overrides(["fixture.hocon"], "3/3")

        ratios = resources.success_ratio_overrides()
        ratios.clear()

        self.assertEqual(resources.success_ratio_overrides(), {"fixture.hocon": "3/3"})
        self.assertTrue(resources.has_success_ratio_overrides())

    def test_remembers_the_active_git_worktree(self) -> None:
        """Return the worktree retained for cleanup."""
        resources = ConsultantResources()

        resources.set_git_worktree("worktree")

        self.assertEqual(resources.git_worktree(), "worktree")
