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

"""Tests for the source-preserving HOCON token model."""

from unittest import TestCase

from middleware.agent_network_consultant.hocon_token import HoconToken


class TestHoconToken(TestCase):
    """Verify token state is exposed only through explicit accessors."""

    def test_accessors_return_the_complete_token_state(self) -> None:
        """Return the lexical category, decoded value, and exact source span."""
        token = HoconToken("string", "hello", 4, 11)

        self.assertEqual("string", token.kind())
        self.assertEqual("hello", token.value())
        self.assertEqual(4, token.start())
        self.assertEqual(11, token.end())
