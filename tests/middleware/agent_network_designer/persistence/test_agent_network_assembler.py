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

"""Tests for the shared MCP sly_data_schema builder on AgentNetworkAssembler."""

from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler

OAUTH_URL = "https://oauth.example.com/mcp"
FILE_AUTH_URL = "https://file-auth.example.com/mcp"
UNUSED_URL = "https://unused.example.com/mcp"

# The client-token servers, as the persistence middleware derives them from
# the conversation's sly_data http_headers (minus file-configured servers):
# each URL maps to the header names it supplied (names only, never values).
# FILE_AUTH_URL is deliberately absent: mcp_info.hocon servers are a
# server-side concern and never appear in generated schemas.
CLIENT_TOKEN_MCP_HEADERS: dict[str, list[str]] = {OAUTH_URL: ["Authorization"], UNUSED_URL: ["Authorization"]}

NETWORK_DEF: dict = {
    "front_man": {"description": "top", "instructions": "Coordinate.", "tools": ["helper", OAUTH_URL]},
    "helper": {
        "description": "helps",
        "instructions": "Help.",
        "tools": [FILE_AUTH_URL, "/sub_network", "ddgs_search"],
    },
    "ddgs_search": {},
}


class TestBuildMcpSlyDataSchema:
    """The schema builder both assemblers share."""

    def test_no_client_urls_means_no_schema(self):
        """None and empty both mean 'no client-token servers' — emit nothing."""
        assert AgentNetworkAssembler.build_mcp_sly_data_schema(NETWORK_DEF, None) is None
        assert AgentNetworkAssembler.build_mcp_sly_data_schema(NETWORK_DEF, {}) is None

    def test_a_network_using_no_client_token_servers_gets_no_schema(self):
        """Agent names and subnetwork refs in tools lists must not trigger a schema."""
        network_def = {
            "front_man": {"instructions": "Coordinate.", "tools": ["helper", "/sub_network"]},
            "helper": {"instructions": "Help."},
        }
        assert AgentNetworkAssembler.build_mcp_sly_data_schema(network_def, CLIENT_TOKEN_MCP_HEADERS) is None

    def test_shape_matches_the_nsflow_contract(self):
        """properties.http_headers.{properties,required} is what nsflow reads."""
        schema = AgentNetworkAssembler.build_mcp_sly_data_schema(NETWORK_DEF, CLIENT_TOKEN_MCP_HEADERS)

        assert schema["type"] == "object"
        assert schema["required"] == ["http_headers"]
        http_headers = schema["properties"]["http_headers"]
        assert http_headers["type"] == "object"
        # Only the used client-token url is declared...
        assert list(http_headers["properties"]) == [OAUTH_URL]
        # ...and each declared url expects an Authorization header.
        for url_schema in http_headers["properties"].values():
            assert url_schema["required"] == ["Authorization"]
            assert url_schema["properties"]["Authorization"]["type"] == "string"

    def test_only_client_token_servers_are_declared_and_required(self):
        """File-configured servers are omitted; every declared URL gates chat."""
        schema = AgentNetworkAssembler.build_mcp_sly_data_schema(NETWORK_DEF, CLIENT_TOKEN_MCP_HEADERS)
        http_headers = schema["properties"]["http_headers"]
        assert FILE_AUTH_URL not in http_headers["properties"]
        assert http_headers["required"] == [OAUTH_URL]

    def test_a_network_using_only_file_servers_gets_no_schema(self):
        """File-configured servers need no client input, so no schema is emitted."""
        network_def = {"front_man": {"instructions": "Go.", "tools": [FILE_AUTH_URL]}}
        assert AgentNetworkAssembler.build_mcp_sly_data_schema(network_def, CLIENT_TOKEN_MCP_HEADERS) is None

    def test_unused_servers_are_not_declared(self):
        """Only URLs the network references appear in the schema."""
        schema = AgentNetworkAssembler.build_mcp_sly_data_schema(NETWORK_DEF, CLIENT_TOKEN_MCP_HEADERS)
        assert UNUSED_URL not in schema["properties"]["http_headers"]["properties"]

    def test_duplicate_and_malformed_tools_entries_are_tolerated(self):
        """A URL used twice is declared once; malformed shapes are skipped."""
        network_def = {
            "front_man": {"instructions": "Go.", "tools": [OAUTH_URL, "helper", None, 42]},
            "helper": {"instructions": "Help.", "tools": [OAUTH_URL]},
            "broken": "not-a-dict",
            # coerce_tools reads a str-valued tools field as [] instead of
            # iterating its characters.
            "strtools": {"instructions": "Odd.", "tools": "not-a-list"},
        }
        schema = AgentNetworkAssembler.build_mcp_sly_data_schema(network_def, CLIENT_TOKEN_MCP_HEADERS)
        assert list(schema["properties"]["http_headers"]["properties"]) == [OAUTH_URL]
        assert schema["properties"]["http_headers"]["required"] == [OAUTH_URL]

    def test_declared_headers_match_the_supplied_header_names(self):
        """A server authenticated with a non-Authorization header is described
        with THAT header, not a hardcoded Authorization."""
        network_def = {"front_man": {"instructions": "Go.", "tools": [OAUTH_URL]}}
        schema = AgentNetworkAssembler.build_mcp_sly_data_schema(network_def, {OAUTH_URL: ["X-Api-Key"]})
        url_schema = schema["properties"]["http_headers"]["properties"][OAUTH_URL]
        assert list(url_schema["properties"]) == ["X-Api-Key"]
        assert url_schema["required"] == ["X-Api-Key"]
        assert "Authorization" not in url_schema["properties"]

    def test_multiple_supplied_headers_are_all_declared(self):
        """Every header name the conversation supplied is declared and required."""
        network_def = {"front_man": {"instructions": "Go.", "tools": [OAUTH_URL]}}
        schema = AgentNetworkAssembler.build_mcp_sly_data_schema(
            network_def, {OAUTH_URL: ["Authorization", "X-Tenant"]}
        )
        url_schema = schema["properties"]["http_headers"]["properties"][OAUTH_URL]
        assert list(url_schema["properties"]) == ["Authorization", "X-Tenant"]
        assert url_schema["required"] == ["Authorization", "X-Tenant"]
