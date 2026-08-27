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

"""Tests for HoconAgentNetworkAssembler's sly_data_schema emission."""

import asyncio
import os
import re
from pathlib import Path

from pyhocon import ConfigFactory

from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler

REPO_ROOT = Path(__file__).resolve().parents[4]

OAUTH_URL = "https://oauth.example.com/mcp"
FILE_AUTH_URL = "https://file-auth.example.com/mcp"

# Client-token servers (from the conversation's sly_data http_headers), each
# mapped to the header names it supplied; FILE_AUTH_URL is a file-configured
# server and deliberately not in it.
CLIENT_TOKEN_MCP_HEADERS: dict[str, list[str]] = {OAUTH_URL: ["Authorization"]}

NETWORK_DEF: dict = {
    "front_man": {"description": "top", "instructions": "Coordinate.", "tools": ["helper", OAUTH_URL]},
    "helper": {"description": "helps", "instructions": "Help.", "tools": [FILE_AUTH_URL]},
}


def assemble(client_token_mcp_headers: dict[str, list[str]] | None) -> str:
    """Assemble the test network into HOCON text."""
    assembler = HoconAgentNetworkAssembler(demo_mode=False)
    return asyncio.run(
        assembler.assemble_agent_network(NETWORK_DEF, "front_man", "test_net", ["query one"], client_token_mcp_headers)
    )


def parse(hocon_text: str) -> dict:
    """Parse assembled HOCON from the repo root so its includes resolve."""
    cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        return ConfigFactory.parse_string(hocon_text)
    finally:
        os.chdir(cwd)


def unquote(key: str) -> str:
    """
    Strip the quotes pyhocon keeps embedded in quoted keys that contain dots
    (URL keys come back as '"https://..."'). Clients normalize the same way —
    see nsflow's _clean_schema_url — and the neuro-san restorer shows the
    identical artifact for the hand-written you_search.hocon.
    """
    return key.strip('"')


class TestHoconAssemblerSlyDataSchema:
    """The generated HOCON text declares the network's MCP header needs."""

    def test_front_man_declares_the_schema_and_it_parses(self):
        """The emitted text stays valid HOCON and carries the nsflow contract."""
        config = parse(assemble(CLIENT_TOKEN_MCP_HEADERS))

        front_man = config["tools"][0]
        assert front_man["name"] == "front_man"
        http_headers = front_man["function"]["sly_data_schema"]["properties"]["http_headers"]
        # Only the client-token URL is declared, and it is required.
        url_properties = {unquote(url): value for url, value in http_headers["properties"].items()}
        assert list(url_properties) == [OAUTH_URL]
        assert list(http_headers["required"]) == [OAUTH_URL]
        assert list(url_properties[OAUTH_URL]["required"]) == ["Authorization"]
        # The description substitution still landed alongside the schema.
        assert "top" in front_man["function"]["description"]

    def test_non_top_agents_carry_no_schema(self):
        """Only the front man talks to clients; helpers must not declare one."""
        config = parse(assemble(CLIENT_TOKEN_MCP_HEADERS))
        for agent in config["tools"][1:]:
            assert "sly_data_schema" not in agent.get("function", {})

    def test_no_mcp_means_no_schema_and_unchanged_output(self):
        """Without MCP the text is byte-identical to the pre-schema behavior."""
        without_client_urls = assemble(None)
        with_no_client_urls = assemble({})

        assert "sly_data_schema" not in without_client_urls
        # The two renders differ only in the date_created stamp.
        strip_date = re.compile(r'"date_created": "[^"]*"')
        assert strip_date.sub("", without_client_urls) == strip_date.sub("", with_no_client_urls)

        config = parse(without_client_urls)
        assert "sly_data_schema" not in config["tools"][0]["function"]

    def test_a_non_ascii_url_key_round_trips_verbatim(self):
        """ensure_ascii=False keeps a non-ASCII URL key matching the tools list;
        an escaped key would read back as literal text pyhocon never decodes."""
        # The non-ASCII character must live in the path, not the host: CI
        # link-checks string literals (lychee) and skips example.com hosts,
        # but a non-ASCII host punycodes to a real, checkable domain.
        unicode_url = "https://example.com/mçp"
        network_def = {"front_man": {"description": "top", "instructions": "Go.", "tools": [unicode_url]}}
        assembler = HoconAgentNetworkAssembler(demo_mode=False)
        text = asyncio.run(
            assembler.assemble_agent_network(
                network_def, "front_man", "test_net", ["q"], {unicode_url: ["Authorization"]}
            )
        )

        # The raw character survives in the emitted text, not a \uXXXX escape...
        assert unicode_url in text
        assert "m\\u00e7p" not in text

        # ...and parses back to the same key the tools list uses.
        http_headers = parse(text)["tools"][0]["function"]["sly_data_schema"]["properties"]["http_headers"]
        assert [unquote(url) for url in http_headers["properties"]] == [unicode_url]
        assert list(http_headers["required"]) == [unicode_url]
