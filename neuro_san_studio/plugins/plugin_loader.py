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

Used by both the runner (neuro_san_studio/commands/run.py) and the server wrapper
(neuro_san_studio/runner/neuro_san_server_wrapper.py) to avoid duplicating the loading logic.
"""

import importlib
import logging
import os
import types
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Type

from pyhocon import ConfigFactory
from pyhocon import ConfigTree
from pyhocon.exceptions import ConfigException

from neuro_san_studio import templates as _templates_pkg

_logger = logging.getLogger("PluginLoader")

# Path to the plugins.hocon that ships inside the neuro_san_studio package.
# Resolving via the imported package's __file__ works both in-repo (where
# neuro_san_studio/ is just a folder on sys.path) and after `pip install`
# (where it lives in site-packages), on every supported platform.
_BUNDLED_PLUGINS_FILE = os.path.join(os.path.dirname(_templates_pkg.__file__), "plugins.hocon")


class PluginLoader:
    """Loads plugin classes from a HOCON configuration file."""

    @staticmethod
    def resolve_plugins_file(root_dir: str) -> str:
        """Resolve the plugins.hocon file path.

        Precedence:
          1. <root_dir>/config/plugins.hocon if it exists (user's editable copy,
             scaffolded by `ns init`).
          2. The plugins.hocon shipped inside the neuro_san_studio package.
        """
        scaffolded_path = os.path.join(root_dir, "config", "plugins.hocon")
        if os.path.isfile(scaffolded_path):
            return scaffolded_path
        return _BUNDLED_PLUGINS_FILE

    @staticmethod
    def _is_enabled(plugin_entry: Dict[str, Any]) -> bool:
        """Determine whether a plugin entry is enabled, handling string env var substitutions."""
        value = plugin_entry.get("enabled", True)
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

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
            config: ConfigTree = ConfigFactory.parse_file(plugins_file)
        except FileNotFoundError:
            _logger.info("No plugins file found at %s. Continuing without plugins.", plugins_file)
            return []
        except (ConfigException, Exception) as exc:  # pylint: disable=broad-exception-caught
            _logger.warning("Failed to parse plugins file at %s: %s. Continuing without plugins.", plugins_file, exc)
            return []

        plugin_classes: List[Type] = []
        plugin_entry: Dict[str, Any]
        for plugin_entry in config.get("plugins", []):
            class_path: Optional[str] = plugin_entry.get("class")
            enabled: bool = PluginLoader._is_enabled(plugin_entry)

            if not enabled:
                _logger.info("Plugin %s is disabled. Skipping.", class_path)
                continue

            # Derive module path and class name from the fully qualified class path
            last_dot: int = class_path.rfind(".")
            module_path: str = class_path[:last_dot]
            class_name: str = class_path[last_dot + 1 :]

            try:
                module: types.ModuleType = importlib.import_module(module_path)
                plugin_cls: Type = getattr(module, class_name)
                plugin_classes.append(plugin_cls)
                _logger.info("Loading plugin: %s from module: %s", class_name, module_path)
            except (ImportError, AttributeError) as exc:
                _logger.warning("Failed to load plugin %s from %s: %s. Skipping.", class_name, module_path, exc)

        return plugin_classes
