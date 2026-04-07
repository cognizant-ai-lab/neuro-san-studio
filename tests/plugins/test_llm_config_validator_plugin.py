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

"""Tests for the LlmConfigValidatorPlugin as a BasePlugin subclass."""

import argparse

from neuro_san_studio.interfaces.plugins import BasePlugin
from plugins.llm_config_validator.llm_config_validator_plugin import LlmConfigValidatorPlugin


class TestLlmConfigValidatorPlugin:
    """Tests for LlmConfigValidatorPlugin BasePlugin integration."""

    def test_extends_base_plugin(self):
        """Test that LlmConfigValidatorPlugin is a BasePlugin subclass."""
        assert issubclass(LlmConfigValidatorPlugin, BasePlugin)

    def test_constructor_sets_plugin_name(self):
        """Test that the constructor sets the plugin name."""
        plugin = LlmConfigValidatorPlugin(args={})
        assert plugin.plugin_name == "LlmConfigValidator"

    def test_pre_server_start_action_noop_without_flag(self):
        """Test that pre_server_start_action is a no-op when check_llm_config is not set."""
        plugin = LlmConfigValidatorPlugin(args={})
        plugin.pre_server_start_action()

    def test_update_parser_args_adds_check_llm_config(self):
        """Test that update_parser_args adds the --check-llm-config argument."""
        parser = argparse.ArgumentParser()
        LlmConfigValidatorPlugin().update_parser_args(parser)
        args = parser.parse_args(["--check-llm-config", "path/to/config.hocon"])
        assert args.check_llm_config == "path/to/config.hocon"

    def test_update_parser_args_default_is_none(self):
        """Test that --check-llm-config defaults to None when not passed."""
        parser = argparse.ArgumentParser()
        LlmConfigValidatorPlugin().update_parser_args(parser)
        args = parser.parse_args([])
        assert args.check_llm_config is None
