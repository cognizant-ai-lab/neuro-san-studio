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

"""The shared registry-level HOCONs that agent networks pull in via ``include``."""

from typing import Tuple

# Registry-level HOCONs that are substitution fragments, not agent networks. Networks
# reference them with `include "registries/<name>"` and then substitute a variable they
# define (e.g. ${aaosa_instructions}, ${expertise_scoping_instructions}), so a project
# missing one fails to parse the moment a network that includes it is read.
#
# The dependency walker doesn't surface them — it looks for networks, coded tools, and
# middleware — so both `ns init` and `ns import` copy them unconditionally. `ns import`
# additionally uses this list to keep fragments OUT of the manifest: registering one as a
# network crashes neuro-san at startup, because its validator iterates the file expecting
# agent specs and a bare string value blows up `agent.get(...)`.
#
# Keep this as the single definition. It previously lived in two places, and the copies
# drifted: `expertise_scoping_instructions.hocon` was added to neither, which left every
# freshly scaffolded project unable to start.
SHARED_REGISTRY_INCLUDES: Tuple[str, ...] = (
    "aaosa.hocon",
    "aaosa_basic.hocon",
    "aaosa_basic_debug.hocon",
    "expertise_scoping_instructions.hocon",
)
