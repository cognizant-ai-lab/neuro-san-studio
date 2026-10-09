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
"""Control-line protocol returned by the Agent Network Consultant network."""


class ConsultantResponseProtocol:
    """Expose control directives parsed from one Agent Network Consultant response."""

    CLARIFICATION_PREFIX = "NEEDS_CLARIFICATION:"
    STRUCTURAL_CHANGE_PREFIX = "STRUCTURAL_CHANGE_REQUIRED:"
    CONFIDENT_FIX_PREFIX = "CONFIDENT_FIX:"
    TOOL_ISSUE_PREFIX = "TOOL_ISSUE:"
    # An ungrounded criterion asks for data no available tool can supply. This differs from a broken tool.
    UNGROUNDED_PREFIX = "UNGROUNDED:"

    def __init__(self, response: str) -> None:
        """
        Store one response for directive queries.

        :param response: The Agent Network Consultant response text.
        """
        self._response = response

    def values(self, prefix: str) -> list[str]:
        """
        Return the payload of every response line beginning with one control prefix.

        :param prefix: The response-line prefix to select.
        :return: The collected control-directive payloads.
        """
        matches: list[str] = []
        for line in self._response.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith(prefix):
                matches.append(stripped_line[len(prefix) :].strip())
        return matches

    def contains(self, prefix: str) -> bool:
        """
        Return whether the response contains at least one directive with the requested prefix.

        :param prefix: The response-line prefix to find.
        :return: Whether a matching directive is present.
        """
        return bool(self.values(prefix))
