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

"""Detection of repeated source-preserving HOCON parse failures."""

import logging

from typing_extensions import override


class ParseErrorCapture(logging.Handler):
    """Capture recurring patch errors during one consultant chat call."""

    ERROR_MARKERS = ("could not be parsed", "Could not locate direct property")
    REPEAT_THRESHOLD = 3

    @override
    def __init__(self) -> None:
        """
        Create a warning-level parse-error capture.
        """
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """
        Record messages containing a supported parse-error signature.

        :param record: The log record to inspect.
        """
        message = record.getMessage()
        for marker in self.ERROR_MARKERS:
            if marker in message:
                self.messages.append(message.strip())
                return

    def is_stuck(self) -> bool:
        """
        Return whether the repeated-error threshold has been reached.

        :return: Whether the requested condition is met.
        """
        return len(self.messages) >= self.REPEAT_THRESHOLD
