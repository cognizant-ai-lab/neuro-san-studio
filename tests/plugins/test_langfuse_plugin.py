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

"""Tests for the LangfusePlugin."""

from unittest.mock import patch

from plugins.base_plugin import BasePlugin
from plugins.langfuse.langfuse_plugin import LangfusePlugin


class TestLangfusePlugin:
    """Tests for LangfusePlugin."""

    def test_extends_base_plugin(self):
        """Test that LangfusePlugin extends BasePlugin."""
        assert issubclass(LangfusePlugin, BasePlugin)

    def test_constructor_sets_plugin_name(self):
        """Test that the constructor properly sets plugin_name."""
        plugin = LangfusePlugin()
        assert plugin.plugin_name == "Langfuse"

    def test_constructor_accepts_args(self):
        """Test that the constructor accepts args parameter."""
        plugin = LangfusePlugin(args={"test": True})
        assert plugin.args == {"test": True}

    def test_constructor_defaults_args(self):
        """Test that the constructor defaults args to empty dict."""
        plugin = LangfusePlugin()
        assert plugin.args == {}

    def test_constructor_initializes_state(self):
        """Test that the constructor initializes internal state."""
        plugin = LangfusePlugin()
        assert plugin.is_initialized is False

    @patch.object(LangfusePlugin, "_get_bool_env", return_value=False)
    def test_initialize_skips_when_disabled(self, _mock_env):
        """Test that initialize is a no-op when LANGFUSE_ENABLED is false."""
        plugin = LangfusePlugin()
        plugin.initialize()
        assert plugin.is_initialized is False

    def test_cleanup_noop_when_not_initialized(self):
        """Test that cleanup is a no-op when not initialized."""
        plugin = LangfusePlugin()
        plugin.cleanup()
