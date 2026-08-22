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

"""Tests for the PluginLoader utility."""

import os
import tempfile
from pathlib import Path

import pytest

from neuro_san_studio.interfaces.base_plugin import BasePlugin
from neuro_san_studio.plugins.plugin_loader import PluginLoader


class TestPluginLoader:
    """Tests for PluginLoader.load_plugin_classes."""

    def test_load_from_valid_hocon(self):
        """Test loading plugins from a valid HOCON config."""
        hocon = """
plugins = [
    {
        class = "neuro_san_studio.interfaces.base_plugin.BasePlugin"
        enabled = true
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert len(classes) == 1
            assert classes[0] is BasePlugin
        finally:
            os.unlink(tmp_path)

    def test_disabled_plugin_is_skipped(self):
        """Test that a plugin with enabled = false is not loaded."""
        hocon = """
plugins = [
    {
        class = "neuro_san_studio.interfaces.base_plugin.BasePlugin"
        enabled = false
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_missing_enabled_defaults_to_true(self):
        """Test that a plugin without an enabled field defaults to enabled."""
        hocon = """
plugins = [
    {
        class = "neuro_san_studio.interfaces.base_plugin.BasePlugin"
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert len(classes) == 1
            assert classes[0] is BasePlugin
        finally:
            os.unlink(tmp_path)

    def test_missing_file_returns_empty_list(self):
        """Test that a missing file returns an empty list."""
        classes = PluginLoader.load_plugin_classes("/nonexistent/path/plugins.hocon")
        assert not classes

    def test_malformed_hocon_returns_empty_list(self):
        """Test that malformed HOCON returns an empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write("{{{invalid hocon")
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_bad_module_skipped_gracefully(self):
        """Test that a bad module import is skipped without crashing."""
        hocon = """
plugins = [
    {
        class = nonexistent.module.FakePlugin
        enabled = true
    }
    {
        class = neuro_san_studio.interfaces.base_plugin.BasePlugin
        enabled = true
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert len(classes) == 1
            assert classes[0] is BasePlugin
        finally:
            os.unlink(tmp_path)

    def test_bad_class_name_skipped_gracefully(self):
        """Test that a missing class attribute is skipped without crashing."""
        hocon = """
plugins = [
    {
        class = neuro_san_studio.interfaces.plugins.NonexistentClass
        enabled = true
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_empty_plugins_list(self):
        """Test that an empty plugins list returns an empty list."""
        hocon = "plugins = []"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_no_plugins_key(self):
        """Test that a config without a 'plugins' key returns an empty list."""
        hocon = "other_key = value"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_mix_of_enabled_and_disabled(self):
        """Test loading a mix of enabled and disabled plugins."""
        hocon = """
plugins = [
    {
        class = "neuro_san_studio.interfaces.base_plugin.BasePlugin"
        enabled = true
    }
    {
        class = "neuro_san_studio.interfaces.base_plugin.BasePlugin"
        enabled = false
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert len(classes) == 1
        finally:
            os.unlink(tmp_path)

    def test_string_false_disables_plugin(self):
        """Test that a string 'False' (from env var substitution) disables the plugin."""
        hocon = """
plugins = [
    {
        class = "neuro_san_studio.interfaces.base_plugin.BasePlugin"
        enabled = "False"
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_string_true_enables_plugin(self):
        """Test that a string 'true' (from env var substitution) enables the plugin."""
        hocon = """
plugins = [
    {
        class = "neuro_san_studio.interfaces.base_plugin.BasePlugin"
        enabled = "true"
    }
]
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".hocon", delete=False) as tmp:
            tmp.write(hocon)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert len(classes) == 1
            assert classes[0] is BasePlugin
        finally:
            os.unlink(tmp_path)


class TestIsEnabled:  # pylint: disable=protected-access
    """Tests for PluginLoader._is_enabled."""

    def test_bool_true(self):
        """Test that boolean True returns True."""
        assert PluginLoader._is_enabled({"enabled": True}) is True

    def test_bool_false(self):
        """Test that boolean False returns False."""
        assert PluginLoader._is_enabled({"enabled": False}) is False

    def test_missing_key_defaults_to_true(self):
        """Test that a missing 'enabled' key defaults to True."""
        assert PluginLoader._is_enabled({}) is True

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "Yes"])
    def test_string_true_variants(self, value):
        """Test that string truthy values are recognized."""
        assert PluginLoader._is_enabled({"enabled": value}) is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", ""])
    def test_string_false_variants(self, value):
        """Test that string falsy values are recognized."""
        assert PluginLoader._is_enabled({"enabled": value}) is False


class TestResolvePluginsFile:
    """Tests for PluginLoader.resolve_plugins_file."""

    def test_user_local_path_used_when_file_exists(self, tmp_path: Path) -> None:
        """A scaffolded <root_dir>/config/plugins.hocon wins over the bundled fallback."""
        scaffolded = tmp_path / "config" / "plugins.hocon"
        scaffolded.parent.mkdir()
        scaffolded.write_text("plugins = []\n")
        assert PluginLoader.resolve_plugins_file(str(tmp_path)) == str(scaffolded)

    def test_falls_back_to_bundled(self, tmp_path: Path) -> None:
        """With no scaffolded copy, the bundled templates path is returned."""
        result = PluginLoader.resolve_plugins_file(str(tmp_path))
        assert os.path.isfile(result)
        assert result.endswith(os.path.join("neuro_san_studio", "templates", "plugins.hocon"))
