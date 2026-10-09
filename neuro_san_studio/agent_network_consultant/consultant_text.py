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

"""Shared text-interface checks for Agent Network Consultant data."""

from typing import Any
from typing import cast


class ConsultantText:
    """Normalize values that satisfy the Agent Network Consultant's text interface."""

    @staticmethod
    def text_value(value: Any) -> str | None:
        """
        Return a value that exposes the expected text-encoding interface.

        :param value: The candidate text value.
        :return: The text value, or `None` when the text interface is unavailable.
        """
        # AGENTS.md requires interface checks instead of isinstance checks against concrete classes.
        encode = getattr(value, "encode", None)
        if not callable(encode):
            return None
        return cast(str, value)

    @classmethod
    def required_text(cls, value: Any, error_message: str) -> str:
        """
        Return a text value or raise the caller's domain-specific contract error.

        :param value: The candidate required text value.
        :param error_message: The message for a missing text interface.
        :return: The required text value.
        :raises TypeError: If the value does not provide the expected text interface.
        """
        text = cls.text_value(value)
        if text is None:
            raise TypeError(error_message)
        return text
