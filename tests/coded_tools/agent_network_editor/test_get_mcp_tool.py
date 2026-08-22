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
"""
Policy tests for GetMcpTool's process-wide caches and its per-conversation
sly_data path: how the TTL and per-server fetch cap are validated, what gets
published, what must never be published (or cached), and how failures
degrade. The generic cache mechanism itself is covered by
test_shared_process_cache.py; these tests pin the policy layered on top of
it, with the MCP client layer stubbed out.

Skipped (not failed) in environments whose neuro-san predates the imports
get_mcp_tool needs, so the suite still collects everywhere.
"""

import asyncio
import os
import sys
from unittest import TestCase
from unittest import mock

import pytest

pytest.importorskip("coded_tools.agent_network_editor.get_mcp_tool")

# The imports must stay below importorskip so old environments skip cleanly,
# and the tests reach the class's protected policy helpers by design.
# pylint: disable=wrong-import-position,protected-access
from coded_tools.agent_network_editor.get_mcp_tool import BUNDLED_MCP_INFO_FILE  # noqa: E402
from coded_tools.agent_network_editor.get_mcp_tool import DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS  # noqa: E402
from coded_tools.agent_network_editor.get_mcp_tool import DEFAULT_MCP_TOOLS_TTL_SECONDS  # noqa: E402
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool  # noqa: E402
from coded_tools.agent_network_editor.globals import ProcessGlobals  # noqa: E402
from coded_tools.agent_network_editor.mcp_servers_load import McpServersLoad  # noqa: E402

MCP_SERVERS: list[str] = ["https://one.example/mcp", "https://two.example/mcp"]

# A server the conversation supplies auth headers for (not file-configured).
CLIENT_URL: str = "https://oauth.example/mcp"

TTL_ENV: str = "AGENT_NETWORK_DESIGNER_MCP_TOOLS_TTL_SECONDS"
FETCH_TIMEOUT_ENV: str = "AGENT_NETWORK_DESIGNER_MCP_TOOLS_FETCH_TIMEOUT_SECONDS"


class TestGetMcpToolConfig(TestCase):
    """Validation policy for the env vars and the fingerprint they feed."""

    def test_ttl_falls_back_to_the_default_on_garbage(self):
        """Unset, unparseable, and non-finite TTLs all mean the default."""
        with mock.patch.dict(os.environ):
            os.environ.pop(TTL_ENV, None)
            os.environ.pop(FETCH_TIMEOUT_ENV, None)
            self.assertEqual(GetMcpTool._mcp_tools_ttl_seconds(), DEFAULT_MCP_TOOLS_TTL_SECONDS)
            # nan and inf parse as floats but would silently freeze the
            # time bucket, so they are rejected alongside plain garbage.
            for raw in ("not-a-number", "nan", "inf", "-inf"):
                os.environ[TTL_ENV] = raw
                self.assertEqual(GetMcpTool._mcp_tools_ttl_seconds(), DEFAULT_MCP_TOOLS_TTL_SECONDS)

    def test_ttl_of_zero_or_less_freezes_the_time_bucket(self):
        """<= 0 disables time-based refresh: no clamp, bucket pinned at 0."""
        with mock.patch.dict(os.environ):
            os.environ.pop(FETCH_TIMEOUT_ENV, None)
            for raw, expected in (("0", 0.0), ("-5", -5.0)):
                os.environ[TTL_ENV] = raw
                self.assertEqual(GetMcpTool._mcp_tools_ttl_seconds(), expected)
                # The time bucket is the last fingerprint component.
                self.assertEqual(GetMcpTool._mcp_tools_fingerprint()[-1], 0)

    def test_ttl_is_clamped_to_twice_the_fetch_cap(self):
        """A TTL shorter than one fetch would livelock the cache; clamp it."""
        with mock.patch.dict(os.environ):
            os.environ.pop(FETCH_TIMEOUT_ENV, None)
            os.environ[TTL_ENV] = "5"
            self.assertEqual(GetMcpTool._mcp_tools_ttl_seconds(), 2 * DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS)
            os.environ[FETCH_TIMEOUT_ENV] = "100"
            self.assertEqual(GetMcpTool._mcp_tools_ttl_seconds(), 200.0)
            # With the cap disabled, the default cap is the clamp basis.
            os.environ[FETCH_TIMEOUT_ENV] = "0"
            self.assertEqual(GetMcpTool._mcp_tools_ttl_seconds(), 2 * DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS)
            # A comfortable TTL is left alone.
            os.environ.pop(FETCH_TIMEOUT_ENV, None)
            os.environ[TTL_ENV] = "500"
            self.assertEqual(GetMcpTool._mcp_tools_ttl_seconds(), 500.0)

    def test_fetch_timeout_defaults_on_garbage_and_disables_below_zero(self):
        """Garbage means the default; <= 0 removes the cap entirely (None)."""
        with mock.patch.dict(os.environ):
            os.environ.pop(FETCH_TIMEOUT_ENV, None)
            self.assertEqual(GetMcpTool._mcp_tools_fetch_timeout_seconds(), DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS)
            os.environ[FETCH_TIMEOUT_ENV] = "120"
            self.assertEqual(GetMcpTool._mcp_tools_fetch_timeout_seconds(), 120.0)
            for raw in ("not-a-number", "nan", "inf"):
                os.environ[FETCH_TIMEOUT_ENV] = raw
                self.assertEqual(
                    GetMcpTool._mcp_tools_fetch_timeout_seconds(), DEFAULT_MCP_TOOLS_FETCH_TIMEOUT_SECONDS
                )
            for raw in ("0", "-1"):
                os.environ[FETCH_TIMEOUT_ENV] = raw
                self.assertIsNone(GetMcpTool._mcp_tools_fetch_timeout_seconds())

    def test_a_ttl_change_is_an_immediate_fingerprint_miss(self):
        """Bucket numbers from different TTL regimes must never compare equal."""
        with mock.patch.dict(os.environ):
            os.environ.pop(FETCH_TIMEOUT_ENV, None)
            os.environ[TTL_ENV] = "100000"
            before = GetMcpTool._mcp_tools_fingerprint()
            os.environ[TTL_ENV] = "50000"
            self.assertNotEqual(GetMcpTool._mcp_tools_fingerprint(), before)

    def test_a_deleted_cwd_falls_back_to_the_bundled_file(self):
        """get_mcp_info_file runs inside fingerprint probes; it must not raise."""
        with mock.patch.dict(os.environ):
            os.environ.pop("MCP_SERVERS_INFO_FILE", None)
            with mock.patch(
                "coded_tools.agent_network_editor.get_mcp_tool.Path.cwd",
                side_effect=FileNotFoundError("cwd was deleted"),
            ):
                self.assertEqual(GetMcpTool.get_mcp_info_file(), str(BUNDLED_MCP_INFO_FILE))


class TestGetMcpServers(TestCase):
    """Publish policy for the shared MCP-servers cache."""

    def setUp(self):
        # tests/conftest.py's autouse fixture also clears the shared caches
        # around every test; clearing here as well keeps these tests correct
        # when run directly through unittest.
        GetMcpTool.clear_shared_mcp_servers_for_testing()
        GetMcpTool.clear_shared_mcp_tool_descriptions_for_testing()

    def test_a_missing_file_publishes_an_empty_list(self):
        """No config file means no file-configured MCP servers, not an error."""
        with mock.patch.dict(os.environ, {"MCP_SERVERS_INFO_FILE": "/nonexistent/mcp_info.hocon"}):
            self.assertEqual(asyncio.run(GetMcpTool.get_mcp_servers()), [])

    def test_unreadable_and_unparseable_files_publish_an_empty_list(self):
        """OSError (unreadable) and ValueError (unparseable) both degrade to []."""
        for error in (OSError("permission denied"), ValueError("bad hocon")):
            GetMcpTool.clear_shared_mcp_servers_for_testing()
            restorer = mock.Mock()
            restorer.restore.side_effect = error
            with mock.patch(
                "coded_tools.agent_network_editor.get_mcp_tool.McpServersInfoRestorer", return_value=restorer
            ):
                self.assertEqual(asyncio.run(GetMcpTool.get_mcp_servers()), [])

    def test_load_reports_a_failure_only_when_the_file_load_failed(self):
        """A broken file is 'unknown' (loaded_ok False); missing, empty, and
        good files all load ok."""
        # A missing file is an authoritative empty, not a failure.
        with mock.patch.dict(os.environ, {"MCP_SERVERS_INFO_FILE": "/nonexistent/mcp_info.hocon"}):
            self.assertEqual(asyncio.run(GetMcpTool.get_mcp_servers_load()), McpServersLoad([], True))

        # A file that exists but cannot be read/parsed is unknown.
        for error in (OSError("permission denied"), ValueError("bad hocon")):
            GetMcpTool.clear_shared_mcp_servers_for_testing()
            restorer = mock.Mock()
            restorer.restore.side_effect = error
            with mock.patch(
                "coded_tools.agent_network_editor.get_mcp_tool.McpServersInfoRestorer", return_value=restorer
            ):
                self.assertEqual(asyncio.run(GetMcpTool.get_mcp_servers_load()), McpServersLoad([], False))

        # A file that loads reports its URLs with loaded_ok True.
        GetMcpTool.clear_shared_mcp_servers_for_testing()
        restorer = mock.Mock()
        restorer.restore.return_value = {"https://one.example/mcp": {}}
        with mock.patch("coded_tools.agent_network_editor.get_mcp_tool.McpServersInfoRestorer", return_value=restorer):
            self.assertEqual(
                asyncio.run(GetMcpTool.get_mcp_servers_load()), McpServersLoad(["https://one.example/mcp"], True)
            )


class TestSlyDataHttpHeaderUrls(TestCase):
    """Extraction of the per-conversation MCP header URLs from sly_data."""

    def test_urls_are_extracted_in_order(self):
        """Well-formed http_headers yields its URL keys, order preserved."""
        sly_data = {
            "http_headers": {
                "https://a.example/mcp": {"Authorization": "Bearer x"},
                "https://b.example/mcp": {"X-Api-Key": "y"},
            }
        }
        self.assertEqual(
            GetMcpTool.sly_data_http_header_urls(sly_data),
            ["https://a.example/mcp", "https://b.example/mcp"],
        )

    def test_missing_or_malformed_shapes_read_as_no_urls(self):
        """Clients control this input: absent/broken shapes must not raise."""
        for sly_data in (None, {}, {"http_headers": None}, {"http_headers": "not-a-dict"}, {"http_headers": []}):
            self.assertEqual(GetMcpTool.sly_data_http_header_urls(sly_data), [])

    def test_malformed_entries_are_skipped(self):
        """Non-string keys and non-dict header values are dropped, not fatal."""
        sly_data = {
            "http_headers": {
                "https://good.example/mcp": {"Authorization": "Bearer x"},
                42: {"Authorization": "Bearer y"},
                "https://bad.example/mcp": "not-a-dict",
            }
        }
        self.assertEqual(GetMcpTool.sly_data_http_header_urls(sly_data), ["https://good.example/mcp"])

    def test_non_http_urls_are_skipped(self):
        """Only http(s) MCP URLs count; a '/'-path or other scheme is not a server."""
        sly_data = {
            "http_headers": {
                "/internal_admin_network": {"Authorization": "Bearer x"},
                "ftp://host/mcp": {"Authorization": "Bearer y"},
                "https://ok.example/mcp": {"Authorization": "Bearer z"},
            }
        }
        self.assertEqual(GetMcpTool.sly_data_http_header_urls(sly_data), ["https://ok.example/mcp"])

    def test_malformed_urls_are_skipped(self):
        """An accepted URL becomes a fetch target and a verbatim log line,
        so a control-character (log-forging) or userinfo-bearing key never
        classifies (shape rules pinned in test_mcp_header_hygiene.py)."""
        sly_data = {
            "http_headers": {
                "https://ok.example/mcp\nFORGED": {"Authorization": "Bearer x"},
                "https://user:pass@ok.example/mcp": {"Authorization": "Bearer y"},
                "https://ok.example/mcp": {"Authorization": "Bearer z"},
            }
        }
        self.assertEqual(GetMcpTool.sly_data_http_header_urls(sly_data), ["https://ok.example/mcp"])

    def test_urls_without_a_usable_header_are_skipped(self):
        """An empty dict, a blank value, a non-string value, or an illegal
        header name supplies no credential the fetch could send."""
        sly_data = {
            "http_headers": {
                "https://empty.example/mcp": {},
                "https://blank.example/mcp": {"Authorization": "   "},
                "https://nonstr.example/mcp": {"Authorization": 123},
                "https://badname.example/mcp": {"Auth orization": "Bearer x"},
                "https://ok.example/mcp": {"Authorization": "Bearer tok"},
            }
        }
        self.assertEqual(GetMcpTool.sly_data_http_header_urls(sly_data), ["https://ok.example/mcp"])


class TestGetMcpToolDescriptions(TestCase):
    """Publish/degrade policy for the shared cache, plus the sly_data path."""

    def setUp(self):
        GetMcpTool.clear_shared_mcp_servers_for_testing()
        GetMcpTool.clear_shared_mcp_tool_descriptions_for_testing()
        self.fetch_log: list[str] = []
        self.headers_log: dict[str, dict | None] = {}
        self.listings: dict[str, str] = {server: f"tools of {server}" for server in MCP_SERVERS}

    def _patched_fetches(self):
        """Stub the per-server fetch; a server absent from self.listings fails."""
        fetch_log = self.fetch_log
        headers_log = self.headers_log
        listings = self.listings

        async def fake_fetch(
            server: str, _fetch_timeout: float | None, headers: dict | None = None
        ) -> tuple[str, str | None]:
            fetch_log.append(server)
            headers_log[server] = headers
            return server, listings.get(server)

        return mock.patch.object(GetMcpTool, "_fetch_tool_descriptions", new=fake_fetch)

    def _patched_servers(self, servers: list[str] | None = None):
        """Pin the servers half so these tests never read the real config file."""
        pinned = MCP_SERVERS if servers is None else servers
        loaded = McpServersLoad(list(pinned), True)
        return mock.patch.object(GetMcpTool._shared_mcp_servers_cache, "get", new=mock.Mock(return_value=loaded))

    def test_concurrent_callers_share_one_fetch_and_warm_reads_are_free(self):
        """A cold burst fetches each server once; warm reads fetch nothing."""

        async def run() -> list[dict[str, str]]:
            burst = await asyncio.gather(*[GetMcpTool.get_mcp_tool_descriptions() for _ in range(10)])
            warm = await GetMcpTool.get_mcp_tool_descriptions()
            return burst + [warm]

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            results = asyncio.run(run())

        for result in results:
            self.assertEqual(result, self.listings)
        # One fetch per server for the whole burst, none for the warm read.
        self.assertEqual(sorted(self.fetch_log), sorted(MCP_SERVERS))

    def test_a_failed_server_is_omitted_and_the_partial_result_is_published(self):
        """One dead server hides that server only, and only until the TTL rolls."""
        del self.listings[MCP_SERVERS[1]]

        async def run() -> tuple[dict[str, str], dict[str, str]]:
            return await GetMcpTool.get_mcp_tool_descriptions(), await GetMcpTool.get_mcp_tool_descriptions()

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            first, second = asyncio.run(run())

        self.assertEqual(first, self.listings)
        self.assertEqual(second, self.listings)
        # The partial result was published: one fetch per server, total.
        self.assertEqual(sorted(self.fetch_log), sorted(MCP_SERVERS))

    def test_all_failed_with_frozen_ttl_degrades_per_call_and_heals(self):
        """With refresh disabled, an all-failed fetch must not be pinned forever."""
        healthy = dict(self.listings)
        self.listings.clear()

        with mock.patch.dict(os.environ, {TTL_ENV: "0"}), self._patched_servers(), self._patched_fetches():
            self.assertEqual(asyncio.run(GetMcpTool.get_mcp_tool_descriptions()), {})
            # Nothing was published: the moment the servers answer again,
            # callers get the full mapping — no fingerprint change needed.
            self.listings.update(healthy)
            self.assertEqual(asyncio.run(GetMcpTool.get_mcp_tool_descriptions()), healthy)

    def test_all_failed_with_a_live_ttl_is_published_for_the_window(self):
        """With refresh enabled, publishing {} prevents a per-call fetch storm."""
        self.listings.clear()

        async def run() -> tuple[dict[str, str], dict[str, str]]:
            return await GetMcpTool.get_mcp_tool_descriptions(), await GetMcpTool.get_mcp_tool_descriptions()

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            first, second = asyncio.run(run())

        self.assertEqual((first, second), ({}, {}))
        # The empty result was published: the second call fetched nothing.
        self.assertEqual(sorted(self.fetch_log), sorted(MCP_SERVERS))

    def test_no_configured_servers_publishes_empty_even_when_frozen(self):
        """An empty server list is a fact, not a failure — publish it."""
        with mock.patch.dict(os.environ, {TTL_ENV: "0"}), self._patched_servers([]), self._patched_fetches():
            self.assertEqual(asyncio.run(GetMcpTool.get_mcp_tool_descriptions()), {})
            self.assertEqual(asyncio.run(GetMcpTool.get_mcp_tool_descriptions()), {})
        self.assertEqual(self.fetch_log, [])

    def test_returned_mapping_is_a_copy(self):
        """Mutating a returned mapping must not corrupt the shared value."""

        async def run() -> dict[str, str]:
            first = await GetMcpTool.get_mcp_tool_descriptions()
            first["https://tampered.example"] = "oops"
            return await GetMcpTool.get_mcp_tool_descriptions()

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            second = asyncio.run(run())

        self.assertNotIn("https://tampered.example", second)

    def test_async_invoke_renders_the_mapping_as_a_string(self):
        """The coded-tool entry point returns str(mapping), per its contract."""
        tool: GetMcpTool = GetMcpTool.__new__(GetMcpTool)

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            result = asyncio.run(tool.async_invoke(args={}, sly_data={}))

        self.assertEqual(result, str(self.listings))

    def test_async_invoke_merges_sly_data_server_listings(self):
        """sly_data http_headers servers are fetched with their own headers."""
        tool: GetMcpTool = GetMcpTool.__new__(GetMcpTool)
        self.listings[CLIENT_URL] = f"tools of {CLIENT_URL}"
        sly_data = {"http_headers": {CLIENT_URL: {"Authorization": "Bearer tok-0"}}}

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            result = asyncio.run(tool.async_invoke(args={}, sly_data=sly_data))

        # The client server got exactly the conversation's header dict...
        self.assertEqual(self.headers_log[CLIENT_URL], {"Authorization": "Bearer tok-0"})
        # ...file servers got none, and everything landed in the output.
        for server in MCP_SERVERS:
            self.assertIsNone(self.headers_log[server])
            self.assertIn(f"tools of {server}", result)
        self.assertIn(f"tools of {CLIENT_URL}", result)
        # The token itself never surfaces in what the LLM will see.
        self.assertNotIn("tok-0", result)

    def test_a_file_configured_server_ignores_sly_data_headers(self):
        """A URL in both sources stays a server-side concern: no client fetch."""
        tool: GetMcpTool = GetMcpTool.__new__(GetMcpTool)
        sly_data = {"http_headers": {MCP_SERVERS[0]: {"Authorization": "Bearer stale"}}}

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            asyncio.run(tool.async_invoke(args={}, sly_data=sly_data))

        # Exactly one (shared, headerless) fetch — no second, client-headed one.
        self.assertEqual(self.fetch_log.count(MCP_SERVERS[0]), 1)
        self.assertIsNone(self.headers_log[MCP_SERVERS[0]])

    def test_sly_data_listings_are_fetched_per_call_not_cached(self):
        """Client-authenticated listings must never be served across calls."""
        tool: GetMcpTool = GetMcpTool.__new__(GetMcpTool)
        self.listings[CLIENT_URL] = "client tools"
        sly_data = {"http_headers": {CLIENT_URL: {"Authorization": "Bearer tok"}}}

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            asyncio.run(tool.async_invoke(args={}, sly_data=sly_data))
            asyncio.run(tool.async_invoke(args={}, sly_data=sly_data))

        # File servers: one shared fetch each; the client server: one per call.
        for server in MCP_SERVERS:
            self.assertEqual(self.fetch_log.count(server), 1)
        self.assertEqual(self.fetch_log.count(CLIENT_URL), 2)

    def test_sly_data_header_values_are_sanitized_before_fetch(self):
        """A token with surrounding whitespace is stripped before it is sent."""
        tool: GetMcpTool = GetMcpTool.__new__(GetMcpTool)
        self.listings[CLIENT_URL] = f"tools of {CLIENT_URL}"
        sly_data = {"http_headers": {CLIENT_URL: {"Authorization": "  Bearer tok-0\n"}}}

        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            asyncio.run(tool.async_invoke(args={}, sly_data=sly_data))

        # The adapter receives the trimmed value, not the raw client input.
        self.assertEqual(self.headers_log[CLIENT_URL], {"Authorization": "Bearer tok-0"})

    def test_client_listings_do_not_leak_across_conversations(self):
        """Two conversations' client-token servers stay isolated: neither
        conversation's sly_data servers may surface in the other's output,
        because those listings are fetched per call and never cached."""
        tool: GetMcpTool = GetMcpTool.__new__(GetMcpTool)
        alice_url = "https://alice.example/mcp"
        bob_url = "https://bob.example/mcp"
        self.listings[alice_url] = "tools of alice"
        self.listings[bob_url] = "tools of bob"
        alice_sly = {"http_headers": {alice_url: {"Authorization": "Bearer alice-tok"}}}
        bob_sly = {"http_headers": {bob_url: {"Authorization": "Bearer bob-tok"}}}

        # Back-to-back in one process, sharing the file-descriptions cache.
        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            result_alice = asyncio.run(tool.async_invoke(args={}, sly_data=alice_sly))
            result_bob = asyncio.run(tool.async_invoke(args={}, sly_data=bob_sly))

        # Each conversation sees its own client server...
        self.assertIn("tools of alice", result_alice)
        self.assertIn("tools of bob", result_bob)
        # ...and never the other conversation's.
        self.assertNotIn("tools of bob", result_alice)
        self.assertNotIn("tools of alice", result_bob)
        # The shared, file-configured servers appear in both (same for everyone).
        for server in MCP_SERVERS:
            self.assertIn(f"tools of {server}", result_alice)
            self.assertIn(f"tools of {server}", result_bob)
        # Neither token reaches the LLM-visible output.
        self.assertNotIn("alice-tok", result_alice)
        self.assertNotIn("bob-tok", result_bob)

    def test_registry_covers_both_mcp_caches(self):
        """globals' REGISTRY triples must resolve now that get_mcp_tool is imported."""
        with mock.patch.dict(os.environ, {TTL_ENV: "100000"}), self._patched_servers(), self._patched_fetches():
            asyncio.run(GetMcpTool.get_mcp_tool_descriptions())
            cache = GetMcpTool._shared_mcp_tool_descriptions_cache
            self.assertIsNotNone(cache.peek())
            # A typo'd module/class/method triple would raise here.
            ProcessGlobals.clear_all_for_testing()
            self.assertIsNone(cache.peek())


class TestFetchToolDescriptions(TestCase):
    """The per-server fetch: cap applied, failures contained, success flattened."""

    @staticmethod
    def _patched_adapter(get_mcp_tools):
        """Patch the MCP adapter with a stub serving the given coroutine function."""
        adapter = mock.Mock()
        adapter.get_mcp_tools = get_mcp_tools
        return mock.patch("coded_tools.agent_network_editor.get_mcp_tool.LangChainMcpAdapter", return_value=adapter)

    def test_a_server_exceeding_the_cap_degrades_to_a_failure(self):
        """A hung server is cut off at the cap and reported as failed."""

        async def never_answers(_server: str, headers: dict | None = None) -> list:  # pylint: disable=unused-argument
            await asyncio.sleep(10)
            return []

        with self._patched_adapter(never_answers):
            server, description = asyncio.run(GetMcpTool._fetch_tool_descriptions("https://slow.example", 0.05))

        self.assertEqual(server, "https://slow.example")
        self.assertIsNone(description)

    def test_a_malformed_tool_degrades_to_that_server_only(self):
        """A tool with no description must fail this server, not the whole load."""

        async def returns_a_broken_tool(  # pylint: disable=unused-argument
            _server: str, headers: dict | None = None
        ) -> list:
            return [mock.Mock(description=None)]

        with self._patched_adapter(returns_a_broken_tool):
            _server, description = asyncio.run(GetMcpTool._fetch_tool_descriptions("https://bad.example", 5.0))

        self.assertIsNone(description)

    def test_descriptions_are_newline_joined(self):
        """A healthy server's tool descriptions flatten into one string."""

        async def returns_two_tools(  # pylint: disable=unused-argument
            _server: str, headers: dict | None = None
        ) -> list:
            return [mock.Mock(description="alpha"), mock.Mock(description="beta")]

        with self._patched_adapter(returns_two_tools):
            _server, description = asyncio.run(GetMcpTool._fetch_tool_descriptions("https://good.example", 5.0))

        self.assertEqual(description, "alpha\nbeta\n")

    def test_headers_are_forwarded_to_the_adapter(self):
        """The per-server fetch passes its headers through to get_mcp_tools."""
        seen: dict[str, dict | None] = {}

        async def records_headers(server: str, headers: dict | None = None) -> list:
            seen[server] = headers
            return [mock.Mock(description="alpha")]

        with self._patched_adapter(records_headers):
            asyncio.run(
                GetMcpTool._fetch_tool_descriptions(
                    "https://auth.example", 5.0, headers={"Authorization": "Bearer tok"}
                )
            )

        self.assertEqual(seen["https://auth.example"], {"Authorization": "Bearer tok"})

    def test_exception_group_leaves_surface_in_the_failure_log(self):
        """The drop-path warning must show the buried cause (e.g. a 401),
        not anyio's opaque 'unhandled errors in a TaskGroup' text (the leaf
        rendering itself is pinned in test_mcp_header_hygiene.py)."""
        if sys.version_info < (3, 11):
            self.skipTest("ExceptionGroup is a 3.11+ builtin")

        nested = ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [ExceptionGroup("inner", [ValueError("401 Unauthorized for url 'https://auth.example'")]), KeyError("k")],
        )

        async def raises_the_group(_server: str, headers: dict | None = None) -> list:
            raise nested

        with self._patched_adapter(raises_the_group), self.assertLogs(level="WARNING") as captured:
            _server, description = asyncio.run(GetMcpTool._fetch_tool_descriptions("https://auth.example", 5.0))

        logged = "\n".join(captured.output)
        self.assertIsNone(description)
        self.assertIn("401 Unauthorized", logged)
        self.assertNotIn("TaskGroup", logged)

    def test_a_leaked_header_value_is_redacted_from_the_failure_log(self):
        """A value-bearing error (mimicking h11) must not put the token in the log."""
        token = "Bearer FAKE-SECRET-xyz\n"

        async def raises_with_value(_server: str, headers: dict | None = None) -> list:
            # h11 renders an illegal header value as its bytes repr.
            raise ValueError(f"Illegal header value {token.encode()!r}")

        with self._patched_adapter(raises_with_value), self.assertLogs(level="WARNING") as captured:
            _server, description = asyncio.run(
                GetMcpTool._fetch_tool_descriptions("https://auth.example", 5.0, headers={"Authorization": token})
            )

        logged = "\n".join(captured.output)
        self.assertIsNone(description)
        self.assertNotIn("FAKE-SECRET-xyz", logged)
        self.assertIn("***", logged)
