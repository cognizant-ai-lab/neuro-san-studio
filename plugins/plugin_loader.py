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
Shared utility for loading plugins from a HOCON configuration file.

Used by both the runner (run.py) and the server wrapper
(neuro_san_server_wrapper.py) to avoid duplicating the loading logic.
"""

import importlib
from typing import List
from typing import Type

from pyhocon import ConfigFactory
from pyhocon.exceptions import ConfigException


class PluginLoader:  # pylint: disable=too-few-public-methods
    """Loads plugin classes from a HOCON configuration file."""

    @staticmethod
    def load_plugin_classes(plugins_file: str) -> List[Type]:
        """Load plugin classes from a HOCON configuration file.

        Each entry in the `plugins` list must specify a `class`
        (fully qualified dotted path to the plugin class) and an
        optional `enabled` boolean (defaults to true).

        If the file is missing, malformed, or an individual plugin
        cannot be imported, a warning is printed and that plugin is
        skipped rather than crashing the entire startup.

        Args:
            plugins_file: Path to the HOCON plugins configuration file.

        Returns:
            A list of successfully loaded plugin classes.
        """
        try:
            config = ConfigFactory.parse_file(plugins_file)
        except FileNotFoundError:
            print(f"No plugins file found at {plugins_file}. Continuing without plugins.")
            return []
        except (ConfigException, Exception) as exc:  # pylint: disable=broad-exception-caught
            print(f"Failed to parse plugins file at {plugins_file}: {exc}. Continuing without plugins.")
            return []

        plugin_classes: List[Type] = []
        for plugin_entry in config.get("plugins", []):
            class_path = plugin_entry.get("class")
            enabled = plugin_entry.get("enabled", True)

            if not enabled:
                print(f"Plugin {class_path} is disabled. Skipping.")
                continue

            # Derive module path and class name from the fully qualified class path
            last_dot = class_path.rfind(".")
            module_path = class_path[:last_dot]
            class_name = class_path[last_dot + 1 :]

            try:
                module = importlib.import_module(module_path)
                plugin_cls = getattr(module, class_name)
                plugin_classes.append(plugin_cls)
                print(f"Loading plugin: {class_name} from module: {module_path}")
            except (ImportError, AttributeError) as exc:
                print(f"Warning: Failed to load plugin {class_name} from {module_path}: {exc}. Skipping.")

        return plugin_classes
