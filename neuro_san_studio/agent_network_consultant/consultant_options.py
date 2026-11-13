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

"""Input values for one Agent Network Consultant run."""

from typing import Literal
from typing import NamedTuple


class ConsultantOptions(NamedTuple):
    """Carry the user-selected values for one Agent Network Consultant run."""

    CONFIDENT_SUCCESS_RATIO = "3/3"
    DEFAULT_MAX_ITERATIONS = 20

    use_case: str | None = None
    hocon_file: str | None = None
    direction: str | None = None
    test_level: str = "normal"
    test_guidance: str = ""
    force_generate: bool = False
    # An ungrounded criterion requires a fact no available network tool can supply. Stop preserves the criterion;
    # continue removes only that impossible criterion so other grounded failures can still be improved.
    ungrounded: Literal["stop", "continue"] = "stop"
    only_fixtures: list[str] | None = None
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    success_ratio: str = CONFIDENT_SUCCESS_RATIO
