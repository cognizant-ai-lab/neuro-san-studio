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

"""Lex the HOCON syntax needed by source-preserving Consultant edits."""

import json

from middleware.agent_network_consultant.hocon_token import HoconToken


class HoconLexer:
    """Read significant HOCON tokens while retaining their exact source spans."""

    def __init__(self, text: str) -> None:
        """
        Initialize a lexer at the beginning of the supplied source text.

        :param text: The HOCON source text to tokenize.
        """
        self._text = text
        self._index = 0

    def tokenize(self) -> list[HoconToken]:
        """
        Read all significant tokens from the source text.

        :return: The tokens in source order.
        """
        tokens: list[HoconToken] = []
        token: HoconToken | None = self.next_token()
        while token is not None:
            tokens.append(token)
            token = self.next_token()
        return tokens

    def next_token(self) -> HoconToken | None:
        """
        Read the next significant token and advance the lexer.

        :return: The next token, or ``None`` after the source has been consumed.
        :raises ValueError: If the next token is malformed or unsupported.
        """
        while self._index < len(self._text):
            ignored_end: int | None = self._ignored_end()
            if ignored_end is None:
                token: HoconToken = self._read_token()
                self._index = token.end()
                return token
            self._index = ignored_end
        return None

    def _read_token(self) -> HoconToken:
        """
        Read the significant token beginning at the current source offset.

        :return: The token at the current source offset.
        :raises ValueError: If the token is malformed or unsupported.
        """
        if self._text.startswith('"""', self._index):
            return self._triple_quoted_token()
        if self._text[self._index] == '"':
            return self._quoted_token()
        if self._text.startswith("${", self._index):
            return self._substitution_token()
        if self._text[self._index] in "{}[]:=,+":
            return HoconToken("punctuation", self._text[self._index], self._index, self._index + 1)
        return self._bare_token()

    def _ignored_end(self) -> int | None:
        """
        Return the offset after whitespace or a comment beginning at the current offset.

        :return: The first offset after ignored text, or ``None`` for a significant token.
        """
        if self._text[self._index].isspace():
            return self._index + 1
        if self._text[self._index] == "#" or self._text.startswith("//", self._index):
            newline: int = self._text.find("\n", self._index)
            return len(self._text) if newline < 0 else newline + 1
        return None

    def _triple_quoted_token(self) -> HoconToken:
        """
        Read one triple-quoted HOCON string token.

        :return: The decoded string token.
        :raises ValueError: If the string has no closing delimiter.
        """
        quote_run_start: int = self._text.find('"""', self._index + 3)
        if quote_run_start < 0:
            raise ValueError("Unterminated triple-quoted HOCON string.")
        quote_run_end: int = quote_run_start + 3
        while quote_run_end < len(self._text) and self._text[quote_run_end] == '"':
            quote_run_end += 1
        delimiter_start: int = quote_run_end - 3
        return HoconToken(
            "string",
            self._text[self._index + 3 : delimiter_start],
            self._index,
            quote_run_end,
        )

    def _quoted_token(self) -> HoconToken:
        """
        Read and decode one JSON-compatible quoted HOCON string token.

        :return: The decoded string token.
        :raises ValueError: If the string is unterminated or malformed.
        """
        end: int = self._index + 1
        escaped = False
        while end < len(self._text):
            if self._text[end] == '"' and not escaped:
                break
            escaped = self._text[end] == "\\" and not escaped
            if self._text[end] != "\\":
                escaped = False
            end += 1
        if end >= len(self._text):
            raise ValueError("Unterminated quoted HOCON string.")
        try:
            value: str = json.loads(self._text[self._index : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid quoted HOCON string.") from exc
        return HoconToken("string", value, self._index, end + 1)

    def _substitution_token(self) -> HoconToken:
        """
        Read one HOCON substitution token.

        :return: The substitution token.
        :raises ValueError: If the substitution is unterminated.
        """
        end: int = self._text.find("}", self._index + 2)
        if end < 0:
            raise ValueError("Unterminated HOCON substitution.")
        return HoconToken("substitution", self._text[self._index : end + 1], self._index, end + 1)

    def _bare_token(self) -> HoconToken:
        """
        Read one unquoted HOCON token.

        :return: The bare token.
        :raises ValueError: If no supported token begins at the current offset.
        """
        end: int = self._index
        while end < len(self._text):
            if (
                self._text[end].isspace()
                or self._text[end] in "{}[]:=,+"
                or self._text[end] == "#"
                or self._text.startswith("//", end)
            ):
                break
            end += 1
        if end == self._index:
            raise ValueError(f"Unexpected HOCON character at offset {self._index}.")
        return HoconToken("bare", self._text[self._index : end], self._index, end)
