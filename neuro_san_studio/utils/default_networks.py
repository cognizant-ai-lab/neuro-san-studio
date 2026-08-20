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

"""The agent networks `ns init` installs into every new project."""

from typing import Tuple

# The Agent Network Designer family plus the CRUSE support networks. `ns init` copies these
# (and their dependencies) so a brand-new project can design agent networks immediately —
# the nsflow NEW button, the tutorial, and the docs all assume the designer is there.
#
# Registry-relative paths, matching the keys of the studio's root manifest, so they feed
# straight into DependencyAnalyzer/AgentNetworkImporter without translation.
#
# agent_network_architect is deliberately absent: it needs Gmail API credentials, a Selenium
# WebDriver, and a second server on non-default ports, so it ships disabled even in this repo's
# own manifest. Users who want it can still `ns import agent_network_architect`.
#
# Keep in sync with neuro_san_studio/templates/manifest.hocon, which declares the manifest entry
# for each of these (with the serve/public flags the support networks need). A network listed
# here but missing there lands on disk without being served.
DEFAULT_NETWORK_HOCONS: Tuple[str, ...] = (
    # The designer proper, plus the sub-networks it delegates to.
    "agent_network_designer.hocon",
    "agent_network_editor.hocon",
    "agent_network_instructions_editor.hocon",
    "agent_network_query_generator.hocon",
    # Generates test fixtures for an existing agent network.
    "agent_network_test_generator.hocon",
    # Back the CRUSE adaptive UI: nsflow asks these for a theme and for widget schemas.
    "experimental/cruse_theme_agent.hocon",
    "experimental/cruse_widget_agent.hocon",
)
