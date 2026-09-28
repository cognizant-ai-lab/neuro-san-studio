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
"""
Removal of copies of the designer's common instructions from the instructions in an agent network definition.
"""

import re
from typing import Any

from middleware.agent_network_designer.persistence.designer_common_instructions import DesignerCommonInstructions


class CommonInstructionStripper:
    """
    Strips copies of the designer's common instructions from agent instructions, so that a save adds exactly one.

    The instructions in agent_network_definition are meant to hold only each agent's custom instructions, its own
    text: every save adds the common instructions again, which are the prefix, the front man's lines, the demo
    sentence and the AAOSA instructions (see DesignerCommonInstructions). A client that reads a saved network with
    its HOCON substitutions resolved gets them inlined in every agent's instructions. Sending that text back as
    the definition used to add one more copy of each piece per save.

    All four pieces are stripped from every agent, whatever its role and whether demo mode is on. The definition
    never needs them, since each save adds back the ones the agent's role calls for. Stripping only those would
    leave a piece behind as own text whenever an agent's role or the demo setting changed between saves: a leaf
    that gained tools would keep the demo sentence, an agent that lost its tools the AAOSA instructions, and a
    network saved in demo mode would keep its demo sentences once demo mode was turned off. Hand-written networks
    that give leaves the AAOSA instructions on purpose (registries/basic/smart_home.hocon, for one) lose them there
    once loaded into the designer, and after a save their leaves work like the ones the designer writes.

    Each piece is matched in one wording only: the one the save writes today, read from DesignerCommonInstructions
    and registries/aaosa.hocon exactly as the save reads them, so a change there changes what is stripped at the
    same time. Old wordings are not kept. A copy in a wording no save writes any more (the prefix of networks
    generated before October 2025, or the AAOSA text as it was before an edit of aaosa.hocon) is not recognized and
    stays in the agent's custom instructions, once. It cannot multiply: only what a save adds can come back again,
    and that is the current wording, which is what gets stripped. Hand-written prefixes that resemble a piece stay
    for the same reason ("You are part of a smart home network of assistants." in registries/basic/smart_home.hocon).

    How copies are matched:

    - Word by word, so copies that differ only in whitespace (indentation, line breaks) match; the text that
      remains keeps its own whitespace exactly as written.
    - Whole copies only, anchored at the start for the prefix, the front man's lines and the demo sentence, and
      at the end for the AAOSA instructions. A text that ends with the prefix's rules
      (registries/basic/wolfram_mcp.hocon) or quotes one of their sentences in the middle is left alone.
    - Every copy, however many there are and in whatever order: after several saves the leading pieces
      interleave (prefix, front man's lines, prefix, front man's lines, ...).
    - The prefix under any network name of up to MAX_NAME_WORDS words, followed by the period a save writes
      after it, since a copy carries the name the network was saved under, which can differ from the name of
      this save.
    - Only the words at the two ends of the text are ever read, and only the end is copied, to be read backwards
      (see _trailing_copy), so the cost grows with the copies stripped, not with the length of the text. The words
      are compared one by one rather than with a regular expression: a pattern anchored at the end of the text is
      quadratic when many copies of the AAOSA instructions come before other text, and this runs on the event loop
      before every model call.

    A text holding none of the common instructions is returned unchanged, byte for byte. A text holding nothing
    but copies of them keeps one copy of each piece found instead of becoming empty: an empty text fails the designer's
    validation (turning a plain save into an LLM run), and an empty leaf would be written as a toolbox reference.
    One copy of each is the smallest text that stays the same over any number of saves.
    """

    # One word of a text: what the matching compares, so whitespace never takes part in it.
    WORD: re.Pattern[str] = re.compile(r"\S+")

    # The most words a network name in a copy of the prefix may span. Names are usually one word, but nothing
    # stops a client from saving a network under a name with spaces, and its prefix copies must be stripped too.
    MAX_NAME_WORDS: int = 16

    # What a save writes right after the network name in the prefix. The name's last word in a copy must end
    # with it, or the words are not a whole copy of the prefix.
    NAME_ENDING: str = "."

    # Keys for the pieces, and the order a text made only of common instructions keeps them in, which is the
    # order a save writes them in.
    PREFIX: str = "prefix"
    FRONT_MAN_LINES: str = "front_man_lines"
    DEMO_SENTENCE: str = "demo_sentence"
    AAOSA_INSTRUCTIONS: str = "aaosa_instructions"
    PIECE_ORDER: tuple[str, ...] = (PREFIX, FRONT_MAN_LINES, DEMO_SENTENCE, AAOSA_INSTRUCTIONS)

    def __init__(self, aaosa_instructions: str | None) -> None:
        """
        Prepare the words of each piece.

        :param aaosa_instructions: The AAOSA instructions the save appends to the front man and to agents with
                tools, from registries/aaosa.hocon, or None to strip none
        """
        # The pieces a save writes before the custom instructions, as (key, words before the network name, words
        # after it). Only the prefix names the network; the other two are fixed texts, so their second list is
        # empty and their words are matched as they are.
        self.leading_pieces: list[tuple[str, list[str], list[str]]] = [
            (
                self.PREFIX,
                self._words(DesignerCommonInstructions.PREFIX_OPENING),
                self._words(DesignerCommonInstructions.PREFIX_RULES),
            ),
            (self.FRONT_MAN_LINES, self._words(DesignerCommonInstructions.FRONT_MAN_LINES), []),
            (self.DEMO_SENTENCE, self._words(DesignerCommonInstructions.DEMO_SENTENCE), []),
        ]
        # The AAOSA instructions, the one piece a save writes after the custom instructions. The end of a text is
        # read backwards (see _trailing_copy), so their words are kept last word first and each spelled backwards.
        # Empty when there are none to strip.
        self.reversed_aaosa: list[str] = self._reversed_words(aaosa_instructions)
        # How many characters _trailing_copy first reads from the end: twice a copy of the AAOSA instructions with
        # single spaces, so a copy with the indentation of registries/aaosa.hocon fits in one read.
        self.trailing_window: int = 1
        for word in self.reversed_aaosa:
            self.trailing_window += 2 * (len(word) + 1)

    def strip_definition(self, network_def: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """
        Strip the copies of the common instructions from the instructions of every agent in a definition.

        :param network_def: The agent network definition, agent name to agent dict. It is not modified.
        :return: The definition to use and the names of the agents whose instructions changed. When none changed,
                the definition is network_def itself; otherwise it is a new dict in which each changed agent is a
                copy with the new instructions and every other agent is the same object as before.
        """
        if not isinstance(network_def, dict):
            # Not a definition at all: the validators report it, and there is no agent to strip anything from.
            return network_def, []

        stripped_def: dict[str, Any] = {}
        changed: list[str] = []
        for agent_name, agent in network_def.items():
            stripped_def[agent_name] = agent
            if not isinstance(agent, dict):
                # Malformed entries are the validators' to report; there is nothing here to strip.
                continue
            instructions: Any = agent.get("instructions")
            if not isinstance(instructions, str):
                continue
            stripped: str = self.strip(instructions)
            if stripped != instructions:
                stripped_agent: dict[str, Any] = dict(agent)
                stripped_agent["instructions"] = stripped
                stripped_def[agent_name] = stripped_agent
                changed.append(agent_name)

        if not changed:
            return network_def, changed
        return stripped_def, changed

    def strip(self, instructions: str) -> str:
        """
        Strip every copy of the common instructions' pieces from an agent's instructions.

        :param instructions: The agent's instructions as received
        :return: The instructions unchanged when they hold no copy; otherwise the text between the copies,
                without the whitespace around it, or one copy of each piece found when nothing else remains
        """
        start: int
        end: int
        first_copies: dict[str, tuple[int, int]]
        start, end, first_copies = self._strip_copies(instructions)

        if not first_copies:
            return instructions
        remaining: str = instructions[start:end].strip()
        if remaining:
            return remaining

        # Nothing but common instructions: keep the first copy found of each piece, as written, in the order a
        # save writes them.
        kept: list[str] = []
        for piece in self.PIECE_ORDER:
            copy: tuple[int, int] | None = first_copies.get(piece)
            if copy is not None:
                kept.append(instructions[copy[0] : copy[1]])
        return "\n".join(kept)

    def _strip_copies(self, instructions: str) -> tuple[int, int, dict[str, tuple[int, int]]]:
        """
        Take every copy of the pieces off the start and the end of a text.

        :param instructions: The agent's instructions
        :return: The offsets that bound the text left, as instructions[start:end], and the offsets of the first
                copy found of each piece, by piece key
        """
        # Each pass takes the copies it finds at either end and the loop repeats until a pass finds none, because
        # the leading pieces can interleave. Every match consumes a whole copy, so the number of passes is bounded
        # by the number of copies.
        start: int = 0
        end: int = len(instructions)
        first_copies: dict[str, tuple[int, int]] = {}
        found: bool = True
        while found:
            found = False
            for piece, head, tail in self.leading_pieces:
                copy: tuple[int, int] | None = self._leading_copy(instructions, start, end, head, tail)
                while copy is not None:
                    first_copies.setdefault(piece, copy)
                    start = copy[1]
                    found = True
                    copy = self._leading_copy(instructions, start, end, head, tail)
            if self.reversed_aaosa:
                copy = self._trailing_copy(instructions, start, end)
                while copy is not None:
                    first_copies.setdefault(self.AAOSA_INSTRUCTIONS, copy)
                    end = copy[0]
                    found = True
                    copy = self._trailing_copy(instructions, start, end)
        return start, end, first_copies

    def _leading_copy(
        self, instructions: str, start: int, end: int, head: list[str], tail: list[str]
    ) -> tuple[int, int] | None:
        """
        Find a whole copy of a piece at the start of the text still left.

        :param instructions: The agent's instructions
        :param start: The offset the text still left begins at
        :param end: The offset the text still left ends at
        :param head: The words of the piece, up to the network name when the piece has one
        :param tail: The words after the network name, or an empty list for a piece without one
        :return: The offsets of the copy's first and past its last character, or None when the text does not
                begin with a copy
        """
        if not head:
            return None
        # A fixed piece spans its words; the prefix spans its head, a name of up to MAX_NAME_WORDS words and its
        # tail. Only that many words are read, and reading stops at the first word of the head that differs.
        limit: int = len(head)
        if tail:
            limit += self.MAX_NAME_WORDS + len(tail)
        words: list[str] = []
        spans: list[tuple[int, int]] = []
        for match in self.WORD.finditer(instructions, start, end):
            if len(words) < len(head) and match.group() != head[len(words)]:
                return None
            words.append(match.group())
            spans.append(match.span())
            if len(words) == limit:
                break

        length: int = self._copy_length(words, head, tail)
        if length == 0:
            return None
        return spans[0][0], spans[length - 1][1]

    def _copy_length(self, words: list[str], head: list[str], tail: list[str]) -> int:
        """
        Count the words a copy of a piece spans at the start of a list of words that begin with its head.

        :param words: The first words of the text still left, known to begin with the head as far as they go
        :param head: The words of the piece, up to the network name when the piece has one
        :param tail: The words after the network name, or an empty list for a piece without one
        :return: The number of words the copy spans, or 0 when the words do not hold a whole copy
        """
        if len(words) < len(head):
            return 0
        if not tail:
            return len(head)
        # Try the shortest name first: the words after the name are fixed, so at most one length can fit a real
        # copy, and a name cannot hold the rule sentences that follow it.
        for name_length in range(1, self.MAX_NAME_WORDS + 1):
            tail_start: int = len(head) + name_length
            if tail_start + len(tail) > len(words):
                return 0
            # A name that stops short of the period is not a whole copy of the prefix.
            if words[tail_start - 1].endswith(self.NAME_ENDING) and words[tail_start : tail_start + len(tail)] == tail:
                return tail_start + len(tail)
        return 0

    def _trailing_copy(self, instructions: str, start: int, end: int) -> tuple[int, int] | None:
        """
        Find a whole copy of the AAOSA instructions at the end of the text still left.

        Regular expressions only scan forwards, so the end is read from a reversed copy of the last characters
        only: a window of trailing_window characters, doubled only while the words matched so far reach its far
        edge. Only the end of the text is ever copied, however long the text is.

        :param instructions: The agent's instructions
        :param start: The offset the text still left begins at
        :param end: The offset the text still left ends at
        :return: The offsets of the copy's first and past its last character, or None when the text does not end
                with a copy
        """
        window: int = self.trailing_window
        while True:
            window_start: int = max(start, end - window)
            copy: tuple[int, int] | None
            cut_short: bool
            copy, cut_short = self._reversed_copy(instructions[window_start:end][::-1], window_start > start)
            if not cut_short:
                if copy is None:
                    return None
                # Offset i of the reversed window is offset end - 1 - i of the instructions.
                return end - copy[1], end - copy[0]
            window *= 2

    def _reversed_copy(self, reversed_tail: str, truncated: bool) -> tuple[tuple[int, int] | None, bool]:
        """
        Match the AAOSA instructions at the start of the reversed end of a text.

        :param reversed_tail: The last characters of the text still left, reversed
        :param truncated: Whether the text still left goes on beyond those characters
        :return: The offsets, in reversed_tail, of the copy's first and past its last character, or None when there
                is no copy; and whether the answer needs more characters, because the words matched so far reach
                the far edge of a truncated tail, where the next word may be cut in two or not read at all
        """
        first_span: tuple[int, int] | None = None
        last_span: tuple[int, int] | None = None
        count: int = 0
        for match in self.WORD.finditer(reversed_tail):
            if truncated and match.end() == len(reversed_tail):
                # The word may go on beyond the tail, so it cannot be compared yet.
                return None, True
            if match.group() != self.reversed_aaosa[count]:
                return None, False
            if first_span is None:
                first_span = match.span()
            last_span = match.span()
            count += 1
            if count == len(self.reversed_aaosa):
                return (first_span[0], last_span[1]), False
        # Every word read matched, but the copy is not complete yet: the rest of it may lie beyond the tail.
        return None, truncated

    @classmethod
    def _words(cls, text: str | None) -> list[str]:
        """
        Split the text of a piece into the words its copies are matched by.

        :param text: The text of the piece, or None
        :return: Its words, split the same way as the instructions are; empty for None, a non-string or a blank
                text, which makes the piece one that is never stripped
        """
        words: list[str] = []
        if isinstance(text, str):
            for match in cls.WORD.finditer(text):
                words.append(match.group())
        return words

    @classmethod
    def _reversed_words(cls, text: str | None) -> list[str]:
        """
        Split the text of a piece into its words the way a reversed text reads them.

        :param text: The text of the piece, or None
        :return: Its words, last word first and each spelled backwards; empty for None, a non-string or a blank text
        """
        reversed_words: list[str] = []
        for word in reversed(cls._words(text)):
            reversed_words.append(word[::-1])
        return reversed_words
