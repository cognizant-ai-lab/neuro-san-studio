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

from typing import Optional


class HoconText:
    """Brace/string/comment-aware scanning helpers for editing HOCON source text in place.

    Operating on raw text (rather than a parsed model) keeps ``include`` directives,
    ``${substitutions}``, and comments intact, which a pyhocon parse/re-emit would drop.
    """

    @staticmethod
    def skip_line(text: str, i: int) -> int:
        """Advance past the rest of the current line (used to skip ``# ...`` comments)."""
        n = len(text)
        while i < n and text[i] != "\n":
            i += 1
        return i + 1 if i < n else i

    @classmethod
    def first_significant_index(cls, text: str) -> int:
        """Index of the first char that isn't whitespace, a ``#``/``//`` comment, or an
        ``include`` directive line. Returns ``len(text)`` if there's nothing significant."""
        n = len(text)
        i = 0
        while i < n:
            char = text[i]
            if char in " \t\r\n":
                i += 1
                continue
            if char == "#" or text.startswith("//", i):
                i = cls.skip_line(text, i)
                continue
            if text.startswith("include", i):
                i = cls.skip_line(text, i)
                continue
            return i
        return n

    @staticmethod
    def find_string_end(text: str, start: int) -> int:
        """Given ``text[start] == '"'``, return the index of the closing quote (-1 if unterminated)."""
        n = len(text)
        j = start + 1
        while j < n:
            if text[j] == "\\" and j + 1 < n:
                j += 2
                continue
            if text[j] == '"':
                return j
            j += 1
        return -1

    @classmethod
    def match_closing_brace(cls, text: str, open_index: int) -> Optional[int]:
        """Given ``text[open_index] == '{'``, return the index just past its matching ``}``.

        Tracks string literals and ``#`` comments so braces inside those don't throw off the
        count. Returns ``None`` if the brace is never closed.
        """
        n = len(text)
        depth = 1
        k = open_index + 1
        while k < n and depth > 0:
            char = text[k]
            if char == '"':
                end = cls.find_string_end(text, k)
                if end == -1:
                    return None
                k = end + 1
                continue
            if char == "#":
                k = cls.skip_line(text, k)
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return k + 1
            k += 1
        return None
