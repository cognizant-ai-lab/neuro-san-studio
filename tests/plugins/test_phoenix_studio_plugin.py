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

"""Tests for the PhoenixStudioPlugin wrapper."""

from unittest.mock import patch

from plugins.base_plugin import BasePlugin
from plugins.phoenix.phoenix_plugin import PhoenixPluginBase
from plugins.phoenix.phoenix_plugin import PhoenixStudioPlugin


class TestPhoenixStudioPlugin:
    """Tests for PhoenixStudioPlugin."""

    def test_extends_both_parents(self):
        """Test that PhoenixStudioPlugin extends both PhoenixPluginBase and BasePlugin."""
        assert issubclass(PhoenixStudioPlugin, PhoenixPluginBase)
        assert issubclass(PhoenixStudioPlugin, BasePlugin)

    def test_constructor_sets_plugin_name(self):
        """Test that the constructor properly sets plugin_name via BasePlugin."""
        plugin = PhoenixStudioPlugin(args={"test": True})
        assert plugin.plugin_name == "PhoenixStudioPlugin"

    def test_constructor_sets_args(self):
        """Test that the constructor properly sets args via BasePlugin."""
        plugin = PhoenixStudioPlugin(args={"test": True})
        assert plugin.args == {"test": True}

    def test_constructor_initializes_phoenix_base(self):
        """Test that the constructor initializes PhoenixPluginBase with config."""
        plugin = PhoenixStudioPlugin()
        assert plugin.config is not None
        assert isinstance(plugin.config, dict)

    @patch.object(PhoenixPluginBase, "start_phoenix_server")
    def test_pre_server_start_calls_start_phoenix(self, mock_start):
        """Test that pre_server_start_action delegates to start_phoenix_server."""
        plugin = PhoenixStudioPlugin()
        plugin.pre_server_start_action()
        mock_start.assert_called_once()

    @patch.object(PhoenixPluginBase, "stop_phoenix_server")
    def test_cleanup_calls_stop_phoenix(self, mock_stop):
        """Test that cleanup delegates to stop_phoenix_server."""
        plugin = PhoenixStudioPlugin()
        plugin.cleanup()
        mock_stop.assert_called_once()

    def test_update_args_dict_adds_phoenix_config(self):
        """Test that update_args_dict adds Phoenix configuration keys."""
        args = {}
        PhoenixStudioPlugin.update_args_dict(args)
        assert "phoenix_enabled" in args
        assert "phoenix_port" in args
        assert "otel_service_name" in args
