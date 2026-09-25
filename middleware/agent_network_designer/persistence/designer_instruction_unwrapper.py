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
Removal of copies of the designer's instruction wrapper from the instructions in an agent network definition.
"""

import re
from typing import Any

from middleware.agent_network_designer.persistence.designer_wrapper_texts import DesignerWrapperTexts


class DesignerInstructionUnwrapper:
    """
    Strips copies of the designer's instruction wrapper from agent instructions, so that a save adds exactly one.

    The instructions in agent_network_definition are meant to hold only each agent's own text: every save wraps
    them in the prefix, the front man's lines, the demo sentence and the AAOSA instructions again (see
    DesignerWrapperTexts). A client that reads a saved network with its HOCON substitutions resolved gets the
    wrapper inlined in every agent's instructions. Sending that text back as the definition used to add one more
    copy of each piece per save (issue #1458, reported as #1429).

    All four pieces are stripped from every agent, whatever its role and whether demo mode is on. The definition
    never needs them, since each save adds back the ones the agent's role calls for. Stripping only those would
    leave a piece behind as own text whenever an agent's role or the demo setting changed between saves: a leaf
    that gained tools would keep the demo sentence, an agent that lost its tools the AAOSA instructions, and a
    network saved in demo mode would keep its demo sentences once demo mode was turned off. Hand-written networks
    that give leaves the AAOSA instructions on purpose (registries/basic/smart_home.hocon, for one) lose them there
    once loaded into the designer, and after a save their leaves work like the ones the designer writes.

    How copies are matched:

    - Word by word, so copies that differ only in whitespace (indentation, line breaks) match; the text that
      remains keeps its own whitespace exactly as written.
    - Whole copies only, anchored at the start for the prefix, the front man's lines and the demo sentence, and
      at the end for the AAOSA instructions. A text that ends with the prefix's rules
      (registries/basic/wolfram_mcp.hocon) or quotes a wrapper sentence in the middle is left alone.
    - Every copy, however many there are and in whatever order: after several saves the leading pieces
      interleave (prefix, front man's lines, prefix, front man's lines, ...).
    - The prefix under any network name of up to MAX_NAME_WORDS words, since a copy carries the name the network
      was saved under, which can differ from the name of this save; and in the wording networks generated before
      22a84541 used, whose names were single words. That old wording is also what some hand-written networks use
      for their own prefix with a longer name ("You are part of a smart home network of assistants." in
      registries/basic/smart_home.hocon), and those are not designer copies, so they are left alone.
    - Only the words at the two ends of the text are ever read, and only the end is copied, to be read backwards
      (see _trailing_copy), so the cost grows with the copies stripped, not with the length of the text. The words
      are compared one by one rather than with a regular expression: a pattern anchored at the end of the text is
      quadratic when many copies of the AAOSA instructions come before other text, and this runs on the event loop
      before every model call.

    A text holding none of the wrapper is returned unchanged, byte for byte. A text holding nothing but wrapper
    copies keeps one copy of each piece found instead of becoming empty: an empty text fails the designer's
    validation (turning a plain save into an LLM run), and an empty leaf would be written as a toolbox reference.
    One copy of each is the smallest text that stays the same over any number of saves.
    """

    # One word of a text: what the matching compares, so whitespace never takes part in it.
    WORD: re.Pattern[str] = re.compile(r"\S+")

    # The most words a network name in a copy of the current prefix may span. Names are usually one word, but
    # nothing stops a client from saving a network under a name with spaces, and its prefix copies must be
    # stripped too.
    MAX_NAME_WORDS: int = 16

    # Keys for the wrapper pieces, and the order a wrapper-only text keeps them in, which is the order a save
    # writes them in.
    PREFIX: str = "prefix"
    FRONT_MAN_LINES: str = "front_man_lines"
    DEMO_SENTENCE: str = "demo_sentence"
    AAOSA_INSTRUCTIONS: str = "aaosa_instructions"
    PIECE_ORDER: tuple[str, ...] = (PREFIX, FRONT_MAN_LINES, DEMO_SENTENCE, AAOSA_INSTRUCTIONS)

    def __init__(self, aaosa_instructions: str | None) -> None:
        """
        Prepare the word patterns of the wrapper pieces.

        The prefix, the front man's lines and the demo sentence are fixed texts from DesignerWrapperTexts. A copy of
        the prefix names the network it was saved under, so up to MAX_NAME_WORDS words stand in for the name (one
        word for the legacy wording).

        :param aaosa_instructions: The AAOSA instructions the save appends to the front man and to agents with
                tools, from registries/aaosa.hocon, or None to strip none
        """
        # An int entry stands for the network name, which differs from copy to copy: it matches one word up to
        # that many words.
        current_prefix: list[str | int] = self._words(DesignerWrapperTexts.PREFIX_OPENING)
        current_prefix.append(self.MAX_NAME_WORDS)
        current_prefix.extend(self._words(DesignerWrapperTexts.PREFIX_RULES))
        legacy_prefix: list[str | int] = self._words(DesignerWrapperTexts.LEGACY_PREFIX_OPENING)
        legacy_prefix.append(1)
        legacy_prefix.extend(self._words(DesignerWrapperTexts.LEGACY_PREFIX_CLOSING))
        legacy_prefix.extend(self._words(DesignerWrapperTexts.PREFIX_RULES))

        # (piece key, word pattern) pairs for the pieces a save writes before the agent's own text.
        self.leading_pieces: list[tuple[str, list[str | int]]] = [
            (self.PREFIX, current_prefix),
            (self.PREFIX, legacy_prefix),
            (self.FRONT_MAN_LINES, self._words(DesignerWrapperTexts.FRONT_MAN_LINES)),
            (self.DEMO_SENTENCE, self._words(DesignerWrapperTexts.DEMO_SENTENCE)),
        ]
        # The AAOSA instructions, the one piece a save writes after the own text, are matched on the reversed text
        # (see _trailing_copy), so their pattern is kept the way that text reads: last word first, and every word
        # spelled backwards. Without them there is nothing to look for at the end.
        reversed_aaosa_pattern: list[str | int] = []
        for word in reversed(self._words(aaosa_instructions)):
            reversed_aaosa_pattern.append(word[::-1])
        self.trailing_pieces: list[tuple[str, list[str | int]]] = []
        if reversed_aaosa_pattern:
            self.trailing_pieces.append((self.AAOSA_INSTRUCTIONS, reversed_aaosa_pattern))
        # How many characters _trailing_copy first reads from the end: twice a copy of the AAOSA instructions with
        # single spaces, so a copy with the indentation of registries/aaosa.hocon fits in one read.
        self.trailing_window: int = 1
        for word in reversed_aaosa_pattern:
            self.trailing_window += 2 * (len(word) + 1)

    def unwrap_definition(self, network_def: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """
        Strip the wrapper copies from the instructions of every agent in a definition.

        :param network_def: The agent network definition, agent name to agent dict. It is not modified.
        :return: The definition to use and the names of the agents whose instructions changed. When none changed,
                the definition is network_def itself; otherwise it is a new dict in which each changed agent is a
                copy with the new instructions and every other agent is the same object as before.
        """
        if not isinstance(network_def, dict):
            # Not a definition at all: the validators report it, and there is no agent to strip anything from.
            return network_def, []

        unwrapped_def: dict[str, Any] = {}
        changed: list[str] = []
        for agent_name, agent in network_def.items():
            unwrapped_def[agent_name] = agent
            if not isinstance(agent, dict):
                # Malformed entries are the validators' to report; there is nothing here to strip.
                continue
            instructions: Any = agent.get("instructions")
            if not isinstance(instructions, str):
                continue
            unwrapped: str = self.unwrap(instructions)
            if unwrapped != instructions:
                unwrapped_agent: dict[str, Any] = dict(agent)
                unwrapped_agent["instructions"] = unwrapped
                unwrapped_def[agent_name] = unwrapped_agent
                changed.append(agent_name)

        if not changed:
            return network_def, changed
        return unwrapped_def, changed

    def unwrap(self, instructions: str) -> str:
        """
        Strip every copy of the wrapper pieces from an agent's instructions.

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

        # Nothing but wrapper: keep the first copy found of each piece, as written, in the order a save writes them.
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
            for piece, pattern in self.leading_pieces:
                copy: tuple[int, int] | None = self._leading_copy(instructions, start, end, pattern)
                while copy is not None:
                    first_copies.setdefault(piece, copy)
                    start = copy[1]
                    found = True
                    copy = self._leading_copy(instructions, start, end, pattern)
            for piece, pattern in self.trailing_pieces:
                copy = self._trailing_copy(instructions, start, end, pattern)
                while copy is not None:
                    first_copies.setdefault(piece, copy)
                    end = copy[0]
                    found = True
                    copy = self._trailing_copy(instructions, start, end, pattern)
        return start, end, first_copies

    def _leading_copy(
        self, instructions: str, start: int, end: int, pattern: list[str | int]
    ) -> tuple[int, int] | None:
        """
        Find a whole copy of a piece at the start of the text still left.

        :param instructions: The agent's instructions
        :param start: The offset the text still left begins at
        :param end: The offset the text still left ends at
        :param pattern: The words of the piece; an int entry stands for one word up to that many words of a network
                name
        :return: The offsets of the copy's first and past its last character, or None when the text does not
                begin with a copy
        """
        # The words before the name, or all of them when the piece has no name.
        head_length: int = len(pattern)
        for index, entry in enumerate(pattern):
            if isinstance(entry, int):
                head_length = index
                break
        limit: int = len(pattern)
        if head_length < len(pattern):
            limit = len(pattern) - 1 + pattern[head_length]

        # Only as many words as a copy can span are read, and reading stops at the first word that differs.
        words: list[str] = []
        spans: list[tuple[int, int]] = []
        for match in self.WORD.finditer(instructions, start, end):
            if len(words) < head_length and match.group() != pattern[len(words)]:
                return None
            words.append(match.group())
            spans.append(match.span())
            if len(words) == limit:
                break

        length: int = self._copy_length(words, pattern, head_length)
        if length == 0:
            return None
        return spans[0][0], spans[length - 1][1]

    def _copy_length(self, words: list[str], pattern: list[str | int], head_length: int) -> int:
        """
        Count the words a copy of a piece spans at the start of a list of words.

        :param words: The first words of the text still left
        :param pattern: The words of the piece; an int entry stands for one word up to that many words of a network
                name
        :param head_length: The number of pattern words before the int entry, or the pattern's length without one
        :return: The number of words the copy spans, or 0 when the words do not begin with a copy
        """
        if words[:head_length] != pattern[:head_length]:
            return 0
        if head_length == len(pattern):
            return head_length
        # Try the shortest name first: the words after the name are fixed, so at most one length can fit a real
        # copy, and a name cannot hold the rule sentences that follow it.
        tail: list[str | int] = pattern[head_length + 1 :]
        for name_length in range(1, pattern[head_length] + 1):
            tail_start: int = head_length + name_length
            if tail_start + len(tail) > len(words):
                return 0
            if words[tail_start : tail_start + len(tail)] == tail:
                return tail_start + len(tail)
        return 0

    def _trailing_copy(
        self, instructions: str, start: int, end: int, reversed_pattern: list[str | int]
    ) -> tuple[int, int] | None:
        """
        Find a whole copy of a piece at the end of the text still left.

        Regular expressions only scan forwards, so the end is read from a reversed copy of the last characters
        only: a window of trailing_window characters, doubled only while the words matched so far reach its far
        edge. Only the end of the text is ever copied, however long the text is.

        :param instructions: The agent's instructions
        :param start: The offset the text still left begins at
        :param end: The offset the text still left ends at
        :param reversed_pattern: The words of the piece, last word first and each word spelled backwards
        :return: The offsets of the copy's first and past its last character, or None when the text does not end
                with a copy
        """
        window: int = self.trailing_window
        while True:
            window_start: int = max(start, end - window)
            copy: tuple[int, int] | None
            cut_short: bool
            copy, cut_short = self._reversed_copy(
                instructions[window_start:end][::-1], window_start > start, reversed_pattern
            )
            if not cut_short:
                if copy is None:
                    return None
                # Offset i of the reversed window is offset end - 1 - i of the instructions.
                return end - copy[1], end - copy[0]
            window *= 2

    def _reversed_copy(
        self, reversed_tail: str, truncated: bool, reversed_pattern: list[str | int]
    ) -> tuple[tuple[int, int] | None, bool]:
        """
        Match a piece at the start of the reversed end of a text.

        :param reversed_tail: The last characters of the text still left, reversed
        :param truncated: Whether the text still left goes on beyond those characters
        :param reversed_pattern: The words of the piece, last word first and each word spelled backwards
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
            if match.group() != reversed_pattern[count]:
                return None, False
            if first_span is None:
                first_span = match.span()
            last_span = match.span()
            count += 1
            if count == len(reversed_pattern):
                return (first_span[0], last_span[1]), False
        # Every word read matched, but the copy is not complete yet: the rest of it may lie beyond the tail.
        return None, truncated

    @classmethod
    def _words(cls, text: str | None) -> list[str | int]:
        """
        Split a wrapper text into the words its copies are matched by.

        :param text: The wrapper text, or None
        :return: Its words, split the same way as the instructions are; empty for None, a non-string or a blank
                text, which makes the piece one that is never stripped
        """
        words: list[str | int] = []
        if isinstance(text, str):
            for match in cls.WORD.finditer(text):
                words.append(match.group())
        return words
