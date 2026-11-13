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

from typing import NamedTuple


class McpServersLoad(NamedTuple):
    """
    Result of loading mcp_info.hocon: the file-configured MCP server URLs
    plus whether the file was read successfully.

    loaded_ok separates an authoritatively empty result (a missing or empty
    file — there really are no file-configured servers) from a degraded one
    (the file exists but could not be read or parsed — the set is UNKNOWN).
    Only the former makes it safe to treat a conversation-connected server
    as client-token; see GetMcpTool.get_mcp_servers_load and
    AgentNetworkPersistenceMiddleware for the caller that acts on the
    difference.
    """

    urls: list[str]
    """The MCP server URLs read from the file; [] when missing or unreadable."""

    loaded_ok: bool
    """True when the file was read (or is genuinely absent); False when it
    exists but could not be read or parsed, making urls non-authoritative."""
