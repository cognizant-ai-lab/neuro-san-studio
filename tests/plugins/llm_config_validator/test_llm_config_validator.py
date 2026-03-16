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

from unittest import TestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from plugins.llm_config_validator.check_llm_configs import _expand_fallbacks
from plugins.llm_config_validator.check_llm_configs import extract_llm_configs_from_agent_network
from plugins.llm_config_validator.check_llm_configs import extract_llm_configs_from_studio_config
from plugins.llm_config_validator.llm_config_validator_plugin import LlmConfigValidatorPlugin


class TestExpandFallbacks(TestCase):
    """Tests for _expand_fallbacks — pure function, no I/O."""

    def test_no_fallbacks_key_returns_config_as_is(self):
        """Config with no 'fallbacks' key is returned unchanged as a single entry."""
        config = {"model_name": "gpt-5-mini"}
        result = _expand_fallbacks("MyAgent", config)
        self.assertEqual(result, [("MyAgent", config)])

    def test_empty_fallbacks_list_returns_config_as_is(self):
        """Config with an empty 'fallbacks' list is returned unchanged as a single entry."""
        config = {"model_name": "gpt-5-mini", "fallbacks": []}
        result = _expand_fallbacks("MyAgent", config)
        self.assertEqual(result, [("MyAgent", config)])

    def test_fallbacks_only_no_primary_model_name(self):
        """Mirrors music_nerd_llm_fallbacks.hocon: each fallback becomes a separate entry."""
        config = {
            "fallbacks": [
                {"model_name": "gpt-5-mini"},
                {"model_name": "claude-sonnet-4-6"},
            ]
        }
        result = _expand_fallbacks("MusicNerd", config)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("MusicNerd (fallback 0)", {"model_name": "gpt-5-mini"}))
        self.assertEqual(result[1], ("MusicNerd (fallback 1)", {"model_name": "claude-sonnet-4-6"}))

    def test_fallbacks_with_primary_model_name_includes_primary(self):
        """When the primary config also has a model_name it is prepended before the fallbacks."""
        config = {
            "model_name": "gpt-5-mini",
            "fallbacks": [{"model_name": "claude-sonnet-4-6"}],
        }
        result = _expand_fallbacks("MyAgent", config)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("MyAgent (primary)", {"model_name": "gpt-5-mini"}))
        self.assertEqual(result[1], ("MyAgent (fallback 0)", {"model_name": "claude-sonnet-4-6"}))

    def test_single_fallback_entry(self):
        """A fallbacks list with one element produces exactly one result entry."""
        config = {"fallbacks": [{"model_name": "gpt-5-mini"}]}
        result = _expand_fallbacks("MyAgent", config)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("MyAgent (fallback 0)", {"model_name": "gpt-5-mini"}))

    def test_label_is_preserved_in_all_entries(self):
        """The label prefix is present in every expanded fallback entry."""
        config = {
            "fallbacks": [
                {"model_name": "a"},
                {"model_name": "b"},
                {"model_name": "c"},
            ]
        }
        result = _expand_fallbacks("Agent X", config)
        labels = [label for label, _ in result]
        self.assertEqual(labels, ["Agent X (fallback 0)", "Agent X (fallback 1)", "Agent X (fallback 2)"])


class TestExtractLlmConfigsFromStudioConfig(TestCase):
    """Tests for extract_llm_configs_from_studio_config — pure function, no I/O."""

    def test_empty_config_returns_empty_list(self):
        """An empty dict produces no llm_config entries."""
        result = extract_llm_configs_from_studio_config({}, "path/to/config.hocon")
        self.assertEqual(result, [])

    def test_config_without_llm_config_key_returns_empty_list(self):
        """A config dict that has no 'llm_config' key produces no entries."""
        result = extract_llm_configs_from_studio_config({"tools": []}, "path/to/config.hocon")
        self.assertEqual(result, [])

    def test_simple_llm_config_uses_hocon_path_as_label(self):
        """A plain llm_config with no fallbacks uses the HOCON file path as the label."""
        config = {"llm_config": {"model_name": "gpt-5-mini"}}
        result = extract_llm_configs_from_studio_config(config, "registries/llm_config.hocon")
        self.assertEqual(result, [("registries/llm_config.hocon", {"model_name": "gpt-5-mini"})])

    def test_llm_config_with_fallbacks_is_expanded(self):
        """A studio llm_config that uses a fallbacks list is expanded into one entry per fallback."""
        config = {
            "llm_config": {
                "fallbacks": [
                    {"model_name": "gpt-5-mini"},
                    {"model_name": "claude-sonnet-4-6"},
                ]
            }
        }
        result = extract_llm_configs_from_studio_config(config, "registries/llm_config.hocon")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "registries/llm_config.hocon (fallback 0)")
        self.assertEqual(result[0][1], {"model_name": "gpt-5-mini"})
        self.assertEqual(result[1][0], "registries/llm_config.hocon (fallback 1)")
        self.assertEqual(result[1][1], {"model_name": "claude-sonnet-4-6"})


class TestExtractLlmConfigsFromAgentNetwork(TestCase):
    """Tests for extract_llm_configs_from_agent_network using a mocked AgentNetwork."""

    def _make_network(self, config: dict) -> MagicMock:
        """Return a MagicMock AgentNetwork backed by the given config dict."""
        mock_network = MagicMock()
        mock_network.get_config.return_value = config
        mock_network.get_name_from_spec.side_effect = lambda spec: spec.get("name", "Unknown")
        return mock_network

    def test_agent_inherits_top_level_llm_config(self):
        """An agent with no per-agent llm_config inherits the top-level one."""
        config = {
            "llm_config": {"model_name": "gpt-5-mini"},
            "tools": [{"name": "AgentA"}],
        }
        result = extract_llm_configs_from_agent_network(self._make_network(config))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "AgentA")
        self.assertEqual(result[0][1]["model_name"], "gpt-5-mini")

    def test_coded_tool_is_skipped(self):
        """Agents with a 'class' key (CodedTools) are excluded from the results."""
        config = {
            "llm_config": {"model_name": "gpt-5-mini"},
            "tools": [
                {"name": "AgentA"},
                {"name": "CodedToolB", "class": "some.CodedClass"},
            ],
        }
        result = extract_llm_configs_from_agent_network(self._make_network(config))
        labels = [label for label, _ in result]
        self.assertIn("AgentA", labels)
        self.assertNotIn("CodedToolB", labels)

    def test_per_agent_llm_config_overrides_top_level(self):
        """A per-agent llm_config model_name takes precedence over the top-level default."""
        config = {
            "llm_config": {"model_name": "gpt-5-mini", "temperature": 0.5},
            "tools": [{"name": "AgentA", "llm_config": {"model_name": "claude-sonnet-4-6"}}],
        }
        result = extract_llm_configs_from_agent_network(self._make_network(config))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1]["model_name"], "claude-sonnet-4-6")

    def test_top_level_fallbacks_expanded_per_agent(self):
        """Top-level fallbacks are inherited and expanded into one entry per fallback per agent."""
        config = {
            "llm_config": {
                "fallbacks": [
                    {"model_name": "gpt-5-mini"},
                    {"model_name": "claude-sonnet-4-6"},
                ]
            },
            "tools": [{"name": "MusicNerd"}],
        }
        result = extract_llm_configs_from_agent_network(self._make_network(config))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "MusicNerd (fallback 0)")
        self.assertEqual(result[0][1], {"model_name": "gpt-5-mini"})
        self.assertEqual(result[1][0], "MusicNerd (fallback 1)")
        self.assertEqual(result[1][1], {"model_name": "claude-sonnet-4-6"})

    def test_no_tools_returns_empty_list(self):
        """An agent network with an empty tools list produces no results."""
        config = {"llm_config": {"model_name": "gpt-5-mini"}, "tools": []}
        result = extract_llm_configs_from_agent_network(self._make_network(config))
        self.assertEqual(result, [])

    def test_multiple_agents_all_extracted(self):
        """All non-coded agents in the network are included in the result."""
        config = {
            "llm_config": {"model_name": "gpt-5-mini"},
            "tools": [
                {"name": "AgentA"},
                {"name": "AgentB"},
                {"name": "AgentC"},
            ],
        }
        result = extract_llm_configs_from_agent_network(self._make_network(config))
        labels = [label for label, _ in result]
        self.assertEqual(labels, ["AgentA", "AgentB", "AgentC"])


_MODULE = "plugins.llm_config_validator.llm_config_validator_plugin"


class TestLlmConfigValidatorPlugin(TestCase):
    """Tests for LlmConfigValidatorPlugin.check using mocked I/O."""

    def _patch_all(self, is_agent_network: bool, llm_configs: list, successes: list, failures: list):
        """Return a dict of active patches for a standard plugin.check() run."""
        patches = {
            "parse_hocon_file": patch(f"{_MODULE}.parse_hocon_file", return_value={}),
            "is_agent_network_hocon": patch(f"{_MODULE}.is_agent_network_hocon", return_value=is_agent_network),
            "extract_studio": patch(f"{_MODULE}.extract_llm_configs_from_studio_config", return_value=llm_configs),
            "extract_network": patch(f"{_MODULE}.extract_llm_configs_from_agent_network", return_value=llm_configs),
            "load_agent_network": patch(f"{_MODULE}.load_agent_network", return_value=MagicMock()),
            "create_factory": patch(f"{_MODULE}.create_and_load_llm_factory", return_value=MagicMock()),
            "test_llm_configs": patch(
                f"{_MODULE}.test_llm_configs", new=AsyncMock(return_value=(successes, failures))
            ),
            "print_results": patch(f"{_MODULE}.print_results"),
        }
        return patches

    def test_all_pass_does_not_exit(self):
        """When all LLM configs succeed, check() returns normally and print_results is called."""
        successes = [(["my.hocon"], {"model_name": "gpt-5-mini"})]
        patches = self._patch_all(
            is_agent_network=False,
            llm_configs=[("my.hocon", {"model_name": "gpt-5-mini"})],
            successes=successes,
            failures=[],
        )
        with (
            patches["parse_hocon_file"],
            patches["is_agent_network_hocon"],
            patches["extract_studio"],
            patches["extract_network"],
            patches["load_agent_network"],
            patches["create_factory"],
            patches["test_llm_configs"],
            patches["print_results"] as mock_print_results,
        ):
            LlmConfigValidatorPlugin().check("my.hocon")  # must not raise
            mock_print_results.assert_called_once_with(successes, [])

    def test_failures_cause_sys_exit_1(self):
        """When any LLM config fails, check() calls sys.exit(1)."""
        failures = [(["my.hocon"], {"model_name": "gpt-5-mini"}, "Connection error")]
        patches = self._patch_all(
            is_agent_network=False,
            llm_configs=[("my.hocon", {"model_name": "gpt-5-mini"})],
            successes=[],
            failures=failures,
        )
        with (
            patches["parse_hocon_file"],
            patches["is_agent_network_hocon"],
            patches["extract_studio"],
            patches["extract_network"],
            patches["load_agent_network"],
            patches["create_factory"],
            patches["test_llm_configs"],
            patches["print_results"],
        ):
            with self.assertRaises(SystemExit) as ctx:
                LlmConfigValidatorPlugin().check("my.hocon")
            self.assertEqual(ctx.exception.code, 1)

    def test_no_llm_configs_found_returns_early(self):
        """When no llm_configs are found, check() returns early without testing or printing."""
        patches = self._patch_all(
            is_agent_network=False,
            llm_configs=[],
            successes=[],
            failures=[],
        )
        with (
            patches["parse_hocon_file"],
            patches["is_agent_network_hocon"],
            patches["extract_studio"],
            patches["extract_network"],
            patches["load_agent_network"],
            patches["create_factory"],
            patches["test_llm_configs"] as mock_test,
            patches["print_results"] as mock_print,
        ):
            LlmConfigValidatorPlugin().check("my.hocon")  # must not raise
            mock_test.assert_not_called()
            mock_print.assert_not_called()

    def test_parse_failure_exits_with_1(self):
        """A failure to parse the HOCON file causes sys.exit(1)."""
        with patch(f"{_MODULE}.parse_hocon_file", side_effect=Exception("bad file")):
            with self.assertRaises(SystemExit) as ctx:
                LlmConfigValidatorPlugin().check("bad.hocon")
            self.assertEqual(ctx.exception.code, 1)

    def test_agent_network_path_uses_network_extractor(self):
        """An agent network HOCON file uses the network extractor, not the studio extractor."""
        mock_network = MagicMock()
        mock_network.get_network_name.return_value = "TestNetwork"
        llm_configs = [("AgentA", {"model_name": "gpt-5-mini"})]
        successes = [(["AgentA"], {"model_name": "gpt-5-mini"})]

        with (
            patch(f"{_MODULE}.parse_hocon_file", return_value={"tools": []}),
            patch(f"{_MODULE}.is_agent_network_hocon", return_value=True),
            patch(f"{_MODULE}.load_agent_network", return_value=mock_network),
            patch(f"{_MODULE}.extract_llm_configs_from_agent_network", return_value=llm_configs) as mock_extract,
            patch(f"{_MODULE}.extract_llm_configs_from_studio_config") as mock_extract_studio,
            patch(f"{_MODULE}.create_and_load_llm_factory", return_value=MagicMock()),
            patch(f"{_MODULE}.test_llm_configs", new=AsyncMock(return_value=(successes, []))),
            patch(f"{_MODULE}.print_results"),
        ):
            LlmConfigValidatorPlugin().check("network.hocon")
            mock_extract.assert_called_once_with(mock_network)
            mock_extract_studio.assert_not_called()
