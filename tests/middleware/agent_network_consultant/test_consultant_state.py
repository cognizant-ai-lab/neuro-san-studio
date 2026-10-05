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

"""Tests for the private state keys shared by Network Consultant middleware."""

from unittest import TestCase

from middleware.agent_network_consultant.consultant_state import ConsultantState


class TestConsultantState(TestCase):
    """Verify the middleware contract uses stable, distinct sly-data keys."""

    def test_keys_are_distinct_nonempty_strings(self) -> None:
        """Verify every middleware state key is usable and unique."""
        keys: tuple[str, ...] = (
            ConsultantState.AGENT_NETWORK_CHANGES,
            ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT,
            ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS,
            ConsultantState.AGENT_NETWORK_SOURCE_FILE,
        )

        self.assertTrue(all(keys))
        self.assertEqual(len(keys), len(set(keys)))
