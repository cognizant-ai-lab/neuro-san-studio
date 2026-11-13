# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""Tests for Agent Network Consultant option validation."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_option_validator import ConsultantOptionValidator
from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions


class TestConsultantOptionValidator(TestCase):
    """Verify option combinations and safe HOCON references before runtime setup."""

    def test_validate_accepts_one_existing_network(self) -> None:
        """Normalize a registries-relative existing-network selection."""
        options = ConsultantOptions(hocon_file="registries/basic/example.hocon")

        normalized_hocon_file = ConsultantOptionValidator(options).validate()

        self.assertEqual("basic/example.hocon", normalized_hocon_file)

    def test_validate_accepts_one_use_case(self) -> None:
        """Allow generation when a use case is supplied without an existing network."""
        options = ConsultantOptions(use_case="Build a helpdesk network")

        normalized_hocon_file = ConsultantOptionValidator(options).validate()

        self.assertIsNone(normalized_hocon_file)

    def test_validate_rejects_invalid_option_values(self) -> None:
        """Reject negative iteration limits, unknown policies, and malformed ratios."""
        invalid_options = (
            (ConsultantOptions(hocon_file="example.hocon", max_iterations=-1), "zero or greater"),
            (ConsultantOptions(hocon_file="example.hocon", ungrounded="unknown"), "--ungrounded"),
            (ConsultantOptions(hocon_file="example.hocon", success_ratio="0/1"), "positive N/M"),
            (ConsultantOptions(hocon_file="example.hocon", success_ratio="2/1"), "positive N/M"),
            (ConsultantOptions(hocon_file="example.hocon", success_ratio="invalid"), "positive N/M"),
        )

        for options, expected_message in invalid_options:
            with self.subTest(options=options):
                with self.assertRaisesRegex(ValueError, expected_message):
                    ConsultantOptionValidator(options).validate()

    def test_validate_requires_exactly_one_target_source(self) -> None:
        """Reject missing and conflicting target selections."""
        invalid_options = (
            ConsultantOptions(),
            ConsultantOptions(use_case="Build a network", hocon_file="example.hocon"),
        )

        for options in invalid_options:
            with self.subTest(options=options):
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    ConsultantOptionValidator(options).validate()

    def test_normalize_hocon_reference_rejects_unsafe_paths(self) -> None:
        """Reject drive-qualified, UNC, parent-relative, and non-HOCON paths."""
        invalid_references = (
            "C:\\outside.hocon",
            "../outside.hocon",
            "\\\\server\\share\\outside.hocon",
            "basic/example.json",
        )

        for value in invalid_references:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "safe .hocon path"):
                    ConsultantOptionValidator.normalize_hocon_reference(value)
