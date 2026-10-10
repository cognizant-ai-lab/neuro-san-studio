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

"""Tests for the resolved Agent Network Consultant target interface."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget


class TestConsultantTarget(TestCase):
    """Verify resolved target values are exposed through accessors."""

    def test_returns_resolved_target_values(self) -> None:
        """Return every value needed by orchestration without exposing attributes."""
        target = ConsultantTarget("example.hocon", "example", "Preserve behavior", "registries/example.hocon")

        self.assertEqual(target.hocon_file(), "example.hocon")
        self.assertEqual(target.network_name(), "example")
        self.assertEqual(target.direction(), "Preserve behavior")
        self.assertEqual(target.hocon_path(), "registries/example.hocon")
