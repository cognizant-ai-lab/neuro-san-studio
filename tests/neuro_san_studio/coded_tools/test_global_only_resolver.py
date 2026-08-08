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

from ipaddress import ip_address
from socket import AF_INET
from socket import IPPROTO_TCP
from socket import gaierror
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from aiohttp import ClientSession
from aiohttp import TCPConnector
from aiohttp.abc import ResolveResult

from neuro_san_studio.coded_tools.global_only_resolver import GlobalOnlyResolver


def make_entry(ip: str, host: str = "test-host.example.com", port: int = 80) -> ResolveResult:
    """Build a ResolveResult dict shaped like DefaultResolver output."""
    return {
        "hostname": host,
        "host": ip,
        "port": port,
        "family": AF_INET,
        "proto": IPPROTO_TCP,
        "flags": 0,
    }


def make_resolver(outcome: list[ResolveResult] | Exception) -> GlobalOnlyResolver:
    """Return a GlobalOnlyResolver whose inner DefaultResolver is mocked.

    :param outcome: ResolveResult entries the inner resolver returns, or an
                    exception it raises. No live DNS lookups are performed.
    """
    resolver = GlobalOnlyResolver()
    inner = MagicMock()
    if isinstance(outcome, Exception):
        inner.resolve = AsyncMock(side_effect=outcome)
    else:
        inner.resolve = AsyncMock(return_value=outcome)
    inner.close = AsyncMock()
    resolver._resolver = inner  # pylint: disable=protected-access
    return resolver


class TestGlobalOnlyResolver(IsolatedAsyncioTestCase):
    """Unit tests for GlobalOnlyResolver.resolve and ensure_global_address."""

    async def test_public_record_returned(self):
        """Tests that a hostname resolving to a public IP returns the resolved entries."""
        entries = [make_entry("93.184.216.34")]
        resolver = make_resolver(entries)
        results = await resolver.resolve("test-host.example.com", 80)
        self.assertEqual(results, entries)

    async def test_multiple_public_records_returned(self):
        """Tests that multiple all-public DNS records are returned unchanged."""
        entries = [make_entry("93.184.216.34"), make_entry("151.101.1.140")]
        resolver = make_resolver(entries)
        results = await resolver.resolve("test-host.example.com", 80)
        self.assertEqual(results, entries)

    async def test_private_record_blocked(self):
        """Tests that a hostname resolving to a private IP raises url_not_allowed."""
        resolver = make_resolver([make_entry("10.0.0.5")])
        with self.assertRaises(ValueError) as ctx:
            await resolver.resolve("internal.example.com", 80)
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_mixed_records_blocked(self):
        """Tests that one non-global record among public ones blocks the host (all records must be global)."""
        resolver = make_resolver([make_entry("93.184.216.34"), make_entry("169.254.169.254")])
        with self.assertRaises(ValueError) as ctx:
            await resolver.resolve("mixed.example.com", 80)
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_dns_failure_blocked(self):
        """Tests that a DNS resolution failure raises url_not_allowed instead of OSError."""
        resolver = make_resolver(gaierror("NXDOMAIN"))
        with self.assertRaises(ValueError) as ctx:
            await resolver.resolve("nonexistent.example.com", 80)
        self.assertIn("url_not_allowed", str(ctx.exception))
        self.assertIn("could not be resolved", str(ctx.exception))

    async def test_empty_records_blocked(self):
        """Tests that a hostname resolving to zero addresses raises url_not_allowed."""
        resolver = make_resolver([])
        with self.assertRaises(ValueError) as ctx:
            await resolver.resolve("empty.example.com", 80)
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_zoned_ipv6_link_local_blocked(self):
        """Tests that a zoned link-local IPv6 record (fe80::1%eth0) is blocked as non-global."""
        resolver = make_resolver([make_entry("fe80::1%eth0")])
        with self.assertRaises(ValueError) as ctx:
            await resolver.resolve("linklocal.example.com", 80)
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_unparseable_address_blocked(self):
        """Tests that a record that cannot be parsed as an IP address fails closed with url_not_allowed."""
        resolver = make_resolver([make_entry("not-an-ip")])
        with self.assertRaises(ValueError) as ctx:
            await resolver.resolve("weird.example.com", 80)
        self.assertIn("url_not_allowed", str(ctx.exception))

    async def test_close_delegates_to_inner_resolver(self):
        """Tests that close() closes the wrapped DefaultResolver."""
        resolver = make_resolver([make_entry("93.184.216.34")])
        await resolver.close()
        resolver._resolver.close.assert_awaited_once()  # pylint: disable=protected-access

    def test_ensure_global_address_allows_global(self):
        """Tests that ensure_global_address accepts a globally routable address."""
        GlobalOnlyResolver.ensure_global_address("example.com", ip_address("8.8.8.8"))  # should not raise

    def test_ensure_global_address_blocks_non_global(self):
        """Tests that ensure_global_address rejects a non-global address with url_not_allowed."""
        with self.assertRaises(ValueError) as ctx:
            GlobalOnlyResolver.ensure_global_address("example.com", ip_address("192.168.1.1"))
        self.assertIn("url_not_allowed", str(ctx.exception))


class TestGlobalOnlyResolverIntegration(IsolatedAsyncioTestCase):
    """Tests that resolver errors propagate through a real aiohttp connector.

    This is the wiring that closes the DNS-rebinding gap: the ValueError raised
    at connection time must surface unchanged from session.get(). TCPConnector
    only wraps OSError, so no request is ever made to a non-global address and
    the tool's url_not_allowed contract is preserved.
    """

    async def test_private_record_blocks_request_at_connection_time(self):
        """Tests that a private DNS record aborts session.get() with url_not_allowed before any connection."""
        resolver = make_resolver([make_entry("10.0.0.5")])
        connector = TCPConnector(resolver=resolver, use_dns_cache=False)
        async with ClientSession(connector=connector) as session:
            with self.assertRaises(ValueError) as ctx:
                async with session.get("http://test-host.example.com/"):
                    pass
        self.assertIn("url_not_allowed", str(ctx.exception))
