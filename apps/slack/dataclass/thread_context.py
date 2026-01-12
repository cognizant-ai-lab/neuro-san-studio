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

from dataclasses import dataclass


@dataclass
class ThreadContext:
    """Store thread-specific context data."""

    channel_id: str
    thread_ts: str | None
    message_ts: str

    @property
    def thread_key(self) -> str:
        """Generate unique thread key."""
        return f"{self.channel_id}:{self.thread_ts or self.message_ts}"

    @property
    def conversation_thread(self) -> str:
        """Get conversation thread timestamp."""
        return self.thread_ts or self.message_ts
