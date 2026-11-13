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

"""Token model used by the consultant's source-preserving HOCON editor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HoconToken:
    """Represent a significant HOCON token and its exact source span."""

    _kind: str
    _value: str
    _start: int
    _end: int

    def kind(self) -> str:
        """
        Return the lexical token category.

        :return: The token category.
        """
        return self._kind

    def value(self) -> str:
        """
        Return the token's decoded value.

        :return: The decoded token value.
        """
        return self._value

    def start(self) -> int:
        """
        Return the inclusive source offset.

        :return: The inclusive source offset.
        """
        return self._start

    def end(self) -> int:
        """
        Return the exclusive source offset.

        :return: The exclusive source offset.
        """
        return self._end
