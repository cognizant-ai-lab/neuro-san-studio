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

"""Current fixture-round state for a consultant run."""

from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class ConsultantRoundState:
    """Carry the current selection, result, and chart position."""

    retest_only: list[str] | None = None
    total_fixture_count: int = 0
    improvement_iteration: int = 0
    iteration: int = 0
    is_subset_check: bool = False
    results: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
