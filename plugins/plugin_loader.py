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

"""
Shared utility for loading plugins from a JSON configuration file.

Used by both the runner (run.py) and the server wrapper
(neuro_san_server_wrapper.py) to avoid duplicating the loading logic.
"""

import importlib
import json
from typing import List
from typing import Type


class PluginLoader:  # pylint: disable=too-few-public-methods
    """Loads plugin classes from a JSON configuration file."""

    @staticmethod
    def load_plugin_classes(plugins_file: str) -> List[Type]:
        """Load plugin classes from a JSON configuration file.

        Each entry in the JSON file's `plugins` list must specify a
        `module` (dotted Python import path) and a `class` (name of
        the class to import from that module).

        If the file is missing, malformed, or an individual plugin
        cannot be imported, a warning is printed and that plugin is
        skipped rather than crashing the entire startup.

        Args:
            plugins_file: Path to the JSON plugins configuration file.

        Returns:
            A list of successfully loaded plugin classes.
        """
        try:
            with open(plugins_file, "r", encoding="utf-8") as file_handle:
                plugins_config = json.load(file_handle)
        except FileNotFoundError:
            print(f"No plugins file found at {plugins_file}. Continuing without plugins.")
            return []
        except json.JSONDecodeError as exc:
            print(f"Failed to parse plugins file at {plugins_file}: {exc}. Continuing without plugins.")
            return []

        plugin_classes: List[Type] = []
        for plugin_info in plugins_config.get("plugins", []):
            module_path = plugin_info.get("module")
            class_name = plugin_info.get("class")
            try:
                module = importlib.import_module(module_path)
                plugin_cls = getattr(module, class_name)
                plugin_classes.append(plugin_cls)
                print(f"Loading plugin: {class_name} from module: {module_path}")
            except (ImportError, AttributeError) as exc:
                print(f"Warning: Failed to load plugin {class_name} from {module_path}: {exc}. Skipping.")

        return plugin_classes
