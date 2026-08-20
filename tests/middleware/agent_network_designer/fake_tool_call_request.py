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

"""Shared test double for the designer middleware tests."""

from typing import Any


class FakeToolCallRequest:  # pylint: disable=too-few-public-methods
    """Just enough of langchain's ToolCallRequest for awrap_tool_call tests: the tool_call dict."""

    def __init__(self, name: str, call_id: str | None = "call_1"):
        self.tool_call: dict[str, Any] = {"name": name, "args": {}, "id": call_id}
