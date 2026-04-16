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

from neuro_san_studio.interfaces.base_plugin import BasePlugin
from neuro_san_studio.plugins.factory.plugin_loader import PluginLoader


class TestPluginLoader:
    """Tests for PluginLoader.load_plugin_classes."""

    def test_load_from_valid_hocon(self):
        """Test loading plugins from a valid HOCON config."""
        hocon = """
plugins = [
    {
        class = "neuro_san_studio.interfaces.plugins.BasePlugin"
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
        class = "neuro_san_studio.interfaces.plugins.BasePlugin"
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
        class = "neuro_san_studio.interfaces.plugins.BasePlugin"
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
        class = neuro_san_studio.interfaces.plugins.BasePlugin
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
        class = "neuro_san_studio.interfaces.plugins.BasePlugin"
        enabled = true
    }
    {
        class = "neuro_san_studio.interfaces.plugins.BasePlugin"
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
