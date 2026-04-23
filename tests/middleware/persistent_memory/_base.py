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

"""Shared ``TestCase`` base for persistent-memory tests."""

from __future__ import annotations

import shutil
import tempfile
from typing import Any
from typing import Optional
from unittest import TestCase

from middleware.persistent_memory.coded_tool import PersistentMemoryTool
from middleware.persistent_memory.json_file_store import JsonFileStore
from middleware.persistent_memory.middleware import PersistentMemoryMiddleware
from middleware.persistent_memory.topic_store import TopicStore


class _ShouldSummarise:  # pylint: disable=too-few-public-methods
    """Callable wrapping the ``max_topic_size`` threshold used in tests.

    Mirrors :py:meth:`TopicSummariser.should_summarise` so mocks can be
    swapped in without recreating the threshold logic in every test.
    """

    def __init__(self, threshold: int) -> None:
        self._threshold: int = threshold

    def __call__(self, content: str) -> bool:
        """Return ``True`` when ``content`` exceeds the configured threshold."""
        return self._threshold > 0 and len(content) > self._threshold


class MemoryTestBase(TestCase):
    """Provide a tmpdir per test, torn down automatically."""

    def setUp(self) -> None:
        """Create a scratch directory for the test."""
        super().setUp()
        self._tmp: str = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def make_tool(
        self,
        enabled_operations: Optional[list[str]] = None,
        store: Optional[TopicStore] = None,
        summariser: Optional[Any] = None,
        max_topic_size: Optional[int] = None,
    ) -> PersistentMemoryTool:
        """Construct a ``PersistentMemoryTool`` wired to the test namespace.

        :param enabled_operations: Optional whitelist of operations.
        :param store:              Optional pre-built store (default: JSON
                                   store rooted in the scratch directory).
        :param summariser:         Optional summariser to attach.
        :param max_topic_size:     When supplied with ``summariser``, wires
                                   a ``should_summarise`` predicate onto
                                   the summariser that returns ``True``
                                   when ``len(content) > max_topic_size``
                                   and ``max_topic_size > 0``.
        :return:                   A ready-to-use tool.
        """
        resolved_store: TopicStore = store if store is not None else JsonFileStore(root_path=self._tmp)
        if summariser is not None and max_topic_size is not None:
            summariser.should_summarise = self._make_should_summarise(max_topic_size)
        return PersistentMemoryTool(
            tool_config={
                "namespace_key": "test_net.test_agent",
                "enabled_operations": enabled_operations,
            },
            store=resolved_store,
            summariser=summariser,
        )

    def _make_should_summarise(self, max_topic_size: int) -> "_ShouldSummarise":
        """Return a ``should_summarise`` predicate matching ``TopicSummariser``.

        :param max_topic_size: Threshold length; ``<= 0`` disables summarisation.
        :return:               Callable-object wrapping the threshold.
        """
        del self
        return _ShouldSummarise(max_topic_size)

    def make_middleware(
        self,
        backend: str = "json_file",
        enabled_operations: Optional[list[str]] = None,
        max_topic_size: int = 1000,
    ) -> PersistentMemoryMiddleware:
        """Construct a middleware wired to a scratch root.

        :param backend:            Backend id (``json_file`` or ``markdown_file``).
        :param enabled_operations: Optional whitelist of operations.
        :param max_topic_size:     Summariser trigger threshold.
        :return:                   A ready-to-use middleware.
        """
        return PersistentMemoryMiddleware(
            origin_str="test_net.test_agent-1.dispatch",
            memory_config={
                "storage": {"backend": backend, "root_path": self._tmp},
                "summarisation": {"max_topic_size": max_topic_size},
                "enabled_operations": enabled_operations,
            },
        )
