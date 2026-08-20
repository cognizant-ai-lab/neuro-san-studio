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

from langchain_core.messages import SystemMessage


class FakeModelRequest:  # pylint: disable=too-few-public-methods
    """Just enough of langchain's ModelRequest for awrap_model_call tests: tools,
    system_message, and an override() that returns a modified copy."""

    def __init__(self, tools: list[Any] | None = None, system_message: SystemMessage | None = None):
        self.tools = [] if tools is None else tools
        self.system_message = system_message

    def override(self, **kwargs) -> "FakeModelRequest":
        """Mirror ModelRequest.override(): a copy with the given fields replaced."""
        return FakeModelRequest(kwargs.get("tools", self.tools), kwargs.get("system_message", self.system_message))
