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

"""
Normalised item type returned by every persistent-memory store backend, plus
the ``Namespace`` tuple alias used to key those items.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Optional

# Namespace is always a 3-tuple: (agent_network_name, agent_name, topic).
# Kept as a plain tuple rather than a dataclass so it is hashable and cheap to
# pass around. Backends destructure it themselves.
Namespace = tuple[str, str, str]


@dataclass
class MemoryItem:
    """
    Normalised item returned by every store backend.

    :param key:   The entry's key within its namespace.
    :param value: The stored payload. Shape is controlled by the tool layer, not
                  the store — currently ``{"content": "..."}``.
    :param score: Optional similarity / relevance score returned by ``search``.
                  ``None`` for lookups that do not produce a score.
    """

    key: str
    value: dict[str, Any]
    score: Optional[float] = None
