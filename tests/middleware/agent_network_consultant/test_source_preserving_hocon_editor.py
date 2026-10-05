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

"""Characterization tests for the consultant's surgical HOCON edits."""

from unittest import TestCase

from pyhocon import ConfigFactory

from middleware.agent_network_consultant.source_preserving_hocon_editor import SourcePreservingHoconEditor


class TestSourcePreservingHoconEditor(TestCase):
    """Prove instruction edits preserve the target network's AAOSA behavior."""

    NON_AAOSA = """{
        "tools": [
            {
                "name": "announcer",
                "function": {"description": "Says hello"},
                "instructions": "Say hello."
            }
        ]
    }
    """
    CHANGE = {"announcer": {"instructions": "Greet the user warmly."}}

    def test_non_aaosa_network_still_resolves(self) -> None:
        """
        Do not inject an undefined AAOSA substitution into a basic network.
        """
        updated = SourcePreservingHoconEditor.update_text(self.NON_AAOSA, self.CHANGE)

        self.assertNotIn("${aaosa_instructions}", updated)
        ConfigFactory.parse_string(updated, resolve=True)

    def test_aaosa_network_keeps_one_substitution(self) -> None:
        """
        Recognize both supported AAOSA include variants without duplication.
        """
        includes: tuple[str, str] = ('include "registries/aaosa.hocon",', 'include "aaosa_basic.hocon",')
        for include in includes:
            with self.subTest(include=include):
                source = self.NON_AAOSA.replace("{\n", "{\n        " + include + "\n", 1)

                updated = SourcePreservingHoconEditor.update_text(source, self.CHANGE)

                self.assertEqual(updated.count("${aaosa_instructions}"), 1)

    def test_description_edit_never_adds_instruction_substitution(self) -> None:
        """
        Keep instruction-only substitutions away from function descriptions.
        """
        source = self.NON_AAOSA.replace("{\n", '{\n        include "registries/aaosa.hocon",\n', 1)

        updated = SourcePreservingHoconEditor.update_text(
            source, {"announcer": {"description": "Offers a warm greeting."}}
        )

        self.assertIn("Offers a warm greeting.", updated)
        self.assertEqual(updated.count("${aaosa_instructions}"), 0)
