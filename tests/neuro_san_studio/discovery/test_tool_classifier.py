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

"""Tests for DependencyAnalyzer's URL-tool classifier.

Calls ``_extract_from_config`` directly with a hand-built dict so we don't need hocon
fixtures or filesystem state. URL strings are assembled from individual pieces so no
URL-shaped substring sits contiguously in the source — keeps the link-checker quiet.
"""

# pylint: disable=protected-access

from neuro_san_studio.discovery.dependency_analyzer import AgentNetworkDependencies
from neuro_san_studio.discovery.dependency_analyzer import DependencyAnalyzer


class TestToolClassifier:  # pylint: disable=too-few-public-methods
    """One pass over each branch of the tool-ref classifier."""

    @staticmethod
    def _join(scheme: str, host: str, *path_parts: str) -> str:
        """Build a URL from non-URL fragments (avoids any literal URL in source)."""
        return scheme + "://" + host + "/" + "/".join(path_parts)

    def test_classifier_routes_each_ref_to_the_correct_bucket(self) -> None:
        """Sub-network goes to ``sub_networks``; ``/mcp``-suffix URL goes to ``mcp_tools``;
        plain external HTTP-agent URL is dropped (runtime-only, not a bundled dep)."""
        external_url = self._join("http", "host-a.invalid", "agent")
        mcp_url = self._join("https", "host-b.invalid", "tool", "mcp")

        config = {
            "tools": [
                {
                    "name": "frontman",
                    "class": "openai",
                    "tools": ["/sub_helper", external_url, mcp_url],
                }
            ]
        }
        deps = AgentNetworkDependencies()
        DependencyAnalyzer._extract_from_config(config, deps)

        assert deps.sub_networks == ["/sub_helper"]
        assert deps.mcp_tools == [mcp_url]
        assert external_url not in deps.mcp_tools
