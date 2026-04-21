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
Shared ``TestCase`` base for persistent-memory tests.

Centralises the two fixtures that every test module needs:

    * An ``os.environ`` snapshot with all ``MEMORY_*`` vars stripped, so host
      environment values (a developer's ``MEMORY_BACKEND`` export, CI secrets)
      cannot leak into assertions.
    * A ``tempfile.mkdtemp`` directory that is torn down on test exit.

Subclasses get the env patch + tmpdir set up automatically in ``setUp``; they
can also call :py:meth:`clean_env_dict` directly when a test needs to build
its own ``patch.dict`` context.
"""

import os
import shutil
import tempfile
from typing import Any
from typing import Optional
from unittest import TestCase
from unittest.mock import patch

from middleware.persistent_memory import PersistentMemoryMiddleware

from coded_tools.tools.persistent_memory.persistent_memory_tool import PersistentMemoryTool


class MemoryTestBase(TestCase):
    """Shared fixtures for every test module in this package.

    Every subclass gets ``self._tmp`` (a scratch directory) and a clean
    ``MEMORY_*`` environment for the duration of the test.
    """

    def setUp(self) -> None:
        """Install the env patch + tmpdir. Subclass ``setUp`` may extend this."""
        super().setUp()
        self._env_patch = patch.dict(os.environ, self.clean_env_dict(), clear=True)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)
        self._tmp: str = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    @staticmethod
    def clean_env_dict() -> dict[str, str]:
        """Return an ``os.environ`` copy with every ``MEMORY_*`` var stripped.

        :return: Env dict safe to feed to ``patch.dict(..., clear=True)``.
        """
        return {k: v for k, v in os.environ.items() if not k.startswith("MEMORY_")}

    def make_tool(
        self,
        root_path: Optional[str] = None,
        enabled_operations: Optional[list[str]] = None,
    ) -> PersistentMemoryTool:
        """Build a tool backed by the markdown_file store under an isolated tmpdir.

        :param root_path: Directory to pass to the backend; defaults to
                          ``self._tmp``.
        :param enabled_operations: Optional whitelist restricting the tool's
                                   operations.
        :return: A fully-constructed ``PersistentMemoryTool``.
        """
        return PersistentMemoryTool(
            tool_config={
                "agent_network_name": "test_net",
                "agent_name": "test_agent",
                "store_config": {"backend": "markdown_file", "root_path": root_path or self._tmp},
                "enabled_operations": enabled_operations,
            }
        )

    def make_middleware(
        self,
        root_path: Optional[str] = None,
        sly_data: Optional[dict[str, Any]] = None,
        enabled_operations: Optional[list[str]] = None,
    ) -> PersistentMemoryMiddleware:
        """Build a middleware on the markdown_file backend under an isolated tmpdir.

        :param root_path: Directory to pass to the backend; defaults to
                          ``self._tmp``.
        :param sly_data: Optional sly_data override; defaults to ``{"user_id": "alice"}``.
        :param enabled_operations: Optional whitelist restricting the tool's
                                   operations.
        :return: A fully-constructed ``PersistentMemoryMiddleware``.
        """
        return PersistentMemoryMiddleware(
            agent_network_name="test_net",
            agent_name="test_agent",
            store_config={"backend": "markdown_file", "root_path": root_path or self._tmp},
            enabled_operations=enabled_operations,
            sly_data=sly_data or {"user_id": "alice"},
        )
