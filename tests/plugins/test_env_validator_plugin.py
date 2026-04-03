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

"""Tests for the EnvValidatorPlugin wrapper."""

import argparse

from plugins.base_plugin import BasePlugin
from plugins.env_validator.env_validator import EnvValidatorPlugin


class TestEnvValidatorPlugin:
    """Tests for EnvValidatorPlugin."""

    def test_extends_base_plugin(self):
        """Test that EnvValidatorPlugin is a BasePlugin subclass."""
        assert issubclass(EnvValidatorPlugin, BasePlugin)

    def test_constructor_sets_plugin_name(self):
        """Test that the constructor sets the plugin name."""
        plugin = EnvValidatorPlugin(args={})
        assert plugin.plugin_name == "Environment Validator"

    def test_pre_server_start_action_noop_without_flag(self):
        """Test that pre_server_start_action is a no-op when validate_keys is not set."""
        plugin = EnvValidatorPlugin(args={})
        plugin.pre_server_start_action()

    def test_update_parser_args_adds_validate_keys(self):
        """Test that update_parser_args adds the --validate-keys argument."""
        parser = argparse.ArgumentParser()
        EnvValidatorPlugin.update_parser_args(parser)
        args = parser.parse_args(["--validate-keys", "2"])
        assert args.validate_keys == 2
