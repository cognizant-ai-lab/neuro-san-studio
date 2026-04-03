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

"""Tests for the LangfuseStudioPlugin wrapper."""

from unittest.mock import patch

from plugins.base_plugin import BasePlugin
from plugins.langfuse.langfuse_plugin import LangfusePlugin
from plugins.langfuse.langfuse_plugin import LangfuseStudioPlugin


class TestLangfuseStudioPlugin:
    """Tests for LangfuseStudioPlugin."""

    def test_extends_both_parents(self):
        """Test that LangfuseStudioPlugin extends both LangfusePlugin and BasePlugin."""
        assert issubclass(LangfuseStudioPlugin, LangfusePlugin)
        assert issubclass(LangfuseStudioPlugin, BasePlugin)

    def test_constructor_sets_plugin_name(self):
        """Test that the constructor properly sets plugin_name."""
        plugin = LangfuseStudioPlugin()
        assert plugin.plugin_name == "LangfuseStudio"

    def test_constructor_accepts_args(self):
        """Test that the constructor accepts args parameter."""
        plugin = LangfuseStudioPlugin(args={"test": True})
        assert plugin.args == {"test": True}

    def test_constructor_defaults_args(self):
        """Test that the constructor defaults args to empty dict."""
        plugin = LangfuseStudioPlugin()
        assert plugin.args == {}

    @patch.object(LangfusePlugin, "initialize")
    def test_initialize_delegates_to_parent(self, mock_init):
        """Test that initialize delegates to LangfusePlugin.initialize."""
        plugin = LangfuseStudioPlugin()
        plugin.initialize()
        mock_init.assert_called_once()

    @patch.object(LangfusePlugin, "shutdown")
    def test_cleanup_delegates_to_shutdown(self, mock_shutdown):
        """Test that cleanup delegates to LangfusePlugin.shutdown."""
        plugin = LangfuseStudioPlugin()
        plugin.cleanup()
        mock_shutdown.assert_called_once()
