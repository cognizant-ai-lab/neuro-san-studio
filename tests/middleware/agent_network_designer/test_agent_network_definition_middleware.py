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

"""Tests for AgentNetworkDefinitionMiddleware.

The S3 reservation path is intentionally not covered here — its underlying storage
client is synchronous and is slated for replacement, so locking down its current
behavior with tests would just block that work.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.messages import SystemMessage

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from middleware.agent_network_designer.agent_network_definition_middleware import AGENT_NETWORK_HOCON_FILE
from middleware.agent_network_designer.agent_network_definition_middleware import SKIP_DESIGNER
from middleware.agent_network_designer.agent_network_definition_middleware import AgentNetworkDefinitionMiddleware


# Tests legitimately exercise private helpers (the load/parse pipeline is internal to the
# middleware class) and the suite covers many behaviors in a single class for cohesion.
# pylint: disable=protected-access,too-many-public-methods
class TestAgentNetworkDefinitionMiddleware:
    """Tests for AgentNetworkDefinitionMiddleware (non-S3 paths)."""

    @staticmethod
    def _make_mw(sly_data: dict | None = None) -> AgentNetworkDefinitionMiddleware:
        """Build a middleware instance with a pre-seeded aaosa cache so tests don't hit disk."""
        sly = sly_data if sly_data is not None else {}
        # Pre-populate aaosa cache so _get_aaosa_instructions short-circuits without reading
        # registries/aaosa.hocon. Tests that need the real loader can delete this key.
        sly.setdefault("aaosa_instructions", "")
        return AgentNetworkDefinitionMiddleware(sly_data=sly)

    # ------------------------------------------------------------------
    # _parse_agent: extracts instructions, description, tools, middleware
    # ------------------------------------------------------------------

    def test_parse_agent_returns_none_for_non_dict_entry(self):
        """Non-dict entries in the `tools` list are skipped."""
        mw = self._make_mw()
        name, agent_def = asyncio.run(mw._parse_agent("not a dict", "src"))
        assert name is None
        assert agent_def == {}

    def test_parse_agent_returns_none_for_missing_name(self):
        """An agent without `name` is skipped."""
        mw = self._make_mw()
        name, agent_def = asyncio.run(mw._parse_agent({"instructions": "hi"}, "src"))
        assert name is None
        assert agent_def == {}

    def test_parse_agent_returns_none_for_empty_name(self):
        """An empty string name is treated as missing."""
        mw = self._make_mw()
        name, _ = asyncio.run(mw._parse_agent({"name": ""}, "src"))
        assert name is None

    def test_parse_agent_returns_none_for_non_string_instructions(self):
        """Non-string `instructions` invalidates the whole agent."""
        mw = self._make_mw()
        name, _ = asyncio.run(mw._parse_agent({"name": "a", "instructions": 123}, "src"))
        assert name is None

    def test_parse_agent_returns_none_for_non_string_description(self):
        """Non-string `function.description` invalidates the whole agent."""
        mw = self._make_mw()
        name, _ = asyncio.run(mw._parse_agent({"name": "a", "function": {"description": 42}}, "src"))
        assert name is None

    def test_parse_agent_extracts_tools(self):
        """`tools` is copied through; absent middleware does not add a `middleware` key."""
        mw = self._make_mw()
        name, agent_def = asyncio.run(mw._parse_agent({"name": "a", "tools": ["b", "c"]}, "src"))
        assert name == "a"
        assert agent_def["tools"] == ["b", "c"]
        assert "middleware" not in agent_def

    def test_parse_agent_extracts_description_from_function(self):
        """`function.description` is trimmed and stored as `description` on the agent."""
        mw = self._make_mw()
        _, agent_def = asyncio.run(
            mw._parse_agent({"name": "a", "instructions": "hi.", "function": {"description": "  An agent.  "}}, "src")
        )
        assert agent_def["description"] == "An agent."

    def test_parse_agent_initializes_blank_description_for_llm_agents(self):
        """When instructions present, description must exist (even empty) so setters can update it."""
        mw = self._make_mw()
        _, agent_def = asyncio.run(mw._parse_agent({"name": "a", "instructions": "hi."}, "src"))
        assert agent_def.get("description") == ""

    def test_parse_agent_preserves_middleware_list(self):
        """Middleware on agents must round-trip on load (regression: previously dropped)."""
        mw = self._make_mw()
        middleware = [
            {"class": "langchain.agents.middleware.PIIMiddleware", "args": {"pii_type": "email"}},
            {
                "class": "middleware.agent_checklist_middleware.AgentChecklistMiddleware",
                "args": {"checklist_title": "Audit"},
            },
        ]
        _, agent_def = asyncio.run(
            mw._parse_agent({"name": "a", "instructions": "hi.", "middleware": middleware}, "src")
        )
        assert agent_def["middleware"] == middleware

    def test_parse_agent_drops_middleware_when_not_a_list(self):
        """Non-list middleware is logged and dropped; the rest of the agent still loads."""
        mw = self._make_mw()
        name, agent_def = asyncio.run(
            mw._parse_agent({"name": "a", "instructions": "hi.", "middleware": "not a list"}, "src")
        )
        assert name == "a"
        assert "middleware" not in agent_def
        assert agent_def["instructions"] == "hi."

    def test_parse_agent_drops_middleware_when_entries_are_not_dicts(self):
        """Middleware that is a list but contains non-dict entries is dropped."""
        mw = self._make_mw()
        _, agent_def = asyncio.run(mw._parse_agent({"name": "a", "middleware": ["not a dict"]}, "src"))
        assert "middleware" not in agent_def

    def test_parse_agent_omits_middleware_key_when_empty(self):
        """An empty middleware list adds no `middleware` key to the agent definition."""
        mw = self._make_mw()
        _, agent_def = asyncio.run(mw._parse_agent({"name": "a", "middleware": []}, "src"))
        assert "middleware" not in agent_def

    # ------------------------------------------------------------------
    # _config_to_network_def: parses HOCON config's `tools` list
    # ------------------------------------------------------------------

    def test_config_to_network_def_returns_none_when_tools_missing(self):
        """A config without the `tools` field reports an actionable error and returns None."""
        mw = self._make_mw()
        result = asyncio.run(mw._config_to_network_def({}, "src"))
        assert result is None
        assert "No field 'tools' found" in mw.error_message

    def test_config_to_network_def_returns_none_when_tools_not_a_list(self):
        """`tools` of the wrong type reports an actionable error and returns None."""
        mw = self._make_mw()
        result = asyncio.run(mw._config_to_network_def({"tools": "not a list"}, "src"))
        assert result is None
        assert "not a list" in mw.error_message

    def test_config_to_network_def_skips_unparseable_agents(self):
        """A single bad entry does not invalidate sibling entries in the same network."""
        mw = self._make_mw()
        config = {
            "tools": [
                {"name": "ok", "instructions": "hi."},
                "not a dict",
                {"missing_name": True},
            ]
        }
        result = asyncio.run(mw._config_to_network_def(config, "src"))
        assert list(result.keys()) == ["ok"]

    # ------------------------------------------------------------------
    # _normalize_network_def: dict pass-through, list (connectivity) → dict
    # ------------------------------------------------------------------

    def test_normalize_dict_input_passes_through_and_caches(self):
        """A dict input is returned as-is and stored under AGENT_NETWORK_DEFINITION in sly_data."""
        sly = {"aaosa_instructions": ""}
        mw = self._make_mw(sly_data=sly)
        net = {"a": {"instructions": "hi."}}
        result = mw._normalize_network_def(net)
        assert result is net
        assert sly[AGENT_NETWORK_DEFINITION] is net

    def test_normalize_connectivity_list_is_converted_to_dict(self):
        """A connectivity-format list is converted to the internal dict format and cached."""
        sly = {"aaosa_instructions": ""}
        mw = self._make_mw(sly_data=sly)
        net_list = [
            {"origin": "top", "tools": ["worker"]},
            {"origin": "worker"},
        ]
        result = mw._normalize_network_def(net_list)
        assert isinstance(result, dict)
        assert set(result.keys()) == {"top", "worker"}
        assert sly[AGENT_NETWORK_DEFINITION] is result

    # ------------------------------------------------------------------
    # format_definition_prompt: markdown-fenced JSON block
    # ------------------------------------------------------------------

    def test_format_definition_prompt_emits_round_trippable_json(self):
        """The injected system-prompt section is a markdown-fenced JSON block we can re-parse."""
        mw = self._make_mw()
        prompt = mw.format_definition_prompt({"a": {"instructions": "hi."}})
        assert prompt.startswith("## Current Agent Network Definition")
        body = prompt.split("```json\n", 1)[1].rsplit("\n```", 1)[0]
        assert json.loads(body) == {"a": {"instructions": "hi."}}

    # ------------------------------------------------------------------
    # _resolve_hocon_path: input validation + cwd vs base_dir resolution
    # ------------------------------------------------------------------

    def test_resolve_hocon_path_returns_none_for_non_string(self):
        """None input is rejected with an `expected non-empty string` error."""
        mw = self._make_mw()
        assert mw._resolve_hocon_path(None) is None
        assert "expected non-empty string" in mw.error_message

    def test_resolve_hocon_path_returns_none_for_whitespace_only(self):
        """Whitespace-only input is rejected with an `expected non-empty string` error."""
        mw = self._make_mw()
        assert mw._resolve_hocon_path("   ") is None
        assert "expected non-empty string" in mw.error_message

    def test_resolve_hocon_path_passes_through_absolute(self):
        """A POSIX-absolute input is returned unchanged."""
        mw = self._make_mw()
        assert mw._resolve_hocon_path("/abs/path/to/file.hocon") == "/abs/path/to/file.hocon"

    def test_resolve_hocon_path_keeps_existing_cwd_relative_path_as_is(self):
        """A relative path that resolves to an existing file under cwd is used as-is."""
        mw = self._make_mw()
        with patch.object(Path, "is_file", return_value=True):
            result = mw._resolve_hocon_path("registries/generated/foo.hocon")
        assert result == "registries/generated/foo.hocon"

    def test_resolve_hocon_path_falls_through_to_manifest_base_dir(self):
        """Non-existent relative input is joined to AGENT_MANIFEST_FILE's directory."""
        mw = self._make_mw()
        with patch.dict(os.environ, {"AGENT_MANIFEST_FILE": "registries/manifest.hocon"}):
            result = mw._resolve_hocon_path("foo.hocon")
        assert result == "registries/foo.hocon"

    # ------------------------------------------------------------------
    # _hocon_to_config: disk reads and error reporting
    # ------------------------------------------------------------------

    def test_hocon_to_config_reads_valid_file(self):
        """A valid HOCON file is parsed into a dict and no error_message is set."""
        mw = self._make_mw()
        with tempfile.NamedTemporaryFile("w", suffix=".hocon", delete=False) as f:
            f.write('{ "tools": [{"name": "a"}] }')
            path = f.name
        try:
            config = asyncio.run(mw._hocon_to_config(path))
            assert config["tools"][0]["name"] == "a"
            assert mw.error_message == ""
        finally:
            os.unlink(path)

    def test_hocon_to_config_sets_error_for_missing_file(self):
        """A missing file path is reported via error_message and the return is None."""
        mw = self._make_mw()
        result = asyncio.run(mw._hocon_to_config("/definitely/not/a/file.hocon"))
        assert result is None
        assert "not found" in mw.error_message.lower()

    # ------------------------------------------------------------------
    # _hocon_to_definition: end-to-end load round trip
    # ------------------------------------------------------------------

    def test_hocon_to_definition_round_trip_preserves_middleware(self):
        """End-to-end HOCON → network_def keeps every agent's middleware array intact."""
        mw = self._make_mw()
        hocon = (
            "{"
            '"tools": ['
            '  {"name": "top", "function": {"description": "Top"},'
            '   "instructions": "I am the top.", "tools": ["worker"],'
            '   "middleware": [{"class": "X", "args": {"k": "v"}}]},'
            '  {"name": "worker", "function": {"description": "Worker"},'
            '   "instructions": "I am the worker.",'
            '   "middleware": [{"class": "Y"}]}'
            "]}"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".hocon", delete=False) as f:
            f.write(hocon)
            path = f.name
        try:
            net = asyncio.run(mw._hocon_to_definition(path))
            assert set(net.keys()) == {"top", "worker"}
            assert net["top"]["middleware"] == [{"class": "X", "args": {"k": "v"}}]
            assert net["worker"]["middleware"] == [{"class": "Y"}]
            assert net["top"]["tools"] == ["worker"]
        finally:
            os.unlink(path)

    # ------------------------------------------------------------------
    # _resolve_network_def: source-precedence
    # ------------------------------------------------------------------

    def test_resolve_prefers_sly_data_definition_over_hocon_file(self):
        """A definition already in sly_data wins over the configured hocon_file."""
        existing = {"top": {"instructions": "hi."}}
        sly = {
            "aaosa_instructions": "",
            AGENT_NETWORK_DEFINITION: existing,
            AGENT_NETWORK_HOCON_FILE: "ignored.hocon",
        }
        mw = self._make_mw(sly_data=sly)
        assert asyncio.run(mw._resolve_network_def()) is existing

    def test_resolve_loads_from_hocon_when_no_definition_in_sly_data(self):
        """When sly_data has no definition, the hocon file is read and the name is auto-set."""
        sly = {"aaosa_instructions": ""}
        mw = self._make_mw(sly_data=sly)
        with tempfile.NamedTemporaryFile("w", suffix=".hocon", delete=False) as f:
            f.write('{"tools": [{"name": "a", "instructions": "hi."}]}')
            path = f.name
        try:
            sly[AGENT_NETWORK_HOCON_FILE] = path
            result = asyncio.run(mw._resolve_network_def())
            assert "a" in result
            # The agent network name is auto-set from the file stem on hocon load.
            assert sly[AGENT_NETWORK_NAME] == Path(path).stem
        finally:
            os.unlink(path)

    def test_resolve_returns_none_when_no_source(self):
        """When sly_data has no definition and no hocon_file, the resolver returns None."""
        mw = self._make_mw()
        assert asyncio.run(mw._resolve_network_def()) is None

    # ------------------------------------------------------------------
    # abefore_model: orchestration + error/skip-designer routing
    # ------------------------------------------------------------------

    def test_abefore_model_returns_none_when_no_definition_anywhere(self):
        """No definition source means the agent is free to respond without injection."""
        mw = self._make_mw()
        result = asyncio.run(mw.abefore_model(state={}, runtime=None))
        assert result is None
        assert mw.network_def is None

    def test_abefore_model_jumps_to_end_when_resolve_errors(self):
        """A missing hocon file surfaces as an AIMessage and a jump_to=end."""
        sly = {"aaosa_instructions": "", AGENT_NETWORK_HOCON_FILE: "/does/not/exist.hocon"}
        mw = self._make_mw(sly_data=sly)
        result = asyncio.run(mw.abefore_model(state={}, runtime=None))
        assert result["jump_to"] == "end"
        assert isinstance(result["messages"][0], AIMessage)
        assert "not found" in result["messages"][0].content.lower()

    def test_abefore_model_reports_missing_agent_network_name(self):
        """A definition present without a name is a user error; report it actionably."""
        sly = {"aaosa_instructions": "", AGENT_NETWORK_DEFINITION: {"a": {"instructions": "hi."}}}
        mw = self._make_mw(sly_data=sly)
        result = asyncio.run(mw.abefore_model(state={}, runtime=None))
        assert result["jump_to"] == "end"
        assert AGENT_NETWORK_NAME in result["messages"][0].content

    def test_abefore_model_skip_designer_jumps_to_end_with_acknowledgement(self):
        """`skip_designer=True` short-circuits the LLM and acknowledges the user-supplied network."""
        sly = {
            "aaosa_instructions": "",
            AGENT_NETWORK_DEFINITION: {"a": {"instructions": "hi."}},
            AGENT_NETWORK_NAME: "my_net",
            SKIP_DESIGNER: True,
        }
        mw = self._make_mw(sly_data=sly)
        result = asyncio.run(mw.abefore_model(state={}, runtime=None))
        assert result["jump_to"] == "end"
        assert "my_net" in result["messages"][0].content

    def test_abefore_model_normal_path_returns_none_and_caches_definition(self):
        """Happy path: a valid sly_data definition + name resolves, caches, and lets the agent proceed."""
        net = {"a": {"instructions": "hi."}}
        sly = {"aaosa_instructions": "", AGENT_NETWORK_DEFINITION: net, AGENT_NETWORK_NAME: "my_net"}
        mw = self._make_mw(sly_data=sly)
        result = asyncio.run(mw.abefore_model(state={}, runtime=None))
        assert result is None
        assert mw.network_def == net

    # ------------------------------------------------------------------
    # awrap_model_call: system-prompt injection
    # ------------------------------------------------------------------

    def test_awrap_passes_through_when_no_definition(self):
        """With no network_def, the handler is invoked with the original request unmodified."""
        mw = self._make_mw()
        mw.network_def = None

        request = MagicMock()
        handler = AsyncMock(return_value="response")
        result = asyncio.run(mw.awrap_model_call(request, handler))
        assert result == "response"
        handler.assert_awaited_once_with(request)
        request.override.assert_not_called()

    def test_awrap_appends_to_existing_system_message(self):
        """An existing SystemMessage is preserved and the definition block is appended to it."""
        mw = self._make_mw()
        mw.network_def = {"a": {"instructions": "hi."}}

        original = SystemMessage(content="ORIGINAL")
        request = MagicMock()
        request.system_message = original
        new_request = MagicMock()
        request.override.return_value = new_request
        handler = AsyncMock(return_value="response")

        result = asyncio.run(mw.awrap_model_call(request, handler))

        assert result == "response"
        request.override.assert_called_once()
        forwarded_system = request.override.call_args.kwargs["system_message"]
        assert "ORIGINAL" in forwarded_system.content
        assert "Current Agent Network Definition" in forwarded_system.content
        handler.assert_awaited_once_with(new_request)

    def test_awrap_creates_system_message_when_none_present(self):
        """When the request has no SystemMessage, a fresh one is created with just the definition."""
        mw = self._make_mw()
        mw.network_def = {"a": {"instructions": "hi."}}

        request = MagicMock()
        request.system_message = None
        request.override.return_value = MagicMock()
        handler = AsyncMock(return_value="ok")

        asyncio.run(mw.awrap_model_call(request, handler))

        forwarded = request.override.call_args.kwargs["system_message"]
        assert isinstance(forwarded, SystemMessage)
        assert "Current Agent Network Definition" in forwarded.content

    # ------------------------------------------------------------------
    # _extract_custom_instructions: strips boilerplate (prefix, aaosa, demo)
    # ------------------------------------------------------------------

    def test_extract_custom_instructions_strips_prefix(self):
        """The standard `You are part of a <noun> of assistants...` prefix is removed."""
        mw = self._make_mw(sly_data={"aaosa_instructions": ""})
        full = (
            "You are part of a team of assistants. "
            "Only answer inquiries that are directly within your area of expertise. "
            "Do not try to help for other matters. "
            "Do not mention what you can NOT do. Only mention what you can do. "
            "Custom body here."
        )
        result = asyncio.run(mw._extract_custom_instructions(full))
        assert result == "Custom body here."

    def test_extract_custom_instructions_strips_demo_mode(self):
        """The demo_mode boilerplate sentence is removed."""
        mw = self._make_mw(sly_data={"aaosa_instructions": ""})
        demo = (
            "You are part of a demo system, so when queried, make up a realistic response as if "
            "you are actually grounded in real data or you are operating a real application API or microservice."
        )
        result = asyncio.run(mw._extract_custom_instructions(f"{demo} Real body."))
        assert result == "Real body."

    def test_extract_custom_instructions_strips_aaosa_when_cached(self):
        """The aaosa instructions stored in sly_data are stripped from the agent's instructions."""
        mw = self._make_mw(sly_data={"aaosa_instructions": "AAOSA TEXT"})
        result = asyncio.run(mw._extract_custom_instructions("Body. AAOSA TEXT"))
        assert result == "Body."
