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
Policy tests for GetExternalNetwork's process-wide descriptions cache: what gets
published, what must never be published, and when the shared cache is
bypassed. The generic cache mechanism itself is covered by
test_shared_process_cache.py; these tests pin the policy layered on top of
it, with the framework session layer stubbed out.

Skipped (not failed) in environments whose neuro-san predates the imports
get_external_network needs, so the suite still collects everywhere.
"""

import asyncio
import os
from typing import Any
from unittest import TestCase
from unittest import mock

import pytest

from neuro_san_studio.agent_network_designer.common.shared_process_cache import SharedProcessCache

pytest.importorskip("neuro_san_studio.agent_network_designer.tools.get_external_network")

# The import must stay below importorskip so old environments skip cleanly.
# pylint: disable-next=wrong-import-position
from neuro_san_studio.agent_network_designer.tools.get_external_network import GetExternalNetwork  # noqa: E402

EXTERNAL_NETWORK_NAMES: list[str] = ["/alpha", "/beta"]


class TestGetExternalNetwork(TestCase):
    """Behavioral tests for the shared external network descriptions policy."""

    def setUp(self):
        # tests/conftest.py's autouse fixture also clears the shared caches
        # around every test; clearing here as well keeps these tests correct
        # when run directly through unittest.
        GetExternalNetwork.clear_shared_external_network_names_for_testing()
        GetExternalNetwork.clear_shared_external_network_descriptions_for_testing()
        self.fetch_log: list[str] = []
        self.descriptions: dict[str, str] = {"/alpha": "does alpha", "/beta": "does beta"}

    def _make_tool(self) -> GetExternalNetwork:
        """
        Build a GetExternalNetwork (bypassing the framework-only __init__) whose
        run_context chain yields a stub session factory serving
        self.descriptions and recording each fetch in self.fetch_log.

        :return: A GetExternalNetwork whose session factory serves self.descriptions.
        """
        fetch_log = self.fetch_log
        descriptions = self.descriptions

        def create_session(name: str, _invocation_context) -> mock.Mock:
            async def function(_args) -> dict:
                fetch_log.append(name)
                return {"function": {"description": descriptions.get(name, "")}}

            session = mock.Mock()
            session.function = function
            return session

        factory = mock.Mock()
        factory.create_session = create_session

        tool: GetExternalNetwork = GetExternalNetwork.__new__(GetExternalNetwork)
        tool.run_context = mock.Mock()
        tool.run_context.get_invocation_context.return_value.get_async_session_factory.return_value = factory
        return tool

    @staticmethod
    def _patched_names():
        """Pin the names half so these tests never parse the real manifest."""
        return mock.patch.object(
            GetExternalNetwork,
            "get_external_network_names",
            new=mock.AsyncMock(return_value=list(EXTERNAL_NETWORK_NAMES)),
        )

    def test_concurrent_callers_share_one_fetch_and_warm_reads_are_free(self):
        """A cold burst fans out once for the whole loop; warm reads fetch nothing."""

        async def run() -> list[dict[str, str]]:
            calls: list[Any] = []
            for _ in range(10):
                calls.append(self._make_tool().get_external_networks())
            burst: list[dict[str, str]] = await asyncio.gather(*calls)
            warm: dict[str, str] = await self._make_tool().get_external_networks()
            return burst + [warm]

        with self._patched_names():
            results = asyncio.run(run())

        for result in results:
            self.assertEqual(result, self.descriptions)
        # One fetch per external network for the whole burst, none for the warm read.
        self.assertEqual(sorted(self.fetch_log), sorted(EXTERNAL_NETWORK_NAMES))

    def test_context_less_caller_degrades_without_publishing(self):
        """A caller without run_context gets {} per-call, never poisoning the cache."""
        bare: GetExternalNetwork = GetExternalNetwork.__new__(GetExternalNetwork)

        async def run() -> tuple[dict[str, str], dict[str, str]]:
            empty: dict[str, str] = await bare.get_external_networks()
            filled: dict[str, str] = await self._make_tool().get_external_networks()
            return empty, filled

        with self._patched_names():
            empty, filled = asyncio.run(run())

        self.assertEqual(empty, {})
        # Had the {} been published, this caller would have been served it.
        self.assertEqual(filled, self.descriptions)

    def test_context_less_caller_is_served_warm_cache_hits(self):
        """The pre-fill peek serves warm reads even to context-less callers."""

        async def run() -> dict[str, str]:
            await self._make_tool().get_external_networks()
            bare: GetExternalNetwork = GetExternalNetwork.__new__(GetExternalNetwork)
            return await bare.get_external_networks()

        with self._patched_names():
            self.assertEqual(asyncio.run(run()), self.descriptions)

    def test_all_empty_fetches_are_not_published_and_the_next_call_heals(self):
        """A fill whose every fetch failed publishes nothing; recovery is immediate."""
        # Every fetch degrades to "" — the signature of an outage.
        self.descriptions.clear()

        async def run() -> dict[str, str]:
            return await self._make_tool().get_external_networks()

        with self._patched_names():
            self.assertEqual(asyncio.run(run()), {})
            # Nothing was published (no fingerprint change needed to heal):
            # the moment fetches work again, callers get the full mapping.
            self.descriptions.update({"/alpha": "does alpha", "/beta": "does beta"})
            self.assertEqual(asyncio.run(run()), self.descriptions)

    def test_partially_empty_descriptions_are_still_published(self):
        """Some empty descriptions are legitimate; a partial mapping is cached."""
        self.descriptions["/beta"] = ""

        async def run() -> dict[str, str]:
            return await self._make_tool().get_external_networks()

        with self._patched_names():
            first = asyncio.run(run())
            second = asyncio.run(run())

        self.assertEqual(first, {"/alpha": "does alpha", "/beta": ""})
        self.assertEqual(second, first)
        # The second call was served warm — one fetch per external network total.
        self.assertEqual(sorted(self.fetch_log), sorted(EXTERNAL_NETWORK_NAMES))

    def test_returned_mapping_is_a_copy(self):
        """Mutating a returned mapping must not corrupt the shared value."""

        async def run() -> dict[str, str]:
            first: dict[str, str] = await self._make_tool().get_external_networks()
            first["/tampered"] = "oops"
            return await self._make_tool().get_external_networks()

        with self._patched_names():
            second = asyncio.run(run())

        self.assertNotIn("/tampered", second)

    def test_authorizer_bypasses_the_shared_cache(self):
        """With AGENT_AUTHORIZER set, every invocation fetches under its own identity."""

        async def run() -> None:
            await self._make_tool().get_external_networks()
            await self._make_tool().get_external_networks()

        with self._patched_names(), mock.patch.dict(os.environ, {"AGENT_AUTHORIZER": "some.authorizer.Class"}):
            asyncio.run(run())

        # Two invocations, two full fan-outs — /function responses are
        # caller-specific under an authorizer, so nothing may be shared...
        self.assertEqual(sorted(self.fetch_log), sorted(EXTERNAL_NETWORK_NAMES * 2))
        # ...and nothing was left behind in the shared cache.
        # pylint: disable-next=protected-access
        cache: SharedProcessCache[dict[str, str]] = GetExternalNetwork._shared_external_network_descriptions_cache
        self.assertIsNone(cache.peek())
