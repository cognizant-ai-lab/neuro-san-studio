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

"""Plateau and best-version state for a consultant run."""

from dataclasses import dataclass


@dataclass
class ConsultantScoreState:
    """Keep full-suite and subset scoring histories independent."""

    best_score: tuple[int, int] | None = None
    stale_rounds: int = 0
    subset_best_score: tuple[int, int] | None = None
    subset_stale_rounds: int = 0
    best_hocon_text: str | None = None
    best_hocon_iteration: int | None = None
