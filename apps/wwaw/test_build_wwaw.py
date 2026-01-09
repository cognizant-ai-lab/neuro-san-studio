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

from unittest.mock import Mock

from build_wwaw import WebAgentNetworkBuilder


def test_create_intermediate_agents_single_pass():
    builder = WebAgentNetworkBuilder()
    parent = "parent_agent"
    chunks = [["child1", "child2"], ["child3", "child4"]]
    new_agents = {parent: {"instructions": "Parent instructions", "down_chains": [], "top_agent": "true"}}

    intermediate_names = builder.create_intermediate_agents(parent, chunks, new_agents)

    # Check number of intermediate agents created
    assert len(intermediate_names) == 2

    # Check each created agent exists and has the correct properties
    for name, expected_chunk in zip(intermediate_names, chunks):
        assert name in new_agents
        agent = new_agents[name]
        assert agent["down_chains"] == expected_chunk
        assert agent["top_agent"] == "false"
        assert "grouping" in agent["instructions"]


def test_process_page_single_pass():
    builder = WebAgentNetworkBuilder()
    url = "http://example.com"
    parent_name = None
    visited = set()
    existing_names = set()
    agents = {}
    count = 0
    to_visit = []
    base_domain = "example.com"

    html = """
    <html><head><title>Test Page</title></head>
    <body>
        <p>This is a test page with enough text content to pass the minimum length requirement.</p>
        <a href="/about">About</a>
        <a href="http://example.com/contact">Contact</a>
        <a href="http://otherdomain.com/external">External</a>
    </body></html>
    """
    resp = Mock()
    resp.text = html
    resp.headers = {"Content-Type": "text/html"}

    # Force text extractor to generate sufficient text
    builder.MIN_PAGE_LEN = 10
    builder.PAGE_LEN_MAX = 5000
    builder.AGENT_INSTRUCTION_PREFACE = "Agent Instructions:"

    new_count = builder._process_page(
        url, parent_name, resp, visited, existing_names, agents, count, to_visit, base_domain
    )

    assert new_count == count + 1
    assert url in visited
    assert len(agents) == 1
    name = next(iter(agents))
    assert "Agent Instructions:" in agents[name]["instructions"]
    assert agents[name]["down_chains"] == []
    assert len(to_visit) == 2  # /about and /contact; external should be ignored
    assert all("example.com" in link for link, _ in to_visit)
