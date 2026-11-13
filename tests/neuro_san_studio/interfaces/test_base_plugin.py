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

"""Tests for the BasePlugin class."""

from neuro_san_studio.interfaces.base_plugin import BasePlugin


class TestBasePlugin:
    """Tests for BasePlugin lifecycle and interface."""

    def test_constructor_sets_name_and_args(self):
        """Test that the constructor sets plugin_name and args."""
        plugin = BasePlugin("TestPlugin", {"key": "value"})
        assert plugin.plugin_name == "TestPlugin"
        assert plugin.args == {"key": "value"}

    def test_constructor_defaults_args_to_empty_dict(self):
        """Test that args defaults to an empty dict when not provided."""
        plugin = BasePlugin("TestPlugin")
        assert plugin.args == {}

    def test_constructor_none_args_defaults_to_empty_dict(self):
        """Test that passing None for args gives an empty dict."""
        plugin = BasePlugin("TestPlugin", None)
        assert plugin.args == {}

    def test_lifecycle_methods_are_noop(self):
        """Test that all lifecycle methods can be called without error."""
        plugin = BasePlugin("TestPlugin")
        plugin.pre_server_start_action()
        plugin.post_server_start_action()
        plugin.initialize()
        plugin.cleanup()

    def test_hook_methods_are_noop(self):
        """Test that hook configuration methods can be called without error."""
        BasePlugin("TestPlugin").update_args_dict({})
        BasePlugin("TestPlugin").update_parser_args(None)

    def test_update_args_dict_does_not_modify_dict(self):
        """Test that the base update_args_dict hook leaves the dict unchanged."""
        args = {"existing_key": "value"}
        BasePlugin("TestPlugin").update_args_dict(args)
        assert args == {"existing_key": "value"}

    def test_str_representation(self):
        """Test __str__ returns expected format."""
        plugin = BasePlugin("MyPlugin")
        assert str(plugin) == "MyPlugin Plugin"

    def test_repr_representation(self):
        """Test __repr__ returns expected format."""
        plugin = BasePlugin("MyPlugin")
        assert repr(plugin) == "MyPlugin Plugin"
