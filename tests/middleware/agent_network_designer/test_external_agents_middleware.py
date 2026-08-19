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

"""Tests for ExternalAgentsMiddleware: env-var gating, fail-closed catalog loading,
process-wide caching, and execution-time tool-call denial."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage

from middleware.agent_network_designer.external_agents_middleware import ExternalAgentsMiddleware

# The env var each test catalog's single module is toggled by.
TOGGLE_ENV_VAR = "TEST_USE_MIDDLEWARE_MODULE"
# Safe name the designer's executor exposes for the catalog's "/middleware_manager" ref.
SAFE_TOOL_NAME = "__middleware_manager"


class _FakeModelRequest:  # pylint: disable=too-few-public-methods
    """Just enough of langchain's ModelRequest for awrap_model_call: tools,
    system_message, and an override() that returns a modified copy."""

    def __init__(self, tools: list[Any], system_message: SystemMessage | None = None):
        self.tools = tools
        self.system_message = system_message

    def override(self, **kwargs) -> "_FakeModelRequest":
        """Mirror ModelRequest.override(): a copy with the given fields replaced."""
        return _FakeModelRequest(kwargs.get("tools", self.tools), kwargs.get("system_message", self.system_message))


class _FakeToolCallRequest:  # pylint: disable=too-few-public-methods
    """Just enough of langchain's ToolCallRequest for awrap_tool_call: the tool_call dict."""

    def __init__(self, name: str, call_id: str | None = "call_1"):
        self.tool_call: dict[str, Any] = {"name": name, "args": {}, "id": call_id}


class TestExternalAgentsMiddleware:
    """Tests for ExternalAgentsMiddleware."""

    @staticmethod
    def _write_catalog(tmp_path: Path, catalog: dict[str, Any], name: str = "external_agents.hocon") -> Path:
        """Write a catalog file (JSON is valid HOCON) and return its path."""
        catalog_file = tmp_path / name
        catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
        return catalog_file

    @staticmethod
    def _standard_catalog() -> dict[str, Any]:
        """One well-formed module toggled by TOGGLE_ENV_VAR."""
        return {
            "middleware_manager": {
                "enabled_env_var": TOGGLE_ENV_VAR,
                "tool": "/middleware_manager",
                "instructions": "Step 3) Call /middleware_manager to attach middleware.",
            }
        }

    def _install_catalog(self, tmp_path: Path, monkeypatch, catalog: dict[str, Any] | None = None) -> Path:
        """Write a catalog and point EXTERNAL_AGENTS_FILE at it."""
        catalog_file = self._write_catalog(tmp_path, catalog if catalog is not None else self._standard_catalog())
        monkeypatch.setenv("EXTERNAL_AGENTS_FILE", str(catalog_file))
        return catalog_file

    @staticmethod
    def _request_tools() -> list[dict[str, str]]:
        return [{"name": SAFE_TOOL_NAME}, {"name": "other_tool"}]

    # ------------------------------------------------------------------
    # awrap_model_call: gating
    # ------------------------------------------------------------------

    def test_disabled_module_tool_stripped_from_model_request(self, tmp_path, monkeypatch):
        """Toggle off: the module's safe tool name is removed from the request's tools."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")
        request = _FakeModelRequest(tools=self._request_tools(), system_message=SystemMessage(content="base"))

        result = asyncio.run(ExternalAgentsMiddleware(sly_data={}).awrap_model_call(request, handler))

        assert result == "model-response"
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]
        # No instructions were injected for a disabled module.
        assert seen_request.system_message.content == "base"

    def test_enabled_module_injects_instructions_and_keeps_tool(self, tmp_path, monkeypatch):
        """Toggle on: instructions are appended to the system prompt and the tool stays."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.setenv(TOGGLE_ENV_VAR, "true")
        handler = AsyncMock(return_value="model-response")
        request = _FakeModelRequest(tools=self._request_tools(), system_message=SystemMessage(content="base"))

        asyncio.run(ExternalAgentsMiddleware(sly_data={}).awrap_model_call(request, handler))

        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == [SAFE_TOOL_NAME, "other_tool"]
        assert seen_request.system_message.content.startswith("base")
        assert "Call /middleware_manager" in seen_request.system_message.content

    def test_falsy_toggle_values_disable(self, tmp_path, monkeypatch):
        """Explicit 'false' (and other non-truthy strings) disable the module."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.setenv(TOGGLE_ENV_VAR, "false")
        handler = AsyncMock(return_value="model-response")
        request = _FakeModelRequest(tools=self._request_tools())

        asyncio.run(ExternalAgentsMiddleware(sly_data={}).awrap_model_call(request, handler))

        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

    def test_non_dict_catalog_entry_skipped_with_warning(self, tmp_path, monkeypatch, caplog):
        """A scalar top-level catalog entry is skipped, not an AttributeError per call."""
        catalog = {"version": "1", **self._standard_catalog()}
        self._install_catalog(tmp_path, monkeypatch, catalog)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")
        request = _FakeModelRequest(tools=self._request_tools())

        with caplog.at_level("WARNING"):
            asyncio.run(ExternalAgentsMiddleware(sly_data={}).awrap_model_call(request, handler))

        assert "not a mapping" in caplog.text
        # The well-formed module was still processed.
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

    # ------------------------------------------------------------------
    # awrap_model_call: fail-closed catalog loading
    # ------------------------------------------------------------------

    def test_missing_catalog_fails_closed(self, tmp_path, monkeypatch):
        """A missing catalog file refuses the model call instead of leaving tools intact."""
        monkeypatch.setenv("EXTERNAL_AGENTS_FILE", str(tmp_path / "nope.hocon"))
        handler = AsyncMock()

        with pytest.raises(ValueError, match="could not be loaded"):
            asyncio.run(ExternalAgentsMiddleware(sly_data={}).awrap_model_call(_FakeModelRequest(tools=[]), handler))

        handler.assert_not_awaited()

    def test_empty_env_var_fails_closed(self, monkeypatch):
        """EXTERNAL_AGENTS_FILE="" (the docker-compose/k8s 'unset' idiom) must not
        silently publish an empty catalog and turn the gate off."""
        monkeypatch.setenv("EXTERNAL_AGENTS_FILE", "")
        handler = AsyncMock()

        with pytest.raises(ValueError, match="empty string"):
            asyncio.run(ExternalAgentsMiddleware(sly_data={}).awrap_model_call(_FakeModelRequest(tools=[]), handler))

        handler.assert_not_awaited()

    def test_corrupt_catalog_fails_closed_then_recovers_after_fix(self, tmp_path, monkeypatch):
        """A corrupt catalog raises; fixing the file recovers without a process restart."""
        catalog_file = tmp_path / "external_agents.hocon"
        catalog_file.write_text("{ this is : : not valid hocon }}", encoding="utf-8")
        monkeypatch.setenv("EXTERNAL_AGENTS_FILE", str(catalog_file))
        handler = AsyncMock(return_value="model-response")
        middleware = ExternalAgentsMiddleware(sly_data={})

        with pytest.raises(ValueError, match="could not be loaded"):
            asyncio.run(middleware.awrap_model_call(_FakeModelRequest(tools=[]), handler))

        # Fix the file in place; a failed load is never published, so the next call reloads.
        catalog_file.write_text(json.dumps(self._standard_catalog()), encoding="utf-8")
        result = asyncio.run(middleware.awrap_model_call(_FakeModelRequest(tools=self._request_tools()), handler))
        assert result == "model-response"

    # ------------------------------------------------------------------
    # awrap_tool_call: execution-time enforcement
    # ------------------------------------------------------------------

    def test_tool_call_denied_when_module_disabled(self, tmp_path, monkeypatch):
        """A tool call naming a disabled module tool is denied, not executed."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock()

        result = asyncio.run(
            ExternalAgentsMiddleware(sly_data={}).awrap_tool_call(_FakeToolCallRequest(SAFE_TOOL_NAME), handler)
        )

        handler.assert_not_awaited()
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert result.tool_call_id == "call_1"
        assert "disabled" in result.content

    def test_tool_call_denied_without_call_id(self, tmp_path, monkeypatch):
        """Providers may omit tool call ids; the denial still carries a string id."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)

        result = asyncio.run(
            ExternalAgentsMiddleware(sly_data={}).awrap_tool_call(
                _FakeToolCallRequest(SAFE_TOOL_NAME, call_id=None), AsyncMock()
            )
        )

        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "unknown"

    def test_tool_call_allowed_when_module_enabled(self, tmp_path, monkeypatch):
        """With the toggle on, the module's tool call goes through to the handler."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.setenv(TOGGLE_ENV_VAR, "1")
        handler = AsyncMock(return_value="tool-result")

        result = asyncio.run(
            ExternalAgentsMiddleware(sly_data={}).awrap_tool_call(_FakeToolCallRequest(SAFE_TOOL_NAME), handler)
        )

        handler.assert_awaited_once()
        assert result == "tool-result"

    def test_tool_call_for_unmanaged_tool_allowed(self, tmp_path, monkeypatch):
        """Tools outside the catalog are never blocked, whatever the toggles say."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="tool-result")

        result = asyncio.run(
            ExternalAgentsMiddleware(sly_data={}).awrap_tool_call(_FakeToolCallRequest("other_tool"), handler)
        )

        handler.assert_awaited_once()
        assert result == "tool-result"

    def test_tool_call_fails_closed_on_missing_catalog(self, tmp_path, monkeypatch):
        """The execution-time gate fails closed too: no catalog, no tool execution."""
        monkeypatch.setenv("EXTERNAL_AGENTS_FILE", str(tmp_path / "nope.hocon"))
        handler = AsyncMock()

        with pytest.raises(ValueError, match="could not be loaded"):
            asyncio.run(
                ExternalAgentsMiddleware(sly_data={}).awrap_tool_call(_FakeToolCallRequest(SAFE_TOOL_NAME), handler)
            )

        handler.assert_not_awaited()

    # ------------------------------------------------------------------
    # Process-wide caching
    # ------------------------------------------------------------------

    def test_catalog_loaded_once_across_instances(self, tmp_path, monkeypatch):
        """Two instances (two 'sessions') share one parse of the catalog file."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")

        real_restore = ExternalAgentsMiddleware._load_external_agents_catalog  # pylint: disable=protected-access
        with patch.object(
            ExternalAgentsMiddleware, "_load_external_agents_catalog", side_effect=real_restore
        ) as load_spy:
            # Re-point the cache's loader at the spy for this test only.
            with patch.object(
                ExternalAgentsMiddleware._shared_catalog_cache,  # pylint: disable=protected-access
                "_loader",
                load_spy,
            ):
                for _ in range(2):
                    request = _FakeModelRequest(tools=self._request_tools())
                    asyncio.run(ExternalAgentsMiddleware(sly_data={}).awrap_model_call(request, handler))

        assert load_spy.call_count == 1

    def test_catalog_edit_is_picked_up_via_fingerprint(self, tmp_path, monkeypatch):
        """Editing the catalog file is visible on the next call, no restart needed."""
        catalog_file = self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")
        middleware = ExternalAgentsMiddleware(sly_data={})

        asyncio.run(middleware.awrap_model_call(_FakeModelRequest(tools=self._request_tools()), handler))
        assert [t["name"] for t in handler.await_args.args[0].tools] == ["other_tool"]

        # Empty the catalog and force a distinct modification time so the
        # fingerprint registers the edit even on coarse-mtime filesystems.
        catalog_file.write_text("{}", encoding="utf-8")
        stat = os.stat(catalog_file)
        os.utime(catalog_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

        asyncio.run(middleware.awrap_model_call(_FakeModelRequest(tools=self._request_tools()), handler))
        # No modules -> nothing stripped anymore.
        assert [t["name"] for t in handler.await_args.args[0].tools] == [SAFE_TOOL_NAME, "other_tool"]
