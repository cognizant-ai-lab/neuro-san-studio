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

import json
import os
import tempfile

from plugins.base_plugin import BasePlugin
from plugins.plugin_loader import PluginLoader


class TestPluginLoader:
    """Tests for PluginLoader.load_plugin_classes."""

    def test_load_from_valid_config(self):
        """Test loading plugins from a valid JSON config."""
        config = {
            "plugins": [
                {
                    "module": "plugins.base_plugin",
                    "class": "BasePlugin",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config, tmp)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert len(classes) == 1
            assert classes[0] is BasePlugin
        finally:
            os.unlink(tmp_path)

    def test_missing_file_returns_empty_list(self):
        """Test that a missing file returns an empty list."""
        classes = PluginLoader.load_plugin_classes("/nonexistent/path/plugins.json")
        assert not classes

    def test_malformed_json_returns_empty_list(self):
        """Test that malformed JSON returns an empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("{invalid json")
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_bad_module_skipped_gracefully(self):
        """Test that a bad module import is skipped without crashing."""
        config = {
            "plugins": [
                {
                    "module": "nonexistent.module",
                    "class": "FakePlugin",
                },
                {
                    "module": "plugins.base_plugin",
                    "class": "BasePlugin",
                },
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config, tmp)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert len(classes) == 1
            assert classes[0] is BasePlugin
        finally:
            os.unlink(tmp_path)

    def test_bad_class_name_skipped_gracefully(self):
        """Test that a missing class attribute is skipped without crashing."""
        config = {
            "plugins": [
                {
                    "module": "plugins.base_plugin",
                    "class": "NonexistentClass",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config, tmp)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_empty_plugins_list(self):
        """Test that an empty plugins list returns an empty list."""
        config = {"plugins": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config, tmp)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)

    def test_no_plugins_key(self):
        """Test that a config without a 'plugins' key returns an empty list."""
        config = {"other_key": "value"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config, tmp)
            tmp_path = tmp.name

        try:
            classes = PluginLoader.load_plugin_classes(tmp_path)
            assert not classes
        finally:
            os.unlink(tmp_path)
