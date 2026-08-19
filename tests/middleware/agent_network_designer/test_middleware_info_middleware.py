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

"""Tests for MiddlewareInfoMiddleware: prompt injection, graceful degradation on a
missing/broken catalog, and process-wide caching."""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import patch

from langchain_core.messages import SystemMessage

from middleware.agent_network_designer.middleware_info_middleware import MiddlewareInfoMiddleware


class _FakeModelRequest:  # pylint: disable=too-few-public-methods
    """Just enough of langchain's ModelRequest for awrap_model_call: a system_message
    and an override() that returns a modified copy."""

    def __init__(self, system_message: SystemMessage | None = None):
        self.system_message = system_message

    def override(self, **kwargs) -> "_FakeModelRequest":
        """Mirror ModelRequest.override(): a copy with the given fields replaced."""
        return _FakeModelRequest(kwargs.get("system_message", self.system_message))


class TestMiddlewareInfoMiddleware:
    """Tests for MiddlewareInfoMiddleware."""

    @staticmethod
    def _install_catalog(tmp_path: Path, monkeypatch, catalog: dict[str, Any] | None = None) -> Path:
        """Write a catalog file (JSON is valid HOCON) and point MIDDLEWARE_INFO_FILE at it."""
        if catalog is None:
            catalog = {"pii_middleware": {"class": "middleware.pii.PII", "args": {}}}
        catalog_file = tmp_path / "middleware_info.hocon"
        catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
        monkeypatch.setenv("MIDDLEWARE_INFO_FILE", str(catalog_file))
        return catalog_file

    def test_catalog_injected_into_system_prompt(self, tmp_path, monkeypatch):
        """The catalog is appended to the system prompt as an Available Middleware section."""
        self._install_catalog(tmp_path, monkeypatch)
        handler = AsyncMock(return_value="model-response")
        request = _FakeModelRequest(system_message=SystemMessage(content="base"))

        result = asyncio.run(MiddlewareInfoMiddleware(sly_data={}).awrap_model_call(request, handler))

        assert result == "model-response"
        seen_content = handler.await_args.args[0].system_message.content
        assert seen_content.startswith("base")
        assert "## Available Middleware" in seen_content
        assert "pii_middleware" in seen_content

    def test_missing_catalog_degrades_gracefully(self, tmp_path, monkeypatch, caplog):
        """A missing catalog warns and skips injection instead of failing the model call."""
        monkeypatch.setenv("MIDDLEWARE_INFO_FILE", str(tmp_path / "nope.hocon"))
        handler = AsyncMock(return_value="model-response")
        request = _FakeModelRequest(system_message=SystemMessage(content="base"))

        with caplog.at_level("WARNING"):
            result = asyncio.run(MiddlewareInfoMiddleware(sly_data={}).awrap_model_call(request, handler))

        assert result == "model-response"
        assert "could not be loaded" in caplog.text
        # The request went through unmodified.
        assert handler.await_args.args[0].system_message.content == "base"

    def test_corrupt_catalog_degrades_then_recovers_after_fix(self, tmp_path, monkeypatch, caplog):
        """A corrupt catalog is retried, not cached: fixing the file recovers injection."""
        catalog_file = tmp_path / "middleware_info.hocon"
        catalog_file.write_text("{ this is : : not valid hocon }}", encoding="utf-8")
        monkeypatch.setenv("MIDDLEWARE_INFO_FILE", str(catalog_file))
        handler = AsyncMock(return_value="model-response")
        middleware = MiddlewareInfoMiddleware(sly_data={})

        with caplog.at_level("WARNING"):
            asyncio.run(middleware.awrap_model_call(_FakeModelRequest(), handler))
        assert "could not be loaded" in caplog.text

        catalog_file.write_text(json.dumps({"pii_middleware": {"class": "x"}}), encoding="utf-8")
        asyncio.run(middleware.awrap_model_call(_FakeModelRequest(), handler))
        assert "## Available Middleware" in handler.await_args.args[0].system_message.content

    def test_root_list_catalog_degrades_gracefully(self, tmp_path, monkeypatch, caplog):
        """A root-level array is not a catalog: warn and skip, and never publish it
        (so no AttributeError-per-call until an mtime change)."""
        catalog_file = tmp_path / "middleware_info.hocon"
        catalog_file.write_text('[{"class": "x"}]', encoding="utf-8")
        monkeypatch.setenv("MIDDLEWARE_INFO_FILE", str(catalog_file))
        handler = AsyncMock(return_value="model-response")
        middleware = MiddlewareInfoMiddleware(sly_data={})

        with caplog.at_level("WARNING"):
            result = asyncio.run(middleware.awrap_model_call(_FakeModelRequest(), handler))

        assert result == "model-response"
        assert "could not be loaded" in caplog.text
        # Fixing the file recovers on the next call — nothing bad was cached.
        catalog_file.write_text(json.dumps({"pii_middleware": {"class": "x"}}), encoding="utf-8")
        asyncio.run(middleware.awrap_model_call(_FakeModelRequest(), handler))
        assert "## Available Middleware" in handler.await_args.args[0].system_message.content

    def test_bundled_catalog_is_the_fallback_when_cwd_has_no_copy(self, tmp_path, monkeypatch):
        """With no env var and no repo/project-layout copy in the working directory,
        the catalog bundled next to the middleware module is used."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("MIDDLEWARE_INFO_FILE", raising=False)
        handler = AsyncMock(return_value="model-response")

        result = asyncio.run(MiddlewareInfoMiddleware(sly_data={}).awrap_model_call(_FakeModelRequest(), handler))

        assert result == "model-response"
        assert "## Available Middleware" in handler.await_args.args[0].system_message.content

    def test_empty_env_var_degrades_with_warning(self, monkeypatch, caplog):
        """MIDDLEWARE_INFO_FILE="" warns and skips instead of silently injecting nothing."""
        monkeypatch.setenv("MIDDLEWARE_INFO_FILE", "")
        handler = AsyncMock(return_value="model-response")

        with caplog.at_level("WARNING"):
            result = asyncio.run(MiddlewareInfoMiddleware(sly_data={}).awrap_model_call(_FakeModelRequest(), handler))

        assert result == "model-response"
        assert "empty string" in caplog.text

    def test_catalog_loaded_once_across_instances(self, tmp_path, monkeypatch):
        """Two instances (two 'sessions') share one parse of the catalog file."""
        self._install_catalog(tmp_path, monkeypatch)
        handler = AsyncMock(return_value="model-response")

        real_loader = MiddlewareInfoMiddleware._load_middleware_info  # pylint: disable=protected-access
        with patch.object(MiddlewareInfoMiddleware, "_load_middleware_info", side_effect=real_loader) as load_spy:
            with patch.object(
                MiddlewareInfoMiddleware._shared_info_cache,  # pylint: disable=protected-access
                "_loader",
                load_spy,
            ):
                for _ in range(2):
                    asyncio.run(MiddlewareInfoMiddleware(sly_data={}).awrap_model_call(_FakeModelRequest(), handler))

        assert load_spy.call_count == 1
