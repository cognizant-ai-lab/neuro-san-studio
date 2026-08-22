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
Tests for SharedProcessCache.

Deliberately stdlib-only (no neuro-san imports): the cache is the shared
concurrency mechanism under every process-wide cache in the Agent Network
Designer family, so these tests must run in any environment that can
collect the suite. Async cases drive their own event loops via asyncio.run()
rather than depending on an asyncio pytest plugin.
"""

import asyncio
import tempfile
import threading
import time
from unittest import TestCase

from coded_tools.agent_network_editor.shared_process_cache import SharedProcessCache


class TestSharedProcessCache(TestCase):
    """Behavioral and regression tests for the shared cache mechanism."""

    def test_get_loads_once_and_peek_reflects_state(self):
        """Loader runs once; peek() mirrors loaded/unloaded state."""
        calls: list[int] = []

        def loader() -> str:
            calls.append(1)
            return "value"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader)
        self.assertIsNone(cache.peek())
        self.assertEqual(cache.get(), "value")
        self.assertEqual(cache.get(), "value")
        self.assertEqual(cache.peek(), "value")
        self.assertEqual(len(calls), 1)

    def test_loader_failure_publishes_nothing_and_next_call_retries(self):
        """A raising loader publishes nothing, so the next get() retries."""
        attempts = {"count": 0}

        def loader() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("boom")
            return "healed"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader)
        with self.assertRaises(RuntimeError):
            cache.get()
        self.assertIsNone(cache.peek())
        self.assertEqual(cache.get(), "healed")
        self.assertEqual(attempts["count"], 2)

    def test_fingerprint_controls_freshness(self):
        """A fingerprint change turns warm reads into a miss and reload."""
        source = {"fingerprint": 1, "loads": 0}

        def loader() -> str:
            source["loads"] += 1
            return f"value-{source['fingerprint']}"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader, fingerprint=lambda: source["fingerprint"])
        self.assertEqual(cache.get(), "value-1")
        self.assertEqual(cache.get(), "value-1")
        self.assertEqual(source["loads"], 1)

        # The source moved on: peek() reports a miss and get() rebuilds.
        source["fingerprint"] = 2
        self.assertIsNone(cache.peek())
        self.assertEqual(cache.get(), "value-2")
        self.assertEqual(source["loads"], 2)

    def test_fingerprint_is_captured_before_the_loader_runs(self):
        """A mid-load source change leaves the published entry stale."""
        # If the source changes while the loader runs, the published entry must
        # already be stale so the next read rebuilds it instead of a torn value
        # living forever.
        source = {"fingerprint": 1}

        def loader() -> str:
            source["fingerprint"] = 2
            return "torn"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader, fingerprint=lambda: source["fingerprint"])
        self.assertEqual(cache.get(), "torn")
        self.assertIsNone(cache.peek())

    def test_aget_shares_one_load_across_concurrent_cold_callers(self):
        """Concurrent cold aget() callers share a single loader run."""
        calls = {"count": 0}

        def loader() -> str:
            calls["count"] += 1
            time.sleep(0.05)
            return "shared"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader)

        async def run() -> list[str]:
            return await asyncio.gather(*[cache.aget() for _ in range(20)])

        self.assertEqual(asyncio.run(run()), ["shared"] * 20)
        self.assertEqual(calls["count"], 1)

    def test_aget_load_survives_one_awaiter_being_cancelled(self):
        """Cancelling one aget() awaiter must not cancel the shared load."""
        # Regression test for the unshielded await: cancelling one awaiter must
        # not cancel the shared load out from under the other awaiters.
        loader_started = threading.Event()
        release_loader = threading.Event()

        def loader() -> str:
            loader_started.set()
            release_loader.wait(timeout=5)
            return "survived"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader)

        async def run() -> str:
            first = asyncio.create_task(cache.aget())
            second = asyncio.create_task(cache.aget())
            await asyncio.to_thread(loader_started.wait, 5)
            first.cancel()
            release_loader.set()
            with self.assertRaises(asyncio.CancelledError):
                await first
            return await second

        self.assertEqual(asyncio.run(run()), "survived")

    def test_aget_failure_is_shared_and_next_call_retries(self):
        """A failing shared load raises for all awaiters; next aget() retries."""
        attempts = {"count": 0}

        def loader() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("boom")
            return "healed"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader)

        async def run() -> str:
            results = await asyncio.gather(*[cache.aget() for _ in range(3)], return_exceptions=True)
            self.assertTrue(all(isinstance(result, RuntimeError) for result in results))
            return await cache.aget()

        self.assertEqual(asyncio.run(run()), "healed")
        self.assertEqual(attempts["count"], 2)

    def test_aget_cleans_up_in_flight_bookkeeping_across_event_loops(self):
        """The once-gate map must not pin dead event loops (leak regression)."""
        # Regression test for the once-gate leak: a Task strongly references the
        # event loop it runs on (its own dictionary key), so without the done
        # callback the weak keying never reclaims entries and one loop + task
        # would be pinned per event loop that ever cold-loaded.
        cache: SharedProcessCache[str] = SharedProcessCache(loader=lambda: "value")
        for _ in range(5):
            cache.clear_for_testing()
            self.assertEqual(asyncio.run(cache.aget()), "value")
        self.assertEqual(len(cache._loads_in_flight), 0)  # pylint: disable=protected-access

    def test_get_raises_on_a_miss_without_a_loader(self):
        """A loaderless cache raises on a get() miss but serves warm reads."""

        async def filler() -> str:
            return "filled"

        cache: SharedProcessCache[str] = SharedProcessCache()
        with self.assertRaises(RuntimeError):
            cache.get()
        self.assertEqual(asyncio.run(cache.aget_or_fill(filler)), "filled")
        self.assertEqual(cache.get(), "filled")

    def test_aget_raises_on_a_miss_without_a_loader(self):
        """aget() rejects a loaderless miss without seeding the once-gate."""
        cache: SharedProcessCache[str] = SharedProcessCache()

        async def filler() -> str:
            return "filled"

        async def run() -> str:
            with self.assertRaises(RuntimeError):
                await cache.aget()
            # The rejected aget() must not have left a doomed task behind
            # for aget_or_fill() to adopt.
            return await cache.aget_or_fill(filler)

        self.assertEqual(asyncio.run(run()), "filled")

    def test_aget_or_fill_raises_when_a_loader_is_configured(self):
        """aget_or_fill() rejects a miss on a loader-backed cache."""
        cache: SharedProcessCache[str] = SharedProcessCache(loader=lambda: "loaded")

        async def filler() -> str:
            return "filled"

        async def run() -> None:
            with self.assertRaises(RuntimeError):
                await cache.aget_or_fill(filler)

        asyncio.run(run())
        # The loader path is unaffected by the rejected call.
        self.assertEqual(cache.get(), "loaded")

    def test_aget_or_fill_does_not_clobber_a_fresher_entry(self):
        """A fill whose capture went stale must not overwrite a racer's fresher entry."""
        source = {"fingerprint": 1}
        cache: SharedProcessCache[str] = SharedProcessCache(fingerprint=lambda: source["fingerprint"])

        async def slow_filler() -> str:
            # Stand-in for a faster fill on ANOTHER event loop finishing
            # first: the source rolls mid-build and the racer publishes a
            # value that is current under the new fingerprint.
            source["fingerprint"] = 2
            cache._entry = ("fresh", 2)  # pylint: disable=protected-access
            return "stale"

        # This fill's own awaiter still receives its value...
        self.assertEqual(asyncio.run(cache.aget_or_fill(slow_filler)), "stale")
        # ...but the racer's fresher entry survives the publish.
        self.assertEqual(cache.peek(), "fresh")

    def test_aget_or_fill_shares_one_fill_and_serves_warm_reads(self):
        """Concurrent cold aget_or_fill() callers share a single filler run."""
        calls = {"count": 0}

        async def filler() -> str:
            calls["count"] += 1
            await asyncio.sleep(0.05)
            return "filled"

        cache: SharedProcessCache[str] = SharedProcessCache()

        async def run() -> list[str]:
            burst = await asyncio.gather(*[cache.aget_or_fill(filler) for _ in range(20)])
            warm = await cache.aget_or_fill(filler)
            return burst + [warm]

        self.assertEqual(asyncio.run(run()), ["filled"] * 21)
        self.assertEqual(calls["count"], 1)

    def test_aget_or_fill_failure_is_shared_and_next_call_retries(self):
        """A failing shared fill raises for all awaiters; the next call retries."""
        attempts = {"count": 0}

        async def filler() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("boom")
            return "healed"

        cache: SharedProcessCache[str] = SharedProcessCache()

        async def run() -> str:
            results = await asyncio.gather(*[cache.aget_or_fill(filler) for _ in range(3)], return_exceptions=True)
            self.assertTrue(all(isinstance(result, RuntimeError) for result in results))
            # Nothing was published, so the failure is not served warm.
            self.assertIsNone(cache.peek())
            return await cache.aget_or_fill(filler)

        self.assertEqual(asyncio.run(run()), "healed")
        self.assertEqual(attempts["count"], 2)

    def test_aget_or_fill_respects_fingerprint_freshness(self):
        """A fingerprint change turns warm aget_or_fill() reads into a refill."""
        source = {"fingerprint": 1, "fills": 0}

        async def filler() -> str:
            source["fills"] += 1
            return f"value-{source['fingerprint']}"

        cache: SharedProcessCache[str] = SharedProcessCache(fingerprint=lambda: source["fingerprint"])

        async def run() -> tuple[str, str, str]:
            first = await cache.aget_or_fill(filler)
            second = await cache.aget_or_fill(filler)
            source["fingerprint"] = 2
            third = await cache.aget_or_fill(filler)
            return first, second, third

        self.assertEqual(asyncio.run(run()), ("value-1", "value-1", "value-2"))
        self.assertEqual(source["fills"], 2)

    def test_aget_or_fill_captures_fingerprint_before_the_filler_runs(self):
        """A mid-fill source change leaves the published entry stale."""
        # The async twin of test_fingerprint_is_captured_before_the_loader_runs:
        # if the source changes while the filler runs, the published entry must
        # already be stale so the next read rebuilds it.
        source = {"fingerprint": 1}

        async def filler() -> str:
            source["fingerprint"] = 2
            return "torn"

        cache: SharedProcessCache[str] = SharedProcessCache(fingerprint=lambda: source["fingerprint"])
        self.assertEqual(asyncio.run(cache.aget_or_fill(filler)), "torn")
        self.assertIsNone(cache.peek())

    def test_aget_or_fill_survives_one_awaiter_being_cancelled(self):
        """Cancelling one aget_or_fill() awaiter must not cancel the shared fill."""
        calls = {"count": 0}

        async def run() -> str:
            release = asyncio.Event()

            async def filler() -> str:
                calls["count"] += 1
                await release.wait()
                return "survived"

            cache: SharedProcessCache[str] = SharedProcessCache()
            first = asyncio.create_task(cache.aget_or_fill(filler))
            second = asyncio.create_task(cache.aget_or_fill(filler))
            # One tick so both awaiters reach the shared fill task.
            await asyncio.sleep(0)
            first.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await first
            return await second

        self.assertEqual(asyncio.run(run()), "survived")
        self.assertEqual(calls["count"], 1)

    def test_clear_for_testing_drops_entry_and_pending_loads(self):
        """clear_for_testing() drops the entry AND forgets pending loads."""
        calls = {"count": 0}

        def loader() -> str:
            calls["count"] += 1
            return f"load-{calls['count']}"

        cache: SharedProcessCache[str] = SharedProcessCache(loader=loader)
        self.assertEqual(cache.get(), "load-1")

        async def run() -> str:
            loop = asyncio.get_running_loop()
            # Stand-in for a load still in flight when the clear happens: if
            # clear_for_testing() left it behind, aget() would adopt it (it is
            # not done) and time out below instead of starting a fresh load.
            pending = loop.create_task(asyncio.sleep(60))
            cache._loads_in_flight[loop] = pending  # pylint: disable=protected-access
            cache.clear_for_testing()
            self.assertIsNone(cache.peek())
            value = await asyncio.wait_for(cache.aget(), timeout=5)
            pending.cancel()
            return value

        self.assertEqual(asyncio.run(run()), "load-2")

    def test_stat_modification_time_ns_probes_without_raising(self):
        """The modification_time building block reports a bad path as None, per the fingerprint contract."""
        self.assertIsNone(SharedProcessCache.stat_modification_time_ns("/nonexistent/definitely/not/here"))
        with tempfile.NamedTemporaryFile() as probe:
            self.assertIsInstance(SharedProcessCache.stat_modification_time_ns(probe.name), int)

    def test_time_bucket_rolls_with_the_period_and_freezes_otherwise(self):
        """Positive periods roll once per period; zero, negative, and non-finite pin bucket 0."""
        for frozen_period in (0.0, -5.0, float("nan"), float("inf")):
            self.assertEqual(SharedProcessCache.time_bucket(frozen_period), 0)
        before = SharedProcessCache.time_bucket(0.01)
        time.sleep(0.03)
        self.assertGreater(SharedProcessCache.time_bucket(0.01), before)
