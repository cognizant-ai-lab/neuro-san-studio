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

"""Private sly-data keys used only by the Network Consultant."""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class ConsultantState:
    """Own the consultant's private sly-data key names."""

    AGENT_NETWORK_CHANGES: ClassVar[str] = "agent_network_changes"
    AGENT_NETWORK_DIAGNOSTIC_CONTEXT: ClassVar[str] = "agent_network_diagnostic_context"
    AGENT_NETWORK_EDITABLE_FIELDS: ClassVar[str] = "agent_network_editable_fields"
    AGENT_NETWORK_SOURCE_FILE: ClassVar[str] = "agent_network_source_file"
