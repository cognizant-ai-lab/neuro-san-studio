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

"""Unit tests for HoconStorabilityUtil, the HOCON round-trip rules behind a network's "metadata" block (#1398)."""

from typing import Any
from unittest import TestCase

from middleware.agent_network_designer.persistence.hocon_storability_util import HoconStorabilityUtil

# The number of C0 control characters, U+0000 through U+001F: the code points both predicates treat
# as control characters (ord(char) < 32), swept exhaustively below.
C0_CONTROL_CHAR_COUNT: int = 32


class TestHoconStorabilityUtil(TestCase):
    """
    Unit tests for HoconStorabilityUtil.

    Covers the two static predicates AgentNetworkMetadataBlock applies to every entry before a block
    is written: is_storable_key() (a str free of double quotes, backslashes and control characters;
    a non-str key is out) and is_storable_string() (no control character other than the tab, newline
    and carriage return pyhocon decodes inside a quoted value), plus DECODED_CONTROL_CHARS, the
    constant naming those three characters.
    """

    # ---- DECODED_CONTROL_CHARS

    def test_decoded_control_chars_are_tab_newline_and_carriage_return(self) -> None:
        """
        DECODED_CONTROL_CHARS names exactly the tab, the newline and the carriage return, and each of
        them is storable inside a string value while still making a key unstorable.
        """
        self.assertEqual(HoconStorabilityUtil.DECODED_CONTROL_CHARS, "\t\n\r")
        for char in HoconStorabilityUtil.DECODED_CONTROL_CHARS:
            with self.subTest(char=char):
                # Values: pyhocon decodes the escape, so the text reads back as written.
                self.assertTrue(HoconStorabilityUtil.is_storable_string(f"a{char}b"))
                # Keys: pyhocon leaves the escape text raw, so the key never reads back as written.
                self.assertFalse(HoconStorabilityUtil.is_storable_key(f"a{char}b"))

    def test_every_c0_control_character_is_storable_in_a_string_only_when_decoded(self) -> None:
        """
        Sweeping U+0000 through U+001F, every control character makes a key unstorable and makes a
        string value unstorable exactly when it is absent from DECODED_CONTROL_CHARS.
        """
        for code_point in range(C0_CONTROL_CHAR_COUNT):
            char: str = chr(code_point)
            with self.subTest(code_point=hex(code_point)):
                self.assertFalse(HoconStorabilityUtil.is_storable_key(f"key{char}"))
                expected: bool = char in HoconStorabilityUtil.DECODED_CONTROL_CHARS
                self.assertEqual(HoconStorabilityUtil.is_storable_string(f"text{char}"), expected)

    # ---- is_storable_key

    def test_is_storable_key_accepts_keys_pyhocon_reads_back_verbatim(self) -> None:
        """
        is_storable_key() is True for the keys the restorer hands back unchanged: a dotted key, a key
        with a space, the HOCON comment starters '#' and '//', a '${x}' substitution shape, non-ASCII
        text and the U+2028 line separator (not a C0 control character, so not a control character here).
        """
        storable: list[tuple[str, str]] = [
            ("dotted", "dot.key"),
            ("spaced", "space key"),
            ("hash", "hash#key"),
            ("substitution", "dollar${x}"),
            ("double slash", "slashes//key"),
            ("non-ascii", "caf\u00e9"),
            ("line separator", "sep\u2028arated"),
        ]
        for label, key in storable:
            with self.subTest(case=label, key=key):
                self.assertTrue(HoconStorabilityUtil.is_storable_key(key))

    def test_is_storable_key_rejects_quotes_backslashes_control_characters_and_non_str(self) -> None:
        """
        is_storable_key() is False for a key holding a double quote, a backslash, a newline, a tab or
        another control character (bell), and for a non-str key, which pyhocon would read back as a str.
        """
        unstorable: list[tuple[str, Any]] = [
            ("double quote", 'we"ird'),
            ("backslash", "back\\slash"),
            ("newline", "a\nb"),
            ("tab", "tab\there"),
            ("bell", "bell\x07x"),
            ("int key", 7),
            ("None key", None),
        ]
        for label, key in unstorable:
            with self.subTest(case=label, key=key):
                self.assertFalse(HoconStorabilityUtil.is_storable_key(key))

    # ---- is_storable_string

    def test_is_storable_string_accepts_decoded_escapes_and_printable_text(self) -> None:
        """
        is_storable_string() is True for plain text, text with a tab, a newline or a carriage return,
        quotes and backslashes (escaped and decoded symmetrically inside a value), non-ASCII text, DEL
        (U+007F, not below 32), the U+2028 line separator and the empty string.
        """
        storable: list[tuple[str, str]] = [
            ("plain", "plain"),
            ("tab", "tab\there"),
            ("newline", "line\nbreak"),
            ("carriage return", "cr\rx"),
            ("quote and backslash", 'quote"back\\slash'),
            ("non-ascii", "caf\u00e9"),
            ("DEL", "del\x7fx"),
            ("line separator", "sep\u2028arated"),
            ("empty", ""),
        ]
        for label, text in storable:
            with self.subTest(case=label, text=text):
                self.assertTrue(HoconStorabilityUtil.is_storable_string(text))

    def test_is_storable_string_rejects_control_characters_pyhocon_does_not_decode(self) -> None:
        """
        is_storable_string() is False for text holding a control character pyhocon reads back as its
        escape text: NUL, bell, backspace, form feed and U+001F, the last C0 code point.
        """
        unstorable: list[tuple[str, str]] = [
            ("NUL", "nul\x00x"),
            ("bell", "bell\x07x"),
            ("backspace", "back\x08space"),
            ("form feed", "form\x0cfeed"),
            ("unit separator", "unit\x1fsep"),
        ]
        for label, text in unstorable:
            with self.subTest(case=label, text=text):
                self.assertFalse(HoconStorabilityUtil.is_storable_string(text))
