# Copyright © 2026 Cognizant Technology Solutions Corp, www.cognizant.com.
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

"""Tests for DesignerCommonInstructions: the reservations templates carry the same common instructions."""

from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase

from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

from middleware.agent_network_designer.persistence.designer_common_instructions import DesignerCommonInstructions

PERSISTENCE_DIR: Path = Path(__file__).resolve().parents[4] / "middleware" / "agent_network_designer" / "persistence"


class TestDesignerCommonInstructions(IsolatedAsyncioTestCase):
    """
    Pins the common instructions in deployable_template.hocon and deployable_template_demo.hocon to
    DesignerCommonInstructions.

    HoconAgentNetworkAssembler builds its header and top-agent template from the constants, but the reservations
    templates are HOCON files and hold their own copies. CommonInstructionStripper strips copies by the
    constants' words, so a template reworded on its own would bring back the growth of copies for networks
    saved in reservations mode. The template texts are compared word by word, as the stripper matches them.
    """

    async def test_reservations_prefix_is_the_designer_prefix(self) -> None:
        """
        The prefix in the reservations template is the opening words, the network name and the three rules.
        """
        template: dict[str, Any] = await self._restore("deployable_template_standard.hocon")

        expected: list[str] = DesignerCommonInstructions.PREFIX_OPENING.split()
        expected.append("{agent_network_name}.")
        expected.extend(DesignerCommonInstructions.PREFIX_RULES.split())
        self.assertEqual(self._replacement_string(template, "instructions_prefix").split(), expected)

    async def test_reservations_demo_sentence_is_the_designer_demo_sentence(self) -> None:
        """
        The demo template's demo sentence is DEMO_SENTENCE, and the standard template has none.
        """
        demo_template: dict[str, Any] = await self._restore("deployable_template_demo.hocon")
        standard_template: dict[str, Any] = await self._restore("deployable_template_standard.hocon")

        self.assertEqual(
            self._replacement_string(demo_template, "demo_mode").split(),
            DesignerCommonInstructions.DEMO_SENTENCE.split(),
        )
        self.assertEqual(self._replacement_string(standard_template, "demo_mode"), "")

    async def test_reservations_templates_give_each_role_the_designer_pieces(self) -> None:
        """
        The top template writes the front man's lines between the prefix and the agent's text; the top and regular
        templates end with the AAOSA instructions; only the leaf template has the demo sentence.
        """
        template: dict[str, Any] = await self._restore("deployable_template_standard.hocon")
        tools: list[dict[str, Any]] = template.get("tools")

        expected_top: list[str] = ["{instructions_prefix}"]
        expected_top.extend(DesignerCommonInstructions.FRONT_MAN_LINES.split())
        expected_top.extend(["{agent_instructions}", "{aaosa_instructions}"])
        self.assertEqual(tools[0].get("instructions").split(), expected_top)
        self.assertEqual(
            tools[1].get("instructions").split(),
            ["{instructions_prefix}", "{agent_instructions}", "{aaosa_instructions}"],
        )
        self.assertEqual(
            tools[2].get("instructions").split(), ["{instructions_prefix}", "{demo_mode}", "{agent_instructions}"]
        )

    @staticmethod
    async def _restore(file_name: str) -> dict[str, Any]:
        """
        Read a reservations template the way DeployableAgentNetworkAssembler does.

        :param file_name: The template's file name in the persistence package
        :return: The parsed template; its include of deployable_template.hocon resolves against the working
                directory, which is the repository root under pytest
        """
        restorer: AbstractAsyncConfigRestorer = AbstractAsyncConfigRestorer(
            "DesignerCommonInstructions test template reader"
        )
        return await restorer.async_restore(file_reference=str(PERSISTENCE_DIR / file_name))

    @staticmethod
    def _replacement_string(template: dict[str, Any], key: str) -> str:
        """
        Read one of the template's commondefs replacement strings.

        :param template: A parsed reservations template
        :param key: The replacement string's key
        :return: The replacement string
        """
        return template.get("commondefs").get("replacement_strings").get(key)
