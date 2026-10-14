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

from typing import Any
from typing import ClassVar


class HoconStorabilityUtil:
    """
    Static rules for what survives the trip through a generated agent network HOCON file.

    The designer writes a network's metadata block as one JSON object inside the HOCON header,
    and neuro-san reads the file back with AbstractAsyncConfigRestorer, which parses through
    leaf-common's HoconSerializationFormat and therefore pyhocon. Three pyhocon behaviours make
    a written entry differ from what is read back, and these predicates name them so that
    AgentNetworkMetadataBlock can drop such entries before they are written:

    - keys come back raw, without decoding JSON escapes, so a key holding a double quote, a
      backslash or a control character comes back changed or split into a path;
    - only the tab, newline and carriage-return escapes are decoded inside a string value; any
      other control character is read back as its escape text;
    - empty strings inside a list are dropped by the parser (the block class handles that one,
      since it is about the position of the value, not the value itself).

    Everything else reads back as written, dotted and URL-shaped keys included: the restorer
    converts with as_plain_ordered_dict(), which removes the quotes pyhocon keeps around such
    keys. Verified with pyhocon 0.3.63 and leaf-common 1.4.2 through the assembler and the
    restorer for every C0 control character, DEL, NEL and the Unicode line separators.

    Every method is static and the class holds no state, hence the Util name.
    """

    # The control characters pyhocon decodes inside a quoted string value.
    DECODED_CONTROL_CHARS: ClassVar[str] = "\t\n\r"

    @staticmethod
    def is_storable_key(key: Any) -> bool:
        """
        Tell whether an object key reads back from a HOCON file exactly as written.

        :param key: The key to check
        :return: True for a str without a double quote, a backslash or a control character;
                False for any other str and for a non-str key, which would come back as a str
        """
        if not isinstance(key, str):
            return False
        for char in key:
            if char in '"\\' or ord(char) < 32:
                return False
        return True

    @staticmethod
    def is_storable_string(text: str) -> bool:
        """
        Tell whether a string value reads back from a HOCON file exactly as written.

        :param text: The string value to check
        :return: True when every control character in text is one pyhocon decodes (tab,
                newline, carriage return); the empty string is storable as a value
        """
        for char in text:
            if ord(char) < 32 and char not in HoconStorabilityUtil.DECODED_CONTROL_CHARS:
                return False
        return True
