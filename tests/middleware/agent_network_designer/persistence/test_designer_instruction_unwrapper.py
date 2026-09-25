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

"""Tests for DesignerInstructionUnwrapper: one wrapper copy per save, own text kept as written (issue #1458)."""

import time
import tracemalloc
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase

from pyhocon import ConfigFactory
from pyhocon import ConfigTree

from middleware.agent_network_designer.persistence.deployable_agent_network_assembler import (
    DeployableAgentNetworkAssembler,
)
from middleware.agent_network_designer.persistence.designer_instruction_unwrapper import DesignerInstructionUnwrapper
from middleware.agent_network_designer.persistence.designer_wrapper_texts import DesignerWrapperTexts
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler

REPO_ROOT: Path = Path(__file__).resolve().parents[4]

# A definition holding only the agents' own text, as the designer's contract has it: a front man, an agent with
# tools whose text spans indented lines, a leaf with a blank line in its text and a toolbox reference.
DEFINITION: dict[str, Any] = {
    "front": {"instructions": "Route travel requests.", "tools": ["booker", "weather", "search"]},
    "booker": {"instructions": "Book trips.\n  - flights\n    - direct only\n  - hotels", "tools": ["weather"]},
    "weather": {"instructions": "Report the weather.\n\nUse Celsius."},
    "search": {},
}
NETWORK_NAME: str = "travel"

# Words that occur once in each wrapper piece and nowhere in DEFINITION, for counting copies.
PREFIX_MARKER: str = DesignerWrapperTexts.PREFIX_OPENING
FRONT_MAN_MARKER: str = "Never express irrelevance"
DEMO_MARKER: str = "You are part of a demo system"
AAOSA_MARKER: str = "When you receive an inquiry, you will:"


class TestDesignerInstructionUnwrapper(IsolatedAsyncioTestCase):
    """
    Tests for DesignerInstructionUnwrapper.

    The round-trip tests save a definition with the real assemblers, read the result back the way a client does
    (the HOCON file parsed with its substitutions resolved, or the reservations spec as deployed) and feed the
    instructions back through the unwrapper, which must return the own text the save started from. The other
    tests cover pieces left from a role the agent no longer has, text that must be left alone, wrapper-only text
    and the running time.
    """

    async def asyncSetUp(self) -> None:
        """
        Read the AAOSA instructions every generated network includes.
        """
        aaosa_config: ConfigTree = ConfigFactory.parse_file(str(REPO_ROOT / "registries" / "aaosa.hocon"))
        self.aaosa: str = aaosa_config.get("aaosa_instructions")

    async def test_hocon_round_trip_returns_the_own_text(self) -> None:
        """
        A definition saved as a HOCON file and read back resolved comes back as the own text, demo mode on or off.
        """
        for demo_mode in (True, False):
            with self.subTest(demo_mode=demo_mode):
                resolved: dict[str, Any] = await self._hocon_round_trip(DEFINITION, NETWORK_NAME, demo_mode)
                self.assertEqual(resolved.get("front").get("instructions").count(AAOSA_MARKER), 1)

                unwrapped: dict[str, Any]
                unwrapped, _ = self._unwrapper().unwrap_definition(resolved)

                self.assertEqual(unwrapped, DEFINITION)

    async def test_reservations_round_trip_returns_the_own_text(self) -> None:
        """
        A definition deployed as a reservations spec in demo mode comes back as the own text. Demo mode off is not
        covered: there the leaf template's "{demo_mode}" placeholder stays in the deployed text as written, because
        neuro-san's StringCommonDefsConfigFilter skips an empty replacement string (issue #1466).
        """
        deployed: dict[str, Any] = await self._reservations_round_trip(DEFINITION, NETWORK_NAME, True)
        self.assertEqual(deployed.get("front").get("instructions").count(FRONT_MAN_MARKER), 1)
        self.assertEqual(deployed.get("weather").get("instructions").count(DEMO_MARKER), 1)

        unwrapped: dict[str, Any]
        unwrapped, _ = self._unwrapper().unwrap_definition(deployed)

        self.assertEqual(unwrapped, DEFINITION)

    async def test_heals_the_copies_left_by_earlier_saves(self) -> None:
        """
        Three saves of resolved text without the unwrapper stack three copies of every piece; one pass removes
        them all, including the interleaved prefix and front man's lines at the start of the front man's text.
        """
        corrupted: dict[str, Any] = deepcopy(DEFINITION)
        for _ in range(3):
            corrupted = await self._hocon_round_trip(corrupted, NETWORK_NAME, True)
        front: str = corrupted.get("front").get("instructions")
        self.assertEqual(front.count(PREFIX_MARKER), 3)
        self.assertEqual(front.count(FRONT_MAN_MARKER), 3)
        self.assertEqual(front.count(AAOSA_MARKER), 3)
        self.assertEqual(corrupted.get("weather").get("instructions").count(DEMO_MARKER), 3)

        unwrapped: dict[str, Any]
        changed: list[str]
        unwrapped, changed = self._unwrapper().unwrap_definition(corrupted)

        self.assertEqual(unwrapped, DEFINITION)
        self.assertEqual(changed, ["front", "booker", "weather"])

    async def test_saving_unwrapped_text_again_and_again_keeps_one_copy(self) -> None:
        """
        Unwrapping before each save, as the designer now does, keeps every piece at one copy over many saves.
        """
        definition: dict[str, Any] = deepcopy(DEFINITION)
        for _ in range(4):
            resolved: dict[str, Any] = await self._hocon_round_trip(definition, NETWORK_NAME, True)
            self.assertEqual(resolved.get("front").get("instructions").count(AAOSA_MARKER), 1)
            self.assertEqual(resolved.get("weather").get("instructions").count(DEMO_MARKER), 1)
            definition, _ = self._unwrapper().unwrap_definition(resolved)
        self.assertEqual(definition, DEFINITION)

    async def test_strips_a_prefix_saved_under_another_network_name(self) -> None:
        """
        A copy of the prefix names the network it was saved under, which can differ from this save's name (nsflow
        saves a loaded network as generated/<name>); it is stripped all the same.
        """
        once: dict[str, Any] = await self._hocon_round_trip(DEFINITION, "old_name", True)
        twice: dict[str, Any] = await self._hocon_round_trip(once, "generated/new_name", True)
        front: str = twice.get("front").get("instructions")
        self.assertIn(f"{PREFIX_MARKER} old_name.", front)
        self.assertIn(f"{PREFIX_MARKER} generated/new_name.", front)

        unwrapped: dict[str, Any]
        unwrapped, _ = self._unwrapper().unwrap_definition(twice)

        self.assertEqual(unwrapped, DEFINITION)

    async def test_strips_a_prefix_saved_under_a_network_name_with_spaces(self) -> None:
        """
        Nothing stops a client from naming a network with spaces, and the prefix copies such a save writes are
        stripped like any other, including under a different name with spaces.
        """
        once: dict[str, Any] = await self._hocon_round_trip(DEFINITION, "My Travel Desk", True)
        twice: dict[str, Any] = await self._hocon_round_trip(once, "Travel Desk v2", True)
        self.assertIn(f"{PREFIX_MARKER} My Travel Desk.", twice.get("front").get("instructions"))

        unwrapped: dict[str, Any]
        unwrapped, _ = self._unwrapper().unwrap_definition(twice)

        self.assertEqual(unwrapped, DEFINITION)

    def test_strips_the_prefix_in_its_legacy_wording(self) -> None:
        """
        Networks generated before 22a84541 opened the prefix with "You are part of a <name> of assistants.".
        """
        legacy_prefix: str = (
            f"\n{DesignerWrapperTexts.LEGACY_PREFIX_OPENING} travel {DesignerWrapperTexts.LEGACY_PREFIX_CLOSING}\n"
            f"{DesignerWrapperTexts.PREFIX_RULES}\n"
        )
        instructions: str = f"{self._prefix('travel')} {legacy_prefix} \nReport the weather.\n"

        self.assertEqual(self._unwrapper().unwrap(instructions), "Report the weather.")

    def test_leaves_text_without_the_wrapper_unchanged(self) -> None:
        """
        Text that holds no whole copy at its start or end comes back byte for byte, outer whitespace included: a
        custom prefix, the prefix's rules at the end of the text (registries/basic/wolfram_mcp.hocon), a reworded
        prefix, wrapper sentences quoted mid-text, and a hand-written prefix in the legacy wording with a name of
        several words.
        """
        texts: list[str] = [
            "Follow the airline policy at all times.\nQuote the relevant policy section.",
            f"Use the Wolfram Alpha tool for math.\n{DesignerWrapperTexts.PREFIX_RULES}",
            f"{PREFIX_MARKER} travel. Only answer questions about travel.",
            f"Start here.\n{DesignerWrapperTexts.FRONT_MAN_LINES}\n{self.aaosa}\nEnd here.",
            "   Surrounding whitespace stays.\n\n",
            # A hand-written network's own prefix in the legacy wording with a longer name
            # (registries/basic/smart_home.hocon), which no designer version wrote.
            f"You are part of a smart home network of assistants.\n{DesignerWrapperTexts.PREFIX_RULES}\nOwn text.",
        ]
        for text in texts:
            with self.subTest(text=text[:30]):
                self.assertEqual(self._unwrapper().unwrap(text), text)

    def test_blank_instructions_are_left_for_validation(self) -> None:
        """
        Empty or blank instructions hold nothing to strip and come back as they are, for the validators to report.
        """
        for text in ("", "   \n  "):
            with self.subTest(text=repr(text)):
                self.assertEqual(self._unwrapper().unwrap(text), text)

    async def test_strips_the_pieces_of_a_role_the_agent_no_longer_has(self) -> None:
        """
        Roles can change between the save and the definition sent back, as when a user edits the network in a
        client: here the front man gets a new agent above it, the agent with tools loses them and the leaf gains
        one. Each keeps only its own text, not the pieces its old role was saved with.
        """
        resolved: dict[str, Any] = await self._hocon_round_trip(DEFINITION, NETWORK_NAME, True)
        resolved["new_front"] = {"instructions": "Greet the traveller.", "tools": ["front"]}
        resolved.get("booker").pop("tools")
        resolved.get("weather")["tools"] = ["search"]

        unwrapped: dict[str, Any]
        unwrapped, _ = self._unwrapper().unwrap_definition(resolved)

        for agent_name in ("front", "booker", "weather"):
            with self.subTest(agent=agent_name):
                own_text: str = DEFINITION.get(agent_name).get("instructions")
                self.assertEqual(unwrapped.get(agent_name).get("instructions"), own_text)

    def test_strips_the_aaosa_instructions_a_hand_written_leaf_ends_with(self) -> None:
        """
        Some hand-written networks give leaves the AAOSA instructions (registries/basic/smart_home.hocon, for one).
        The designer never writes them for a leaf, so once such a network is loaded they are removed like any other
        copy, and the saved leaf works like the ones the designer writes.
        """
        instructions: str = f"{self._prefix(NETWORK_NAME)} \nYour name is Book. You're a book.\n{self.aaosa}"

        self.assertEqual(self._unwrapper().unwrap(instructions), "Your name is Book. You're a book.")

    async def test_heals_demo_mode_copies_once_demo_mode_is_turned_off(self) -> None:
        """
        A network whose copies stacked up in demo mode before the fix loses them all, demo sentences included,
        when it is next saved with demo mode off, and that save writes no demo sentence.
        """
        corrupted: dict[str, Any] = deepcopy(DEFINITION)
        for _ in range(3):
            corrupted = await self._hocon_round_trip(corrupted, NETWORK_NAME, True)
        self.assertEqual(corrupted.get("weather").get("instructions").count(DEMO_MARKER), 3)

        unwrapped: dict[str, Any]
        unwrapped, _ = self._unwrapper().unwrap_definition(corrupted)
        saved: dict[str, Any] = await self._hocon_round_trip(unwrapped, NETWORK_NAME, False)

        self.assertEqual(unwrapped, DEFINITION)
        self.assertEqual(saved.get("weather").get("instructions").count(DEMO_MARKER), 0)
        self.assertEqual(saved.get("weather").get("instructions").count(PREFIX_MARKER), 1)

    async def test_wrapper_only_text_keeps_one_copy_of_each_piece_over_saves(self) -> None:
        """
        A front man whose text is nothing but wrapper keeps one copy of each piece rather than an empty text, which
        would fail validation, and that text is the same after every later save instead of growing.
        """
        resolved: dict[str, Any] = await self._hocon_round_trip(DEFINITION, NETWORK_NAME, True)
        wrapper_only: str = resolved.get("front").get("instructions").replace("Route travel requests.", "")

        kept: str = self._unwrapper().unwrap(wrapper_only)
        self.assertEqual(kept.count(PREFIX_MARKER), 1)
        self.assertEqual(kept.count(FRONT_MAN_MARKER), 1)
        self.assertEqual(kept.count(AAOSA_MARKER), 1)
        # In the order a save writes them.
        self.assertLess(kept.index(PREFIX_MARKER), kept.index(FRONT_MAN_MARKER))
        self.assertLess(kept.index(FRONT_MAN_MARKER), kept.index(AAOSA_MARKER))

        after_saves: list[str] = []
        definition: dict[str, Any] = deepcopy(DEFINITION)
        definition.get("front")["instructions"] = kept
        for _ in range(3):
            resolved = await self._hocon_round_trip(definition, NETWORK_NAME, True)
            # One copy from the own text and one from the save, never more.
            self.assertEqual(resolved.get("front").get("instructions").count(AAOSA_MARKER), 2)
            definition, _ = self._unwrapper().unwrap_definition(resolved)
            after_saves.append(definition.get("front").get("instructions"))
        self.assertEqual(after_saves[1], after_saves[0])
        self.assertEqual(after_saves[2], after_saves[1])

    def test_unwrap_definition_passes_malformed_entries_through(self) -> None:
        """
        Entries that are not agents, or whose instructions are not text, are left for the validators to report,
        while the agents around them are unwrapped; a value that is not a definition at all comes back as it is.
        """
        wrapped_front: str = (
            f"{self._prefix(NETWORK_NAME)} \n{DesignerWrapperTexts.FRONT_MAN_LINES}\nLead.\n{self.aaosa}"
        )
        definition: dict[str, Any] = {
            "first": {"instructions": wrapped_front, "tools": ["shared"]},
            "shared": {"instructions": "Share."},
            "not_an_agent": "text",
            "odd_instructions": {"instructions": ["a", "list"]},
        }
        not_a_definition: list[str] = ["first", "shared"]

        unwrapped: dict[str, Any]
        changed: list[str]
        unwrapped, changed = self._unwrapper().unwrap_definition(definition)
        passed: Any
        passed_changed: list[str]
        passed, passed_changed = self._unwrapper().unwrap_definition(not_a_definition)

        self.assertEqual(changed, ["first"])
        self.assertEqual(unwrapped.get("first").get("instructions"), "Lead.")
        self.assertIs(unwrapped.get("not_an_agent"), definition.get("not_an_agent"))
        self.assertIs(unwrapped.get("odd_instructions"), definition.get("odd_instructions"))
        self.assertIs(passed, not_a_definition)
        self.assertEqual(passed_changed, [])

    async def test_unwrap_definition_copies_only_the_agents_it_changes(self) -> None:
        """
        The definition passed in is never modified; agents without a copy stay the same objects, and a definition
        without any copy comes back as the same object with nothing reported.
        """
        resolved: dict[str, Any] = await self._hocon_round_trip(DEFINITION, NETWORK_NAME, True)
        resolved["search"] = {"instructions": "Search the web.", "tools": ["https://example.com/mcp"]}
        sent: dict[str, Any] = deepcopy(resolved)

        unwrapped: dict[str, Any]
        changed: list[str]
        unwrapped, changed = self._unwrapper().unwrap_definition(resolved)
        clean: dict[str, Any] = deepcopy(DEFINITION)
        clean_result: dict[str, Any]
        clean_changed: list[str]
        clean_result, clean_changed = self._unwrapper().unwrap_definition(clean)

        self.assertEqual(resolved, sent)
        self.assertEqual(changed, ["front", "booker", "weather"])
        self.assertIs(unwrapped.get("search"), resolved.get("search"))
        self.assertIs(clean_result, clean)
        self.assertEqual(clean_changed, [])

    def test_unwraps_long_text_and_many_copies_quickly(self) -> None:
        """
        A long whitespace run in the own text with fifty stacked copies at each end, and four hundred AAOSA copies
        ahead of other text, take a fraction of a second together. A regular expression anchored at the end of the
        text takes about a second on the second input alone, since it is quadratic there.
        """
        own_text: str = "Own text." + " " * 200_000 + "More own text."
        leading: str = f"{self._prefix(NETWORK_NAME)} {DesignerWrapperTexts.FRONT_MAN_LINES} " * 50
        stacked: str = leading + own_text + f" {self.aaosa}" * 50
        not_trailing: str = f"{self._prefix(NETWORK_NAME)} Own text. " + f"{self.aaosa} " * 400 + "Then this."

        started: float = time.perf_counter()
        stacked_result: str = self._unwrapper().unwrap(stacked)
        not_trailing_result: str = self._unwrapper().unwrap(not_trailing)
        elapsed: float = time.perf_counter() - started

        self.assertEqual(stacked_result, own_text)
        self.assertTrue(not_trailing_result.startswith("Own text."))
        self.assertTrue(not_trailing_result.endswith("Then this."))
        self.assertLess(elapsed, 0.25)

    def test_reads_only_the_ends_of_a_long_text(self) -> None:
        """
        Only the words at the two ends of a text are read, so two megabytes of own text between the copies cost
        about a millisecond and no more memory than two copies of the text, whatever it holds.
        """
        own_text: str = "a " * 1_000_000
        wrapped: str = (
            f"{self._prefix(NETWORK_NAME)} \n{DesignerWrapperTexts.FRONT_MAN_LINES}\n{own_text}\n{self.aaosa}"
        )

        tracemalloc.start()
        started: float = time.perf_counter()
        clean_result: str = self._unwrapper().unwrap(own_text)
        wrapped_result: str = self._unwrapper().unwrap(wrapped)
        elapsed: float = time.perf_counter() - started
        peak: int
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertIs(clean_result, own_text)
        self.assertEqual(wrapped_result, own_text.strip())
        self.assertLess(elapsed, 0.25)
        self.assertLess(peak, 3 * len(wrapped))

    def _unwrapper(self) -> DesignerInstructionUnwrapper:
        """
        Build the unwrapper the designer builds for a save.

        :return: An unwrapper for the AAOSA instructions of registries/aaosa.hocon and the fixed wrapper texts
        """
        return DesignerInstructionUnwrapper(self.aaosa)

    @staticmethod
    def _prefix(network_name: str) -> str:
        """
        Spell the prefix the way a generated file resolves it.

        :param network_name: The network name the prefix carries
        :return: The prefix, with the line breaks of the file's triple-quoted value
        """
        return f"\n{DesignerWrapperTexts.PREFIX_OPENING} {network_name}.\n{DesignerWrapperTexts.PREFIX_RULES}\n"

    async def _hocon_round_trip(
        self, definition: dict[str, Any], network_name: str, demo_mode: bool
    ) -> dict[str, Any]:
        """
        Save a definition as HOCON and read it back as a client does, with the substitutions resolved.

        :param definition: The definition to save
        :param network_name: The network name to save it under
        :param demo_mode: Whether the save runs in demo mode
        :return: The definition read back from the saved text
        """
        text: str = await HoconAgentNetworkAssembler(demo_mode).assemble_agent_network(
            definition, "front", network_name, []
        )
        # The generated file's includes are relative to the repository root.
        config: ConfigTree = ConfigFactory.parse_string(text, basedir=str(REPO_ROOT))
        return self._definition_from_tools(config.get("tools"))

    async def _reservations_round_trip(
        self, definition: dict[str, Any], network_name: str, demo_mode: bool
    ) -> dict[str, Any]:
        """
        Deploy a definition as a reservations spec and read the agents back from it.

        :param definition: The definition to deploy
        :param network_name: The network name to deploy it under
        :param demo_mode: Whether the save runs in demo mode
        :return: The definition read back from the spec
        """
        spec: dict[str, Any] = await DeployableAgentNetworkAssembler(demo_mode).assemble_agent_network(
            definition, "front", network_name, []
        )
        return self._definition_from_tools(spec.get("tools"))

    @staticmethod
    def _definition_from_tools(tools: list[Any]) -> dict[str, Any]:
        """
        Turn a network's "tools" list back into a definition of instructions and tools.

        :param tools: The agent specs of a saved network
        :return: Agent name to its instructions and, when it has them, its tools; toolbox references map to {}
        """
        definition: dict[str, Any] = {}
        for agent in tools:
            entry: dict[str, Any] = {}
            instructions: str | None = agent.get("instructions", None)
            if instructions is not None:
                entry["instructions"] = instructions
            agent_tools: list[str] | None = agent.get("tools", None)
            if agent_tools:
                entry["tools"] = list(agent_tools)
            definition[agent.get("name")] = entry
        return definition
