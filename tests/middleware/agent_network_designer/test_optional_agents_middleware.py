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

"""Tests for OptionalAgentsMiddleware: env-var gating, fail-closed catalog loading,
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
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

from middleware.agent_network_designer.optional_agents_middleware import OptionalAgentsMiddleware
from tests.middleware.agent_network_designer.fake_model_request import FakeModelRequest
from tests.middleware.agent_network_designer.fake_tool_call_request import FakeToolCallRequest

# The env var each test catalog's single module is toggled by.
TOGGLE_ENV_VAR = "TEST_USE_MIDDLEWARE_MODULE"
# Safe name the designer's executor exposes for the catalog's "/middleware_manager" ref.
SAFE_TOOL_NAME = "__middleware_manager"


# One public method per gated behavior; same accepted trade as the sibling
# definition-middleware tests.
# pylint: disable-next=too-many-public-methods
class TestOptionalAgentsMiddleware:
    """Tests for OptionalAgentsMiddleware."""

    @staticmethod
    def _write_catalog(tmp_path: Path, catalog: dict[str, Any], name: str = "optional_agents.hocon") -> Path:
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
        """Write a catalog and point AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE at it."""
        catalog_file = self._write_catalog(tmp_path, catalog if catalog is not None else self._standard_catalog())
        monkeypatch.setenv("AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE", str(catalog_file))
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
        request = FakeModelRequest(tools=self._request_tools(), system_message=SystemMessage(content="base"))

        result = asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

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
        request = FakeModelRequest(tools=self._request_tools(), system_message=SystemMessage(content="base"))

        asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == [SAFE_TOOL_NAME, "other_tool"]
        assert seen_request.system_message.content.startswith("base")
        assert "Call /middleware_manager" in seen_request.system_message.content

    def test_falsy_toggle_values_disable(self, tmp_path, monkeypatch):
        """Explicit 'false' (and other non-truthy strings) disable the module."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.setenv(TOGGLE_ENV_VAR, "false")
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

    def test_non_dict_catalog_entry_skipped_with_warning(self, tmp_path, monkeypatch, caplog):
        """A scalar top-level catalog entry is skipped, not an AttributeError per call."""
        catalog = {"version": "1", **self._standard_catalog()}
        self._install_catalog(tmp_path, monkeypatch, catalog)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        with caplog.at_level("WARNING"):
            asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert "not a mapping" in caplog.text
        # The well-formed module was still processed.
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

    def test_missing_env_var_field_disables_the_tool(self, tmp_path, monkeypatch, caplog):
        """An entry with a `tool` but no usable `enabled_env_var` must fail CLOSED:
        the tool is stripped and denied, not left silently live."""
        catalog = {"middleware_manager": {"tool": "/middleware_manager"}}
        self._install_catalog(tmp_path, monkeypatch, catalog)
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        with caplog.at_level("WARNING"):
            asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert "disabling its tool" in caplog.text
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

        denial = asyncio.run(
            OptionalAgentsMiddleware().awrap_tool_call(FakeToolCallRequest(SAFE_TOOL_NAME), AsyncMock())
        )
        assert isinstance(denial, ToolMessage)

    def test_non_string_env_var_field_disables_the_tool(self, tmp_path, monkeypatch, caplog):
        """An unquoted HOCON boolean (`enabled_env_var: true`) must disable the tool
        with a warning — not raise TypeError from os.getenv on every call."""
        catalog = {"middleware_manager": {"enabled_env_var": True, "tool": "/middleware_manager"}}
        self._install_catalog(tmp_path, monkeypatch, catalog)
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        with caplog.at_level("WARNING"):
            asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert "non-string `enabled_env_var`" in caplog.text
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

    def test_tool_ref_without_leading_slash_is_normalized(self, tmp_path, monkeypatch, caplog):
        """A `tool` ref missing its leading '/' is the common typo: normalize it so
        the gate still strips the real tool instead of silently matching nothing."""
        catalog = {
            "middleware_manager": {
                "enabled_env_var": TOGGLE_ENV_VAR,
                "tool": "middleware_manager",
            }
        }
        self._install_catalog(tmp_path, monkeypatch, catalog)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        with caplog.at_level("WARNING"):
            asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert "missing its leading '/'" in caplog.text
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

    def test_disabled_name_matching_nothing_warns(self, tmp_path, monkeypatch, caplog):
        """A disabled safe name that strips nothing is surfaced — it usually means a
        typo'd catalog ref whose real tool is now silently ungated."""
        catalog = {
            "ghost_module": {
                "enabled_env_var": TOGGLE_ENV_VAR,
                "tool": "/nonexistent_agent",
            }
        }
        self._install_catalog(tmp_path, monkeypatch, catalog)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        with caplog.at_level("WARNING"):
            asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert "matched nothing" in caplog.text
        # Nothing legitimate was stripped.
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == [SAFE_TOOL_NAME, "other_tool"]

    def test_empty_catalog_warns_and_gates_nothing(self, tmp_path, monkeypatch, caplog):
        """An empty catalog is a legitimate no-modules config, but it must leave a
        breadcrumb: it is indistinguishable from an accidentally truncated file."""
        self._install_catalog(tmp_path, monkeypatch, {})
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        with caplog.at_level("WARNING"):
            asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert "is empty" in caplog.text
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == [SAFE_TOOL_NAME, "other_tool"]

    # ------------------------------------------------------------------
    # awrap_model_call: fail-closed catalog loading
    # ------------------------------------------------------------------

    def test_missing_catalog_fails_closed(self, tmp_path, monkeypatch, caplog):
        """A missing catalog file refuses the model call instead of leaving tools intact,
        with a client-safe message; the resolved path goes to the server log only."""
        bad_path = tmp_path / "nope.hocon"
        monkeypatch.setenv("AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE", str(bad_path))
        handler = AsyncMock()

        with caplog.at_level("ERROR"):
            with pytest.raises(ValueError, match="failed to load") as raised:
                asyncio.run(OptionalAgentsMiddleware().awrap_model_call(FakeModelRequest(tools=[]), handler))

        handler.assert_not_awaited()
        # The client-visible message must not disclose the server-side path...
        assert str(bad_path) not in str(raised.value)
        # ...which lands in the server log instead.
        assert str(bad_path) in caplog.text

    def test_empty_env_var_fails_closed(self, monkeypatch, caplog):
        """AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE="" (the docker-compose/k8s 'unset' idiom) must not
        silently publish an empty catalog and turn the gate off."""
        monkeypatch.setenv("AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE", "")
        handler = AsyncMock()

        with caplog.at_level("ERROR"):
            with pytest.raises(ValueError, match="failed to load"):
                asyncio.run(OptionalAgentsMiddleware().awrap_model_call(FakeModelRequest(tools=[]), handler))

        handler.assert_not_awaited()
        assert "empty string" in caplog.text

    def test_root_list_catalog_fails_closed(self, tmp_path, monkeypatch):
        """A root-level array parses fine but is not a catalog: it must raise the
        actionable fail-closed error, not get published and AttributeError per call."""
        catalog_file = tmp_path / "optional_agents.hocon"
        catalog_file.write_text('[{"tool": "/middleware_manager"}]', encoding="utf-8")
        monkeypatch.setenv("AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE", str(catalog_file))
        handler = AsyncMock(return_value="model-response")
        middleware = OptionalAgentsMiddleware()

        with pytest.raises(ValueError, match="failed to load"):
            asyncio.run(middleware.awrap_model_call(FakeModelRequest(tools=[]), handler))

        # Nothing bad was published: fixing the file recovers on the next call.
        catalog_file.write_text(json.dumps(self._standard_catalog()), encoding="utf-8")
        result = asyncio.run(middleware.awrap_model_call(FakeModelRequest(tools=self._request_tools()), handler))
        assert result == "model-response"

    def test_corrupt_catalog_fails_closed_then_recovers_after_fix(self, tmp_path, monkeypatch):
        """A corrupt catalog raises; fixing the file recovers without a process restart."""
        catalog_file = tmp_path / "optional_agents.hocon"
        catalog_file.write_text("{ this is : : not valid hocon }}", encoding="utf-8")
        monkeypatch.setenv("AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE", str(catalog_file))
        handler = AsyncMock(return_value="model-response")
        middleware = OptionalAgentsMiddleware()

        with pytest.raises(ValueError, match="failed to load"):
            asyncio.run(middleware.awrap_model_call(FakeModelRequest(tools=[]), handler))

        # Fix the file in place; a failed load is never published, so the next call reloads.
        catalog_file.write_text(json.dumps(self._standard_catalog()), encoding="utf-8")
        result = asyncio.run(middleware.awrap_model_call(FakeModelRequest(tools=self._request_tools()), handler))
        assert result == "model-response"

    def test_bundled_catalog_is_the_fallback_when_cwd_has_no_copy(self, tmp_path, monkeypatch):
        """With no env var and no repo/project-layout copy in the working directory
        (the `ns run`-in-a-scaffolded-project case), the catalog bundled next to the
        middleware module is used — the designer must not brick."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE", raising=False)
        # The bundled (shipped) catalog gates /middleware_manager by this env var.
        monkeypatch.delenv("AGENT_NETWORK_DESIGNER_USE_MIDDLEWARE", raising=False)
        handler = AsyncMock(return_value="model-response")
        request = FakeModelRequest(tools=self._request_tools())

        result = asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert result == "model-response"
        seen_request = handler.await_args.args[0]
        assert [t["name"] for t in seen_request.tools] == ["other_tool"]

    # ------------------------------------------------------------------
    # awrap_tool_call: execution-time enforcement
    # ------------------------------------------------------------------

    def test_tool_call_denied_when_module_disabled(self, tmp_path, monkeypatch):
        """A tool call naming a disabled module tool is denied, not executed."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock()

        result = asyncio.run(OptionalAgentsMiddleware().awrap_tool_call(FakeToolCallRequest(SAFE_TOOL_NAME), handler))

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
            OptionalAgentsMiddleware().awrap_tool_call(FakeToolCallRequest(SAFE_TOOL_NAME, call_id=None), AsyncMock())
        )

        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "unknown"

    def test_tool_call_allowed_when_module_enabled(self, tmp_path, monkeypatch):
        """With the toggle on, the module's tool call goes through to the handler."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.setenv(TOGGLE_ENV_VAR, "1")
        handler = AsyncMock(return_value="tool-result")

        result = asyncio.run(OptionalAgentsMiddleware().awrap_tool_call(FakeToolCallRequest(SAFE_TOOL_NAME), handler))

        handler.assert_awaited_once()
        assert result == "tool-result"

    def test_tool_call_for_unmanaged_tool_allowed(self, tmp_path, monkeypatch):
        """Tools outside the catalog are never blocked, whatever the toggles say."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="tool-result")

        result = asyncio.run(OptionalAgentsMiddleware().awrap_tool_call(FakeToolCallRequest("other_tool"), handler))

        handler.assert_awaited_once()
        assert result == "tool-result"

    def test_tool_call_fails_closed_on_missing_catalog(self, tmp_path, monkeypatch):
        """The execution-time gate fails closed too: no catalog, no tool execution."""
        monkeypatch.setenv("AGENT_NETWORK_DESIGNER_OPTIONAL_AGENTS_FILE", str(tmp_path / "nope.hocon"))
        handler = AsyncMock()

        with pytest.raises(ValueError, match="failed to load"):
            asyncio.run(OptionalAgentsMiddleware().awrap_tool_call(FakeToolCallRequest(SAFE_TOOL_NAME), handler))

        handler.assert_not_awaited()

    # ------------------------------------------------------------------
    # Process-wide caching
    # ------------------------------------------------------------------

    def test_catalog_loaded_once_across_instances(self, tmp_path, monkeypatch):
        """Two instances (two 'sessions') share one parse of the catalog file."""
        self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")

        # Spy on the file parse itself: with autospec the original method still
        # runs (captured before patching, so no recursion), and the call count
        # tells us how many times the file was actually read.
        real_restore = AbstractAsyncConfigRestorer.restore
        with patch.object(AbstractAsyncConfigRestorer, "restore", autospec=True, side_effect=real_restore) as spy:
            for _ in range(2):
                request = FakeModelRequest(tools=self._request_tools())
                asyncio.run(OptionalAgentsMiddleware().awrap_model_call(request, handler))

        assert spy.call_count == 1

    def test_catalog_edit_is_picked_up_via_fingerprint(self, tmp_path, monkeypatch):
        """Editing the catalog file is visible on the next call, no restart needed."""
        catalog_file = self._install_catalog(tmp_path, monkeypatch)
        monkeypatch.delenv(TOGGLE_ENV_VAR, raising=False)
        handler = AsyncMock(return_value="model-response")
        middleware = OptionalAgentsMiddleware()

        asyncio.run(middleware.awrap_model_call(FakeModelRequest(tools=self._request_tools()), handler))
        assert [t["name"] for t in handler.await_args.args[0].tools] == ["other_tool"]

        # Empty the catalog and force a distinct modification time so the
        # fingerprint registers the edit even on coarse-mtime filesystems.
        catalog_file.write_text("{}", encoding="utf-8")
        stat = os.stat(catalog_file)
        os.utime(catalog_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

        asyncio.run(middleware.awrap_model_call(FakeModelRequest(tools=self._request_tools()), handler))
        # No modules -> nothing stripped anymore.
        assert [t["name"] for t in handler.await_args.args[0].tools] == [SAFE_TOOL_NAME, "other_tool"]
