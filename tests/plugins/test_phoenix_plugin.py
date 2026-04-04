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

"""Tests for the PhoenixPlugin."""

from unittest.mock import patch

from plugins.base_plugin import BasePlugin
from plugins.phoenix.phoenix_plugin import PhoenixPlugin


class TestPhoenixPlugin:
    """Tests for PhoenixPlugin."""

    def test_extends_base_plugin(self):
        """Test that PhoenixPlugin extends BasePlugin."""
        assert issubclass(PhoenixPlugin, BasePlugin)

    def test_constructor_sets_plugin_name(self):
        """Test that the constructor properly sets plugin_name."""
        plugin = PhoenixPlugin(args={"test": True})
        assert plugin.plugin_name == "Phoenix"

    def test_constructor_sets_args(self):
        """Test that the constructor properly sets args."""
        plugin = PhoenixPlugin(args={"test": True})
        assert plugin.args == {"test": True}

    def test_constructor_initializes_config(self):
        """Test that the constructor initializes config from defaults."""
        plugin = PhoenixPlugin()
        assert plugin.config is not None
        assert isinstance(plugin.config, dict)
        assert "phoenix_port" in plugin.config

    def test_constructor_initializes_state(self):
        """Test that the constructor initializes internal state."""
        plugin = PhoenixPlugin()
        assert plugin.is_initialized is False
        assert plugin.phoenix_process is None

    @patch.object(PhoenixPlugin, "start_phoenix_server")
    def test_pre_server_start_calls_start_phoenix(self, mock_start):
        """Test that pre_server_start_action delegates to start_phoenix_server."""
        plugin = PhoenixPlugin()
        plugin.pre_server_start_action()
        mock_start.assert_called_once()

    @patch.object(PhoenixPlugin, "stop_phoenix_server")
    def test_cleanup_calls_stop_phoenix(self, mock_stop):
        """Test that cleanup delegates to stop_phoenix_server."""
        plugin = PhoenixPlugin()
        plugin.cleanup()
        mock_stop.assert_called_once()

    def test_update_args_dict_adds_phoenix_config(self):
        """Test that update_args_dict adds Phoenix configuration keys."""
        args = {}
        PhoenixPlugin.update_args_dict(args)
        assert "phoenix_port" in args
        assert "otel_service_name" in args
