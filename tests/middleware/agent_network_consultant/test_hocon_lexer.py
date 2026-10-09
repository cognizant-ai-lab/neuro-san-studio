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

"""Tests for source-aware HOCON tokenization."""

from unittest import TestCase

from middleware.agent_network_consultant.hocon_lexer import HoconLexer
from middleware.agent_network_consultant.hocon_token import HoconToken


class TestHoconLexer(TestCase):
    """Verify that the Consultant lexer preserves significant HOCON token boundaries."""

    def test_tokenize_reads_supported_hocon_syntax_in_source_order(self) -> None:
        """Read bare, quoted, substitution, triple-quoted, and punctuation tokens."""
        source = '# ignored\ntools = [{ name: "front_man", instructions: ${common} """Do work.""" }]'

        tokens: list[HoconToken] = HoconLexer(source).tokenize()
        values: list[str] = []
        for token in tokens:
            values.append(token.value())

        self.assertEqual(
            [
                "tools",
                "=",
                "[",
                "{",
                "name",
                ":",
                "front_man",
                ",",
                "instructions",
                ":",
                "${common}",
                "Do work.",
                "}",
                "]",
            ],
            values,
        )
        self.assertEqual(source.index('"front_man"'), tokens[6].start())
        self.assertEqual(source.index('"front_man"') + len('"front_man"'), tokens[6].end())

    def test_tokenize_rejects_unterminated_structures(self) -> None:
        """Report each supported string-like token when its closing delimiter is absent."""
        malformed_sources: tuple[tuple[str, str], ...] = (
            ('"unterminated', "Unterminated quoted HOCON string"),
            ('"""unterminated', "Unterminated triple-quoted HOCON string"),
            ("${unterminated", "Unterminated HOCON substitution"),
        )
        for source, message in malformed_sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, message):
                    HoconLexer(source).tokenize()

    def test_next_token_supports_incremental_consumption(self) -> None:
        """Read one token at a time and report when the source is exhausted."""
        lexer = HoconLexer("name = value")

        name = lexer.next_token()
        separator = lexer.next_token()
        value = lexer.next_token()

        self.assertEqual("name", name.value() if name is not None else None)
        self.assertEqual("=", separator.value() if separator is not None else None)
        self.assertEqual("value", value.value() if value is not None else None)
        self.assertIsNone(lexer.next_token())
