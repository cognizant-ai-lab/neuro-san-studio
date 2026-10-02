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

"""Error raised when source-preserving patch retries cannot succeed."""


class StuckPatchError(Exception):
    """Report repeated unsupported HOCON patch failures for one network."""

    def __init__(self, hocon_file: str, messages: list[str]) -> None:
        """Create an error retaining the affected file and parse messages."""
        self.hocon_file = hocon_file
        self.messages = messages
        super().__init__(
            f"consultant is stuck patching {hocon_file} -- its source-preserving editor "
            "doesn't support this file's brace-less/'=' HOCON style. Skipping."
        )
