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

"""Tests for the Network Consultant safe-stop exception."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.stuck_patch_error import StuckPatchError


class TestStuckPatchError(TestCase):
    """Verify the safe-stop error preserves its actionable diagnostic."""

    def test_message_is_preserved(self) -> None:
        """Expose the actionable patch failure through the exception message."""
        error = StuckPatchError("unsupported HOCON style")

        self.assertEqual("unsupported HOCON style", str(error))
