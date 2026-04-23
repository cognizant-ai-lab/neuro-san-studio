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

from middleware.persistent_memory.json_file_store import JsonFileStore
from middleware.persistent_memory.persistent_memory_middleware import PersistentMemoryMiddleware
from middleware.persistent_memory.persistent_memory_tool import PersistentMemoryTool
from middleware.persistent_memory.topic_store import TopicStore
from tests.middleware.persistent_memory.should_summarize import ShouldSummarize


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
        summarizer: Optional[Any] = None,
        max_topic_size: Optional[int] = None,
    ) -> PersistentMemoryTool:
        """Construct a ``PersistentMemoryTool`` wired to the test namespace.

        :param enabled_operations: Optional whitelist of operations.
        :param store:              Optional pre-built store (default: JSON
                                   store rooted in the scratch directory).
        :param summarizer:         Optional summarizer to attach.
        :param max_topic_size:     When supplied with ``summarizer``, wires
                                   a ``should_summarize`` predicate onto
                                   the summarizer that returns ``True``
                                   when ``len(content) > max_topic_size``
                                   and ``max_topic_size > 0``.
        :return:                   A ready-to-use tool.
        """
        resolved_store: TopicStore = store if store is not None else JsonFileStore(root_path=self._tmp)
        if summarizer is not None and max_topic_size is not None:
            summarizer.should_summarize = self._make_should_summarize(max_topic_size)
        return PersistentMemoryTool(
            tool_config={
                "namespace_key": "test_net.test_agent",
                "enabled_operations": enabled_operations,
            },
            store=resolved_store,
            summarizer=summarizer,
        )

    def _make_should_summarize(self, max_topic_size: int) -> ShouldSummarize:
        """Return a ``should_summarize`` predicate matching ``TopicSummarizer``.

        :param max_topic_size: Threshold length; ``<= 0`` disables summarization.
        :return:               Callable-object wrapping the threshold.
        """
        del self
        return ShouldSummarize(max_topic_size)

    def make_middleware(
        self,
        backend: str = "json_file",
        enabled_operations: Optional[list[str]] = None,
        max_topic_size: int = 1000,
    ) -> PersistentMemoryMiddleware:
        """Construct a middleware wired to a scratch root.

        :param backend:            Backend id (``json_file`` or ``markdown_file``).
        :param enabled_operations: Optional whitelist of operations.
        :param max_topic_size:     Summarizer trigger threshold.
        :return:                   A ready-to-use middleware.
        """
        return PersistentMemoryMiddleware(
            origin_str="test_net.test_agent-1.dispatch",
            memory_config={
                "storage": {"backend": backend, "root_path": self._tmp},
                "summarization": {"max_topic_size": max_topic_size},
                "enabled_operations": enabled_operations,
            },
        )
