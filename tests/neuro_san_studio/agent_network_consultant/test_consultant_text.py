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

"""Tests for shared Agent Network Consultant text-interface checks."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_text import ConsultantText


class TestConsultantText(TestCase):
    """Verify text normalization accepts text and rejects incompatible values."""

    def test_text_value_returns_text(self) -> None:
        """Return a value that provides the expected text interface."""
        self.assertEqual("message", ConsultantText.text_value("message"))

    def test_text_value_rejects_a_nontext_value(self) -> None:
        """Reject a value that does not provide the expected text interface."""
        self.assertIsNone(ConsultantText.text_value(42))

    def test_required_text_raises_the_callers_contract_error(self) -> None:
        """Raise the caller-provided error when a required value is not text."""
        with self.assertRaisesRegex(TypeError, "response must be text"):
            ConsultantText.required_text(None, "response must be text")
