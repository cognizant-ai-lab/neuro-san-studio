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

import asyncio
import os
import shutil
import tempfile
from unittest import TestCase
from unittest.mock import patch

from coded_tools.tools.persistent_memory.persistent_memory_tool import PersistentMemoryTool


def _clean_env_dict() -> dict[str, str]:
    """Strip MEMORY_* env vars so test host env cannot alter tool behaviour."""
    return {k: v for k, v in os.environ.items() if not k.startswith("MEMORY_")}


def _make_tool(root_path: str, enabled_operations=None) -> PersistentMemoryTool:
    """Build a tool backed by the file_system store under an isolated tmpdir."""
    return PersistentMemoryTool(
        tool_config={
            "agent_network_name": "test_net",
            "agent_name":         "test_agent",
            "store_config":       {"backend": "file_system", "root_path": root_path},
            "enabled_operations": enabled_operations,
        }
    )


class TestPersistentMemoryToolDispatch(TestCase):
    """The six operations, their required fields, and error envelopes."""

    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, _clean_env_dict(), clear=True)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        self.tool = _make_tool(root_path=self._tmp)
        self.sly_data = {"user_id": "alice"}

    def _invoke(self, args: dict) -> dict:
        return asyncio.run(self.tool.async_invoke(args, self.sly_data))

    def test_create_auto_generates_key_when_omitted(self):
        """create without 'key' returns a generated key; create with 'content' only is the common path."""
        result = self._invoke({"operation": "create", "content": "likes dark coffee"})
        self.assertIn("result", result)
        self.assertEqual(result["result"]["status"], "created")
        self.assertTrue(result["result"]["key"])

    def test_create_missing_content_returns_error(self):
        """create without 'content' is a user error, not an exception."""
        result = self._invoke({"operation": "create"})
        self.assertIn("error", result)
        self.assertIn("content", result["error"])

    def test_read_returns_created_entry(self):
        """A key produced by create is readable via read."""
        created = self._invoke({"operation": "create", "key": "k1", "content": "v1"})
        self.assertEqual(created["result"]["key"], "k1")

        read = self._invoke({"operation": "read", "key": "k1"})
        self.assertEqual(read["result"]["content"], "v1")

    def test_read_missing_key_returns_error(self):
        """read on a non-existent key returns an error envelope, not a crash."""
        result = self._invoke({"operation": "read", "key": "missing"})
        self.assertIn("error", result)

    def test_update_overwrites(self):
        """update changes the stored content under the same key."""
        self._invoke({"operation": "create", "key": "k1", "content": "v1"})
        self._invoke({"operation": "update", "key": "k1", "content": "v2"})
        read = self._invoke({"operation": "read", "key": "k1"})
        self.assertEqual(read["result"]["content"], "v2")

    def test_append_concatenates_content(self):
        """append preserves old content and adds the new content separated by a blank line."""
        self._invoke({"operation": "create", "key": "k1", "content": "ordered matcha"})
        self._invoke({"operation": "append", "key": "k1", "content": "ordered black coffee"})
        read = self._invoke({"operation": "read", "key": "k1"})
        self.assertIn("ordered matcha", read["result"]["content"])
        self.assertIn("ordered black coffee", read["result"]["content"])

    def test_append_on_missing_key_creates_it(self):
        """append on a non-existent key behaves like create."""
        result = self._invoke({"operation": "append", "key": "new_key", "content": "first entry"})
        self.assertEqual(result["result"]["status"], "appended")
        read = self._invoke({"operation": "read", "key": "new_key"})
        self.assertEqual(read["result"]["content"], "first entry")

    def test_delete_removes_entry(self):
        """After delete, read returns an error for the same key."""
        self._invoke({"operation": "create", "key": "k1", "content": "v"})
        self._invoke({"operation": "delete", "key": "k1"})
        result = self._invoke({"operation": "read", "key": "k1"})
        self.assertIn("error", result)

    def test_search_returns_matches(self):
        """search returns ranked entries whose content contains query terms."""
        self._invoke({"operation": "create", "key": "k1", "content": "loves coffee"})
        self._invoke({"operation": "create", "key": "k2", "content": "loves tea"})
        result = self._invoke({"operation": "search", "query": "coffee"})
        keys = [r["key"] for r in result["result"]["results"]]
        self.assertIn("k1", keys)
        self.assertNotIn("k2", keys)

    def test_list_returns_all_keys(self):
        """list enumerates every key in the topic's namespace."""
        self._invoke({"operation": "create", "key": "a", "content": "v"})
        self._invoke({"operation": "create", "key": "b", "content": "v"})
        result = self._invoke({"operation": "list"})
        self.assertCountEqual(result["result"]["keys"], ["a", "b"])

    def test_unknown_operation_returns_error(self):
        """Operations outside ALL_OPERATIONS surface a readable error."""
        result = self._invoke({"operation": "explode"})
        self.assertIn("error", result)

class TestPersistentMemoryToolEnabledOperations(TestCase):
    """``enabled_operations`` locks down what the LLM can do."""

    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, _clean_env_dict(), clear=True)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_disabled_operation_returns_error(self):
        """An enabled-op check runs before any store access."""
        tool = _make_tool(root_path=self._tmp, enabled_operations=["read", "search"])
        result = asyncio.run(
            tool.async_invoke({"operation": "create", "content": "v"}, {"user_id": "alice"})
        )
        self.assertIn("error", result)
        self.assertIn("not enabled", result["error"].lower())


class TestPersistentMemoryToolUserScoping(TestCase):
    """``sly_data['user_id']`` drives the topic component of the namespace."""

    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, _clean_env_dict(), clear=True)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

    def test_different_users_have_isolated_memory(self):
        """Alice's create is not visible to Bob's read."""
        tool = _make_tool(root_path=self._tmp)
        asyncio.run(
            tool.async_invoke({"operation": "create", "key": "k1", "content": "alice"}, {"user_id": "alice"})
        )
        result = asyncio.run(
            tool.async_invoke({"operation": "read", "key": "k1"}, {"user_id": "bob"})
        )
        self.assertIn("error", result)
